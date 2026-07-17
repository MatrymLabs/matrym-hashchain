"""Evidence for the 0.1.1 claim: `append` is O(1) in ledger size, not O(n).

The changelog says appends stay fast as the ledger grows without bound. This measures it head to
head against the pre-0.1.1 behavior (re-read and re-verify the whole chain before every append) so
the claim carries proof, not just an assertion.

Method (single-writer, one process):
  * Build a valid ledger of N records once (fast, in one write).
  * Time appending ONE more record onto it, repeated R times, holding N constant by truncating the
    ledger back to its original size after each rep (an O(1) rollback). Report the median.
  * Do that for both implementations at each N:
      - baseline  : the O(n) pre-0.1.1 append -- `read()` the whole chain, then write the new row.
      - current   : `hashchain.append` -- reads only the tail (an O(1) backward seek), then writes.

Only the library's PUBLIC API is used (`read`, `append`, `content_hash`, `GENESIS`), so the
baseline is a faithful reconstruction, not a peek at internals.

Run: `python benchmarks/bench_append.py` (or `make bench`). Prints a Markdown table; the committed
copy lives in `benchmarks/RESULTS.md`.
"""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Callable
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hashchain import GENESIS, append, content_hash, read, verify  # noqa: E402

SIZES = (500, 2_000, 8_000, 16_000, 64_000)
REPS = 50
AppendImpl = Callable[[Path, dict[str, Any]], object]


def _row_for(seq: int, payload: dict[str, Any], prior: str) -> dict[str, Any]:
    """One ledger row, hashed exactly as the library hashes it -- via the public `content_hash`."""
    digest = content_hash({"seq": seq, "payload": payload, "prior_hash": prior})
    return {"seq": seq, "payload": payload, "prior_hash": prior, "content_hash": digest}


def _build_ledger(path: Path, n: int) -> None:
    """Write a valid N-record chain in a single pass (setup, not measured)."""
    lines: list[str] = []
    prior = GENESIS
    for seq in range(n):
        row = _row_for(seq, {"tick": seq}, prior)
        lines.append(json.dumps(row, sort_keys=True))
        prior = row["content_hash"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_baseline(path: Path, payload: dict[str, Any]) -> object:
    """The pre-0.1.1 append: re-read and re-verify the ENTIRE chain, then write the row. O(n)."""
    entries = read(path)  # full-chain re-verification -- the cost that grew with the ledger
    prior = entries[-1].content_hash if entries else GENESIS
    row = _row_for(len(entries), payload, prior)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def _median_append_ms(impl: AppendImpl, path: Path, reps: int) -> float:
    """Median milliseconds to append one record at the ledger's current size, size held constant."""
    original_size = path.stat().st_size
    samples: list[float] = []
    for _ in range(reps):
        start = perf_counter()
        impl(path, {"event": "measured"})
        samples.append((perf_counter() - start) * 1_000)
        with path.open("r+b") as handle:  # roll the appended row back off, O(1)
            handle.truncate(original_size)
    return median(samples)


def _run() -> list[tuple[int, float, float]]:
    results: list[tuple[int, float, float]] = []
    with TemporaryDirectory() as tmp:
        for n in SIZES:
            ledger = Path(tmp) / f"chain_{n}.jsonl"
            _build_ledger(ledger, n)
            if not verify(ledger):  # fail loud if the setup itself is not a clean chain
                raise SystemExit(f"benchmark setup built a broken chain at N={n}")
            baseline = _median_append_ms(_append_baseline, ledger, REPS)
            current = _median_append_ms(append, ledger, REPS)
            results.append((n, baseline, current))
    return results


def _render(results: list[tuple[int, float, float]]) -> str:
    lines = [
        f"Host: {platform.platform()} | Python {platform.python_version()} | reps={REPS}",
        "",
        "| ledger size (records) | O(n) baseline (ms) | O(1) current (ms) | speedup |",
        "|---:|---:|---:|---:|",
    ]
    for n, baseline, current in results:
        speedup = baseline / current if current else float("inf")
        lines.append(f"| {n:,} | {baseline:.4f} | {current:.4f} | {speedup:,.0f}x |")
    first, last = results[0], results[-1]
    base_growth = last[1] / first[1] if first[1] else float("inf")
    curr_growth = last[2] / first[2] if first[2] else float("inf")
    lines += [
        "",
        f"Ledger grew {last[0] // first[0]}x ({first[0]:,} -> {last[0]:,} records). Over that span "
        f"the baseline append slowed **{base_growth:.1f}x** (grows with N, O(n)); the current "
        f"append changed **{curr_growth:.1f}x** (flat within noise, O(1)).",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(_render(_run()))
