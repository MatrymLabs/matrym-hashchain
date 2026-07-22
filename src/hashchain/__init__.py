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

Honest bounds -- the chain alone proves INTEGRITY; two optional features extend it:
- Detected by the chain: a changed payload (hash mismatch), a reordered or inserted record, a
  deleted MIDDLE record (the next record's prior-hash no longer links).
- Truncation (dropping the LAST record(s)) is invisible to the chain alone -- anchor `head_hash`
  elsewhere (a receipt, a second store, a witness) and check it via `verify(expected_head=...)`.
- Authenticity (WHO wrote it) is not integrity -- pass a secret `key` to sign records with HMAC,
  a symmetric shared-secret MAC (proves "written by a key-holder"), not public-key non-repudiation.
Any break fails loud with `HashChainError` rather than returning a dishonest history.

Provenance: this is a MatrymLabs Hardware Store part -- a pattern first proven in the CodeForge MUD
engine (the "Chronicle", the game's tamper-evident memory) and reused across the fleet (a federal
guidance-check ledger; an AI-triage decision audit trail). Published standalone so any project can
reuse the same tested primitive.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__version__ = "0.4.0"
__all__ = [
    "GENESIS",
    "Entry",
    "HashChainError",
    "append",
    "content_hash",
    "head_hash",
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


def content_hash(payload: Mapping[str, Any], *, key: bytes | None = None) -> str:
    """A deterministic digest over a JSON-serializable mapping (canonical: sorted keys, compact).

    Unkeyed (`key=None`) it is a plain sha256 -- integrity only. Given a secret `key` it is instead
    an HMAC-sha256, so only a holder of that key can produce or validate the digest: that is what
    turns the ledger from tamper-EVIDENT into tamper-evident AND authorship-bound. An HMAC is a
    symmetric shared-secret MAC (it proves "written by a key-holder"), not public-key
    non-repudiation. The same `key` must be passed to every call over a given ledger."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if key is None:
        return hashlib.sha256(canonical).hexdigest()
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def _digest(seq: int, payload: Mapping[str, Any], prior_hash: str, *, key: bytes | None) -> str:
    return content_hash({"seq": seq, "payload": payload, "prior_hash": prior_hash}, key=key)


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


def _tail(path: Path, *, key: bytes | None) -> Entry | None:
    """The last entry, validated on its OWN content hash (O(1)) but not chain-verified against the
    whole ledger -- that stays `read`/`verify`'s job, on demand. None for an empty/missing store.
    A corrupt TAIL is caught here (we never chain onto garbage); a tampered EARLIER record is caught
    on read, not hidden -- tamper-evidence is preserved, eager re-verification is not."""
    line = _last_line(path)
    if line is None:
        return None
    row = _parse_row(line, -1)
    if _digest(row["seq"], row["payload"], row["prior_hash"], key=key) != row["content_hash"]:
        raise HashChainError(f"record {row['seq']} was tampered: content hash mismatch")
    return Entry(row["seq"], row["payload"], row["prior_hash"], row["content_hash"])


def append(path: Path, payload: dict[str, Any], *, key: bytes | None = None) -> Entry:
    """Validate, hash-chain, and append one record; return the new Entry.

    Chains onto the ledger's TAIL in O(1): it reads only the last record (validating that record's
    own hash), not the whole file, so appends stay fast as the ledger grows without bound. Full
    integrity is `read`/`verify`'s job, on demand -- a tampered PAST record is caught there, never
    hidden. Tamper-evidence is preserved; only eager re-verification on every append is dropped.

    Pass a secret `key` to sign the record with HMAC (authorship-bound, not just tamper-evident);
    the same key must then be given to every append/read/verify over this ledger. See `content_hash`
    for what signing does and does not prove."""
    if not isinstance(payload, dict):
        raise HashChainError("payload must be a JSON object (dict)")
    tail = _tail(path, key=key)
    prior = tail.content_hash if tail else GENESIS
    seq = tail.seq + 1 if tail else 0
    try:
        digest = _digest(seq, payload, prior, key=key)
    except (TypeError, ValueError) as exc:
        raise HashChainError(f"payload is not JSON-serializable: {exc}") from exc
    entry = Entry(seq=seq, payload=payload, prior_hash=prior, content_hash=digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_as_row(entry), sort_keys=True) + "\n")
    return entry


def read(path: Path, *, key: bytes | None = None) -> list[Entry]:
    """Read every record, verifying the chain as it goes. Fails loud (`HashChainError`) on a
    tampered payload, a broken/reordered chain, or a malformed line. Empty/missing store -> [].

    Pass the same secret `key` the ledger was signed with; a signed ledger read without it (or with
    the wrong key) fails as a content-hash mismatch, since the HMAC will not reproduce."""
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
        if _digest(row["seq"], row["payload"], row["prior_hash"], key=key) != row["content_hash"]:
            raise HashChainError(f"record {row['seq']} was tampered: content hash mismatch")
        if row["prior_hash"] != prev_hash:
            raise HashChainError(f"broken chain at record {row['seq']}: prior hash does not link")
        entries.append(Entry(row["seq"], row["payload"], row["prior_hash"], row["content_hash"]))
        prev_hash = row["content_hash"]
    return entries


def head_hash(path: Path, *, key: bytes | None = None) -> str:
    """The content hash of the ledger's last record, or `GENESIS` for an empty/missing store.

    This is the truncation anchor: dropping the last record(s) is invisible to the chain alone, so
    record this head somewhere the ledger cannot reach (a receipt, a second store, a witness) and
    later assert the ledger still ends there via `verify(path, expected_head=...)`. O(1): reads only
    the tail (validating that one record's own hash), never the whole file."""
    tail = _tail(path, key=key)
    return tail.content_hash if tail else GENESIS


def verify(path: Path, *, key: bytes | None = None, expected_head: str | None = None) -> bool:
    """True if the ledger reads clean end to end, False if the chain is broken or a line is bad.

    Pass `key` to verify a signed ledger (authorship, not just integrity). Pass `expected_head` (a
    hash you anchored earlier via `head_hash`) to also catch truncation: if the ledger no longer
    ends at that head -- the tail was dropped, or it is otherwise not the log you anchored -- this
    returns False even though the surviving chain reads clean on its own."""
    try:
        entries = read(path, key=key)
    except HashChainError:
        return False
    if expected_head is not None:
        actual_head = entries[-1].content_hash if entries else GENESIS
        return actual_head == expected_head
    return True


def _as_row(entry: Entry) -> dict[str, Any]:
    return {
        "seq": entry.seq,
        "payload": entry.payload,
        "prior_hash": entry.prior_hash,
        "content_hash": entry.content_hash,
    }
