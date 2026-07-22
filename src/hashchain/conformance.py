"""Conformance vectors: the canonical (payload -> chain hash) fixtures that DEFINE the
matrym-hashchain wire format.

Any independent hash-chain implementation that produces these exact `content_hash` values for
these payloads, appended in order from GENESIS (unkeyed), is byte-compatible with this package.
The MatrymLabs fleet's *harvested* ledgers (re-implemented, not imported, per ADR 0002) each carry
a test that asserts they reproduce these hashes - so "harvest is faithful reuse" is a pinned,
tested invariant, not a one-time measurement, and no consumer takes a runtime dependency.

Frozen literals: `CONFORMANCE_HASHES` was captured from this package's own `append()`. If a change
to the digest ever alters them, `tests/test_conformance.py` fails loud - a wire-format change is
then a deliberate, versioned break, never a silent drift.
"""

from __future__ import annotations

from typing import Any

# Canonical payloads, in order. Chosen to exercise the format's determinism: sorted keys on a
# nested dict, a list, and null / bool / int values.
CONFORMANCE_PAYLOADS: list[dict[str, Any]] = [
    {"event": "opened", "actor": "system", "n": 1},
    {"event": "changed", "ok": True, "note": None, "tags": ["a", "b"]},
    {"nested": {"z": 1, "a": {"deep": [3, 2, 1]}}},
]

# The content_hash each payload produces, appended in order from GENESIS, unkeyed. The
# authoritative spec of the wire format (sha256 over a compact, key-sorted
# {"seq","payload","prior_hash"}).
CONFORMANCE_HASHES: list[str] = [
    "706e4edc753bf4870819dfbfaafe5bdf56da93faba6191f3b25957b2e5f4cf4b",
    "7ad9a790b05596f82471d8467dfb0821da0cd491f0866fa6a2b1cc2e06914823",
    "f378cfaa478e0a2fae17ed494fb8a7d9a633eb6ba6575006e7cc584d8977db2c",
]

# The head (last content_hash) of the canonical chain.
CONFORMANCE_HEAD: str = CONFORMANCE_HASHES[-1]


def expected_chain() -> list[tuple[dict[str, Any], str]]:
    """The canonical (payload, expected content_hash) pairs, in order - the conformance suite a
    faithful re-implementation must reproduce."""
    return list(zip(CONFORMANCE_PAYLOADS, CONFORMANCE_HASHES, strict=True))
