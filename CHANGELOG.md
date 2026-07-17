# Changelog

All notable changes to `matrym-hashchain`. Format follows
[Keep a Changelog](https://keepachangelog.com/); this is 0.x, so the API may still move.

## [0.3.0] - 2026-07-16

### Added
- **CLI signing and truncation anchoring.** `--key-env VAR` signs/verifies with the HMAC key held
  in an environment variable (never on the command line, so it can't leak to the process table); a
  new `head` command prints the anchor hash and `verify --expected-head HASH` catches a dropped tail.
- **bandit SAST** over the shipped library, folded into `make security` (now bandit + pip-audit)
  and CI, closing the "bandit + pip-audit" tooling gap.
- **CodeQL** workflow (GitHub-native SAST; results in the Security > Code scanning tab).
- A README **Evaluation** section: `forge-audit` scores this part `pass` at the advanced stage.
- A **64k-record tier** in the append benchmark (`make bench`): at 64k the O(n) baseline costs
  ~930 ms per append while the O(1) current append still costs ~0.08 ms (~11,900x).

## [0.2.0] - 2026-07-16

### Added
- **Optional HMAC signing** closes the authenticity gap. Pass a secret `key=` to `append`/`read`/
  `verify`/`head_hash`/`content_hash` and records are signed with HMAC-SHA256, so only a key-holder
  can produce or validate them. `key=None` is unchanged plain-SHA-256 behavior (backward
  compatible). Honestly labelled: a symmetric shared-secret MAC, not public-key non-repudiation.
- **Truncation anchoring** closes the last-record-drop gap. `head_hash(path)` returns the tail's
  content hash to stash off-ledger; `verify(path, expected_head=...)` confirms the ledger still
  ends there, catching a dropped tail the chain alone cannot see.
- **Command line interface.** `matrym-hashchain {append,read,verify}` (also `python -m hashchain`),
  a thin caller over the library's public functions. `verify` exits 0 on a clean chain and 1 on a
  broken one, naming the tampered record on stderr, so it drops into a shell gate or CI step;
  `append` reads its payload object from an argument or from stdin.
- **Benchmark evidence** for the O(1) append claim (`benchmarks/`, `make bench`): head to head
  against the pre-0.1.1 O(n) behavior, the current append stays flat as the ledger grows.
- **Coverage and security gates.** CI now enforces **100% line + branch coverage** (`make
  coverage`) and audits the project's dependency closure with `pip-audit` (`make security`), so
  the "zero dependencies" claim is verified rather than asserted. Adds a Codecov badge.
- A refusal test for a self-consistent record that points at the wrong predecessor (only the
  chain-link check catches it) - the distinct break the earlier reorder/delete tests skipped past.

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
