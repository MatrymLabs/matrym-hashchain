# Changelog

All notable changes to `matrym-hashchain`. Format follows
[Keep a Changelog](https://keepachangelog.com/); this is 0.x, so the API may still move.

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
