# Benchmark: `append` is O(1) in ledger size

Evidence for the 0.1.1 change (`append` reads only the tail, not the whole chain). Reproduce with
`make bench` (or `python benchmarks/bench_append.py`); the harness and method live in
[`bench_append.py`](bench_append.py). Numbers are host-specific, the *shape* is the point.

Host: Linux-6.18.34+rpt-rpi-2712-aarch64-with-glibc2.41 | Python 3.13.5 | reps=50

| ledger size (records) | O(n) baseline (ms) | O(1) current (ms) | speedup |
|---:|---:|---:|---:|
| 500 | 6.2526 | 0.0751 | 83x |
| 2,000 | 29.4551 | 0.0754 | 391x |
| 8,000 | 113.6527 | 0.0969 | 1,172x |
| 16,000 | 229.1265 | 0.0761 | 3,011x |

Ledger grew 32x (500 -> 16,000 records). Over that span the baseline append slowed **36.6x** (grows
with N, O(n)); the current append changed **1.0x** (flat within noise, O(1)).

## What is being compared

- **baseline** - the pre-0.1.1 append: `read()` the whole chain (re-verifying every record), then
  write the new row. Its cost grows with the ledger.
- **current** - `hashchain.append`: read only the ledger's tail via a backward seek (validating that
  one record's own hash), then write. Its cost is independent of ledger size.

Both are driven through the library's public API only, so the baseline is a faithful reconstruction
of the old behavior, not a peek at internals. Ledger size is held constant across repetitions by
truncating each measured append back off (an O(1) rollback), so each row times a single append at a
fixed N rather than a growing one.

## Honest label

**Verified improvement.** The baseline's per-append time scales linearly with N while the current
implementation's stays flat within measurement noise; the tamper-evidence guarantee is unchanged
(`read`/`verify` remain the full-chain integrity check). This is a genuine algorithmic win, not a
refactor relabelled, and not a gain inside noise.
