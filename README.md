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

## API

- `append(path, payload) -> Entry` - validate, hash-chain, and append one record. Verifies the
  chain *before* extending it, so you can't quietly append onto an already-tampered log.
- `read(path) -> list[Entry]` - read every record, verifying as it goes. Empty/missing store -> `[]`.
- `verify(path) -> bool` - `True` if the ledger reads clean end to end, `False` if broken.
- `content_hash(mapping) -> str` - the canonical SHA-256 (sorted keys, no whitespace) the chain uses.
- `Entry(seq, payload, prior_hash, content_hash)` - one link; `HashChainError` - the loud failure.

## Provenance

This is a **MatrymLabs Hardware Store part**: a pattern first proven in the
[CodeForge](https://github.com/MatrymLabs/codeforge) MUD engine (the "Chronicle" - the game's
tamper-evident memory), then reused across the fleet (a federal guidance-check ledger; an AI-triage
decision audit trail). Published standalone so any project can reuse the same tested primitive -
*one well-made part, many jobs.*

## License

MIT
