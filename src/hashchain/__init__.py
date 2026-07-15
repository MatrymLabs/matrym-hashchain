"""A tamper-evident, append-only, hash-chained ledger. Dependency-free (stdlib only).

Each entry carries a sha256 over its own payload AND the previous entry's hash, so any later edit,
reorder, or removal of a PAST record is detected the next time the log is read. A file-simple,
zero-dependency primitive for audit trails, transaction logs, and chain-of-custody records.

    from pathlib import Path
    from hashchain import append, read, verify

    p = Path("audit.jsonl")
    append(p, {"event": "created", "who": "alice"})
    append(p, {"event": "approved", "who": "bob"})
    verify(p)   # True -- the history reads clean end to end

Honest bounds -- this proves INTEGRITY, not everything:
- Detected: a changed payload (hash mismatch), a reordered or inserted record, a deleted MIDDLE
  record (the next record's prior-hash no longer links).
- NOT detected by the chain alone: dropping the LAST record(s) -- anchor the head hash elsewhere
  (a receipt, a second store) if truncation must be caught. And integrity is not authenticity:
  sign the head hash to prove WHO wrote it.
Any break fails loud with `HashChainError` rather than returning a dishonest history.

Provenance: this is a MatrymLabs Hardware Store part -- a pattern first proven in the CodeForge MUD
engine (the "Chronicle", the game's tamper-evident memory) and reused across the fleet (a federal
guidance-check ledger; an AI-triage decision audit trail). Published standalone so any project can
reuse the same tested primitive.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__version__ = "0.1.1"
__all__ = [
    "GENESIS",
    "Entry",
    "HashChainError",
    "append",
    "content_hash",
    "read",
    "verify",
]

GENESIS = ""  # the prior_hash of the first entry: nothing precedes it
_FIELDS = ("seq", "payload", "prior_hash", "content_hash")


class HashChainError(Exception):
    """Raised when the ledger is malformed or its chain is broken. Names the exact record."""


@dataclass(frozen=True)
class Entry:
    """One entry in the chain: its position, its data, and the hashes that bind it to the past."""

    seq: int
    payload: dict[str, Any]
    prior_hash: str
    content_hash: str


def content_hash(payload: Mapping[str, Any]) -> str:
    """A deterministic sha256 over a JSON-serializable mapping (canonical: sorted keys, compact)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _digest(seq: int, payload: Mapping[str, Any], prior_hash: str) -> str:
    return content_hash({"seq": seq, "payload": payload, "prior_hash": prior_hash})


def _parse_row(line: str, lineno: int) -> dict[str, Any]:
    """Parse and shape-check one JSONL record (valid JSON, all fields present). No chain check."""
    try:
        row = json.loads(line)
    except json.JSONDecodeError as exc:
        raise HashChainError(f"line {lineno} is unreadable JSON: {exc}") from exc
    if not isinstance(row, dict) or not all(field in row for field in _FIELDS):
        raise HashChainError(f"line {lineno} is a malformed record (missing fields)")
    return row


def _last_line(path: Path) -> str | None:
    """The last non-empty line, read WITHOUT scanning the whole file: seek to the end and walk
    back to the preceding newline. None for an empty/missing store. This keeps `append` O(1) in
    ledger size; full-chain integrity stays `read`/`verify`'s job, on demand."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    with path.open("rb") as handle:
        size = handle.seek(0, 2)  # end of file
        data = b""
        while size > 0:
            step = min(4096, size)
            size -= step
            handle.seek(size)
            data = handle.read(step) + data
            stripped = data.rstrip(b"\n")
            newline = stripped.rfind(b"\n")
            if newline != -1:
                return stripped[newline + 1 :].decode("utf-8")
        text = data.strip().decode("utf-8")
        return text or None


def _tail(path: Path) -> Entry | None:
    """The last entry, validated on its OWN content hash (O(1)) but not chain-verified against the
    whole ledger -- that stays `read`/`verify`'s job, on demand. None for an empty/missing store.
    A corrupt TAIL is caught here (we never chain onto garbage); a tampered EARLIER record is caught
    on read, not hidden -- tamper-evidence is preserved, eager re-verification is not."""
    line = _last_line(path)
    if line is None:
        return None
    row = _parse_row(line, -1)
    if _digest(row["seq"], row["payload"], row["prior_hash"]) != row["content_hash"]:
        raise HashChainError(f"record {row['seq']} was tampered: content hash mismatch")
    return Entry(row["seq"], row["payload"], row["prior_hash"], row["content_hash"])


def append(path: Path, payload: dict[str, Any]) -> Entry:
    """Validate, hash-chain, and append one record; return the new Entry.

    Chains onto the ledger's TAIL in O(1): it reads only the last record (validating that record's
    own hash), not the whole file, so appends stay fast as the ledger grows without bound. Full
    integrity is `read`/`verify`'s job, on demand -- a tampered PAST record is caught there, never
    hidden. Tamper-evidence is preserved; only eager re-verification on every append is dropped."""
    if not isinstance(payload, dict):
        raise HashChainError("payload must be a JSON object (dict)")
    tail = _tail(path)
    prior = tail.content_hash if tail else GENESIS
    seq = tail.seq + 1 if tail else 0
    try:
        digest = _digest(seq, payload, prior)
    except (TypeError, ValueError) as exc:
        raise HashChainError(f"payload is not JSON-serializable: {exc}") from exc
    entry = Entry(seq=seq, payload=payload, prior_hash=prior, content_hash=digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_as_row(entry), sort_keys=True) + "\n")
    return entry


def read(path: Path) -> list[Entry]:
    """Read every record, verifying the chain as it goes. Fails loud (`HashChainError`) on a
    tampered payload, a broken/reordered chain, or a malformed line. Empty/missing store -> []."""
    if not path.exists():
        return []
    entries: list[Entry] = []
    prev_hash = GENESIS
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        row = _parse_row(line, lineno)
        expected_seq = len(entries)
        if row["seq"] != expected_seq:
            raise HashChainError(
                f"record {row['seq']} is out of order (expected seq {expected_seq})"
            )
        if _digest(row["seq"], row["payload"], row["prior_hash"]) != row["content_hash"]:
            raise HashChainError(f"record {row['seq']} was tampered: content hash mismatch")
        if row["prior_hash"] != prev_hash:
            raise HashChainError(f"broken chain at record {row['seq']}: prior hash does not link")
        entries.append(Entry(row["seq"], row["payload"], row["prior_hash"], row["content_hash"]))
        prev_hash = row["content_hash"]
    return entries


def verify(path: Path) -> bool:
    """True if the ledger reads clean end to end, False if the chain is broken or a line is bad."""
    try:
        read(path)
        return True
    except HashChainError:
        return False


def _as_row(entry: Entry) -> dict[str, Any]:
    return {
        "seq": entry.seq,
        "payload": entry.payload,
        "prior_hash": entry.prior_hash,
        "content_hash": entry.content_hash,
    }
