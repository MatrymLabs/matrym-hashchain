"""The package IS the spec: its own append() must reproduce the frozen conformance vectors.

If this breaks, the wire format changed - update hashchain/conformance.py deliberately (a versioned
break), and every fleet consumer's conformance test will flag the same, so nothing drifts silently.
"""

from pathlib import Path

from hashchain import append, head_hash, read
from hashchain.conformance import (
    CONFORMANCE_HASHES,
    CONFORMANCE_HEAD,
    CONFORMANCE_PAYLOADS,
    expected_chain,
)


def test_append_reproduces_the_frozen_conformance_vectors(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl"
    for payload in CONFORMANCE_PAYLOADS:
        append(path, payload)
    got = [entry.content_hash for entry in read(path)]
    assert got == CONFORMANCE_HASHES
    assert head_hash(path) == CONFORMANCE_HEAD


def test_expected_chain_pairs_payloads_with_hashes() -> None:
    pairs = expected_chain()
    assert len(pairs) == len(CONFORMANCE_PAYLOADS)
    assert pairs[0] == (CONFORMANCE_PAYLOADS[0], CONFORMANCE_HASHES[0])
