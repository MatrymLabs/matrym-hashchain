# Changelog

All notable changes to `matrym-hashchain`. Format follows
[Keep a Changelog](https://keepachangelog.com/); this is 0.x, so the API may still move.

## [Unreleased]

### Added
- **Command line interface.** `matrym-hashchain {append,read,verify}` (also `python -m hashchain`),
  a thin caller over the library's public functions. `verify` exits 0 on a clean chain and 1 on a
  broken one, naming the tampered record on stderr, so it drops into a shell gate or CI step;
  `append` reads its payload object from an argument or from stdin.
- **Benchmark evidence** for the O(1) append claim (`benchmarks/`, `make bench`): head to head
  against the pre-0.1.1 O(n) behavior, the current append stays flat as the ledger grows.

## [0.1.1] - 2026-07-15

### Changed
- **`append` is now O(1) instead of O(n).** It previously re-read and re-hashed the entire ledger
  to verify the whole chain before every append; it now reads only the ledger's tail (validating
  that record's own hash) and chains onto it. Appends stay fast as the ledger grows without bound.
- **Tamper-evidence is unchanged.** A tampered *past* record is still caught by `read`/`verify`
  (which remain the full-chain integrity check, on demand); a tampered *tail* is still caught at
  append. Only *eager re-verification on every append* is dropped. No API change.

## [0.1.0] - 2026-07-14

### Added
- First public release. A tamper-evident, append-only, hash-chained ledger, dependency-free
  (stdlib only): `append`, `read`, `verify`, `content_hash`, `Entry`, `HashChainError`.
- Detects a tampered payload, a reordered or inserted record, and a deleted *middle* record;
  fails loud with `HashChainError`. Honest bounds documented (integrity, not authenticity; last-
  record truncation needs a separate anchor).
- Ships type hints (`py.typed`), MIT license, and CI (ruff + mypy --strict + pytest).
- Harvested from the CodeForge MUD engine's "Chronicle" and proven across the MatrymLabs fleet
  before being published standalone.
