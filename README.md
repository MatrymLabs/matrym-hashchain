# matrym-hashchain

[![PyPI](https://img.shields.io/pypi/v/matrym-hashchain)](https://pypi.org/project/matrym-hashchain/)
[![CI](https://github.com/MatrymLabs/matrym-hashchain/actions/workflows/ci.yml/badge.svg)](https://github.com/MatrymLabs/matrym-hashchain/actions/workflows/ci.yml)
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

## What it guarantees (and what it doesn't)

This proves **integrity**, honestly labelled:

| Attack | Detected? |
|---|---|
| A payload was edited | ✅ content-hash mismatch |
| Records were reordered or one was inserted | ✅ sequence / prior-hash mismatch |
| A *middle* record was deleted | ✅ the next record's prior-hash no longer links |
| The *last* record(s) were dropped | ❌ not by the chain alone - anchor the head hash elsewhere (a receipt, a second store) if truncation must be caught |
| Who wrote a record (authenticity) | ❌ integrity is not authenticity - sign the head hash (HMAC or a key) to prove authorship |

Any break **fails loud** with `HashChainError` rather than returning a dishonest history.

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

- `append(path, payload) -> Entry` - validate, hash-chain, and append one record. Verifies the
  chain *before* extending it, so you can't quietly append onto an already-tampered log.
- `read(path) -> list[Entry]` - read every record, verifying as it goes. Empty/missing store -> `[]`.
- `verify(path) -> bool` - `True` if the ledger reads clean end to end, `False` if broken.
- `content_hash(mapping) -> str` - the canonical SHA-256 (sorted keys, no whitespace) the chain uses.
- `Entry(seq, payload, prior_hash, content_hash)` - one link; `HashChainError` - the loud failure.

## Test

```bash
pip install -e ".[dev]"   # pytest, ruff, mypy
make check                # ruff + mypy + pytest (the full gate)
pytest -q                 # the suite on its own
```

The suite pins both **acceptance and refusal**: a clean chain reads end to end and `verify`
returns `True`, while every tampered case (an edited payload, a reorder, a deleted middle
record, an append onto an already-broken log) fails loud with `HashChainError` rather than
returning a dishonest history. CI runs it on every push.

## Provenance

This is a **MatrymLabs Hardware Store part**: a pattern first proven in the
[CodeForge](https://github.com/MatrymLabs/codeforge) MUD engine (the "Chronicle" - the game's
tamper-evident memory), then reused across the fleet (a federal guidance-check ledger; an AI-triage
decision audit trail). Published standalone so any project can reuse the same tested primitive -
*one well-made part, many jobs.*

## License

MIT
