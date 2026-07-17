# matrym-hashchain

[![PyPI](https://img.shields.io/pypi/v/matrym-hashchain)](https://pypi.org/project/matrym-hashchain/)
[![CI](https://github.com/MatrymLabs/matrym-hashchain/actions/workflows/ci.yml/badge.svg)](https://github.com/MatrymLabs/matrym-hashchain/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/MatrymLabs/matrym-hashchain/branch/main/graph/badge.svg)](https://codecov.io/gh/MatrymLabs/matrym-hashchain)
[![Python](https://img.shields.io/pypi/pyversions/matrym-hashchain)](https://pypi.org/project/matrym-hashchain/)
![License](https://img.shields.io/badge/license-MIT-green)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

**A tamper-evident, append-only, hash-chained ledger. Dependency-free (stdlib only).**

Each entry carries a SHA-256 over its own payload **and** the previous entry's hash, so any later
edit, reorder, or deletion of a *past* record is detected the next time the log is read. It's a
file-simple, zero-dependency primitive for **audit trails, transaction logs, and chain-of-custody
records** - the kind of thing a compliance, finance, or records system needs and shouldn't hand-roll.

## Install

```bash
pip install matrym-hashchain
```

Released to PyPI via [trusted publishing](RELEASING.md) (GitHub OIDC, no stored token).

## Use

```python
from pathlib import Path
from hashchain import append, read, verify, HashChainError

ledger = Path("audit.jsonl")

append(ledger, {"event": "created", "who": "alice"})
append(ledger, {"event": "approved", "who": "bob"})

for entry in read(ledger):          # read() verifies the whole chain as it goes
    print(entry.seq, entry.payload)

verify(ledger)                      # True -- the history reads clean end to end

# If anyone edits, reorders, or deletes a past record...
ledger.write_text(ledger.read_text().replace("alice", "mallory"))
verify(ledger)                      # False
read(ledger)                        # raises HashChainError: record 0 was tampered ...
```

The store is plain JSON Lines (`.jsonl`) - one record per line, human-readable, greppable, and
portable. No database, no daemon, no dependencies.

## Command line

The same three verbs, from one terminal line (installed as `matrym-hashchain`, or run
`python -m hashchain`):

```bash
matrym-hashchain append audit.jsonl '{"event": "created", "who": "alice"}'
matrym-hashchain append audit.jsonl '{"event": "approved", "who": "bob"}'
matrym-hashchain read   audit.jsonl        # 0<TAB>{"event": "created", ...}
matrym-hashchain verify audit.jsonl        # "clean: 2 record(s), head e7c1f28a3595"; exit 0
```

`verify` exits **0 on a clean chain and 1 on a broken one**, naming the tampered record on stderr,
so it drops straight into a shell gate or a CI step. `append` also reads the payload object from
stdin when you omit it (`... | matrym-hashchain append audit.jsonl`).

Signing and truncation work from the CLI too. The HMAC key is read from an **environment variable**
(never the command line, so it can't leak into the process table or shell history):

```bash
export LEDGER_KEY='a secret only writers hold'
matrym-hashchain append audit.jsonl '{"event": "created"}' --key-env LEDGER_KEY
matrym-hashchain verify audit.jsonl --key-env LEDGER_KEY          # exit 0; without it -> exit 1

anchor=$(matrym-hashchain head audit.jsonl --key-env LEDGER_KEY)  # stash off-ledger
matrym-hashchain verify audit.jsonl --key-env LEDGER_KEY --expected-head "$anchor"  # catches a dropped tail
```

## What it guarantees (and what it doesn't)

This proves **integrity** by default, and closes the two classic gaps with two optional features:

| Attack | Detected? |
|---|---|
| A payload was edited | ✅ content-hash mismatch |
| Records were reordered or one was inserted | ✅ sequence / prior-hash mismatch |
| A *middle* record was deleted | ✅ the next record's prior-hash no longer links |
| The *last* record(s) were dropped | ✅ *with an anchor* - stash `head_hash(path)` elsewhere (a receipt, a second store, a witness) and check `verify(path, expected_head=...)`; the chain alone can't see truncation |
| Who wrote a record (authenticity) | ✅ *with a signing key* - pass `key=...` to sign records with HMAC-SHA256; only a key-holder can produce or validate them |

Any break **fails loud** with `HashChainError` rather than returning a dishonest history.

### Signing and truncation, honestly

```python
KEY = b"a secret only writers hold"
append(ledger, {"event": "created"}, key=KEY)   # HMAC-signed
verify(ledger, key=KEY)                          # True; verify(ledger) alone -> False (no key)

anchor = head_hash(ledger, key=KEY)              # stash this off-ledger
# ... later, after someone drops the last record ...
verify(ledger, key=KEY, expected_head=anchor)    # False -- the tail is gone
```

Honest label: HMAC is a **symmetric shared-secret MAC**. It proves a record was written by a holder
of the key; it is **not** public-key non-repudiation (anyone with the key can both sign and verify).
The same key must be passed to every `append`/`read`/`verify`/`head_hash` over a signed ledger.

One more honest bound: this is a **single-writer** primitive. `append` is not guarded against two
processes writing the same ledger at once (no file lock), so concurrent appends can interleave.
Serialize writers (one process, or your own lock) if that's a risk; `read`/`verify` are read-only
and safe alongside a single writer.

## Performance

`append` is **O(1) in ledger size**: it reads only the ledger's tail (a backward seek), not the
whole chain, so appends stay fast as the log grows without bound. That claim ships with evidence,
not just an assertion, measured head to head against the pre-0.1.1 O(n) behavior:

| ledger size | O(n) baseline | O(1) current | speedup |
|---:|---:|---:|---:|
| 500 | 6.25 ms | 0.08 ms | 83x |
| 16,000 | 229.13 ms | 0.08 ms | 3,011x |

Across a 32x ledger growth the old append slowed **36.6x** (linear); the current one stayed **flat**.
Full method, table, and reproduction: [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md) (`make bench`).

## API

All functions take an optional keyword-only `key: bytes` (sign/verify with HMAC; omit for plain
integrity).

- `append(path, payload, *, key=None) -> Entry` - validate, hash-chain, and append one record.
  Reads only the tail (O(1)), validating that record before extending, so you can't quietly append
  onto a tampered tail.
- `read(path, *, key=None) -> list[Entry]` - read every record, verifying as it goes. Empty/missing
  store -> `[]`.
- `verify(path, *, key=None, expected_head=None) -> bool` - `True` if the ledger reads clean end to
  end; pass `expected_head` to also catch truncation.
- `head_hash(path, *, key=None) -> str` - the last record's content hash (or `GENESIS` if empty);
  the value you anchor off-ledger to detect truncation.
- `content_hash(mapping, *, key=None) -> str` - the canonical digest the chain uses: SHA-256
  unkeyed, HMAC-SHA256 when a `key` is given (sorted keys, no whitespace).
- `Entry(seq, payload, prior_hash, content_hash)` - one link; `HashChainError` - the loud failure.

## Test

```bash
pip install -e ".[dev]"   # pytest, ruff, mypy, coverage, bandit, pip-audit
make check                # ruff + mypy --strict + pytest at 100% coverage (the full gate)
make security             # bandit SAST + pip-audit the dependency closure (proves "zero deps")
make bench                # the O(1)-append benchmark
```

The suite pins both **acceptance and refusal**: a clean chain reads end to end and `verify`
returns `True`, while every tampered case (an edited payload, a reorder, a deleted middle
record, a mislinked record with a valid own hash, an append onto an already-broken log) fails
loud with `HashChainError` rather than returning a dishonest history. CI runs it on every push
across Python 3.10-3.13, at **100% line + branch coverage**, and audits the dependency closure.

## Evaluation

Scored by [`forge-audit`](https://github.com/MatrymLabs/forge-audit) - the fleet's proof-tool, which
runs the gates on a target repo behind a mockable GitHub-API seam and emits a `pass|watchlist|fail`
scorecard. This part passes at the **advanced** stage (a snapshot; reproduce with
`forge-audit --path . --stage advanced --online`):

| Dimension | Verdict | Evidence |
|---|---|---|
| lint | ✅ pass | clean |
| typecheck | ✅ pass | clean |
| tests | ✅ pass | green suite, coverage 100% ≥ 85% |
| security | ✅ pass | bandit + pip-audit clean |
| dependencies | ✅ pass | clean |
| ci | ✅ pass | 3 CI workflows (check, release, CodeQL) |
| collaboration | ✅ pass | 9 merged PRs |
| performance | ✅ pass | benchmark artifact present |
| readme | ✅ pass | covers purpose, install, run, test |

**Overall: `pass`** (advanced). Role signals: testing, security, backend, devops, collaboration,
performance, documentation.

## Provenance

This is a **MatrymLabs Hardware Store part**: a pattern first proven in the
[CodeForge](https://github.com/MatrymLabs/codeforge) MUD engine (the "Chronicle" - the game's
tamper-evident memory), then reused across the fleet (a federal guidance-check ledger; an AI-triage
decision audit trail). Published standalone so any project can reuse the same tested primitive -
*one well-made part, many jobs.*

## License

MIT
