"""A thin command line over the ledger: append, read, verify, and head from one terminal line.

    matrym-hashchain append audit.jsonl '{"event": "created", "who": "alice"}'
    matrym-hashchain read   audit.jsonl
    matrym-hashchain verify audit.jsonl   # exit 0 clean, exit 1 broken -- scriptable
    matrym-hashchain head   audit.jsonl   # the head hash, to anchor against truncation

Every command is a thin caller over the library's public functions; the CLI adds no integrity logic
of its own. A broken chain or a bad payload fails loud on stderr and returns a non-zero exit code,
so `verify` slots straight into a shell gate or CI step.

Signing: pass `--key-env VAR` to sign/verify a ledger with the HMAC key held in environment variable
VAR. The key is read from the environment, never taken on the command line, so it does not leak into
the process table or shell history.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import GENESIS, HashChainError, __version__, append, head_hash, read


def _load_payload(text: str) -> dict[str, Any]:
    """Parse a JSON object from CLI text; reject anything that is not an object, loud."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HashChainError(f"payload is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HashChainError('payload must be a JSON object, e.g. \'{"event": "created"}\'')
    return parsed


def _key_from_env(var: str | None) -> bytes | None:
    """Read an HMAC signing key from environment variable `var` (never from argv). None if unset
    via `--key-env`; a loud error if the named variable is missing or empty."""
    if var is None:
        return None
    value = os.environ.get(var)
    if not value:
        raise HashChainError(f"env var {var!r} is unset or empty; expected an HMAC signing key")
    return value.encode("utf-8")


def _cmd_append(args: argparse.Namespace) -> int:
    text = args.payload if args.payload is not None else sys.stdin.read()
    entry = append(args.ledger, _load_payload(text), key=_key_from_env(args.key_env))
    print(f"appended seq {entry.seq}, head {entry.content_hash[:12]}")
    return 0


def _cmd_read(args: argparse.Namespace) -> int:
    entries = read(args.ledger, key=_key_from_env(args.key_env))  # verifies as it goes; raises
    for entry in entries:
        if args.json:
            print(json.dumps({"seq": entry.seq, "payload": entry.payload}, sort_keys=True))
        else:
            print(f"{entry.seq}\t{json.dumps(entry.payload, sort_keys=True)}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    key = _key_from_env(args.key_env)
    entries = read(args.ledger, key=key)  # the integrity check; the reason is in the exception
    head = entries[-1].content_hash if entries else GENESIS
    if args.expected_head is not None and head != args.expected_head:
        raise HashChainError(
            f"head mismatch (truncation?): ledger head "
            f"{head[:12] if head else '(empty)'} != expected {args.expected_head[:12]}"
        )
    print(f"clean: {len(entries)} record(s), head {head[:12] if head else '(empty)'}")
    return 0


def _cmd_head(args: argparse.Namespace) -> int:
    print(head_hash(args.ledger, key=_key_from_env(args.key_env)))  # raw hash, for `$(...)` capture
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="matrym-hashchain",
        description="A tamper-evident, append-only, hash-chained ledger.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # Shared by every command: read an HMAC key from an env var, never from the command line.
    signed = argparse.ArgumentParser(add_help=False)
    signed.add_argument(
        "--key-env",
        metavar="VAR",
        help="read the HMAC signing key from this environment variable (not passed on the CLI)",
    )

    p_append = sub.add_parser(
        "append", parents=[signed], help="append one JSON-object record to the ledger"
    )
    p_append.add_argument("ledger", type=Path, help="path to the .jsonl ledger")
    p_append.add_argument(
        "payload", nargs="?", help="a JSON object; omit to read the object from stdin"
    )
    p_append.set_defaults(func=_cmd_append)

    p_read = sub.add_parser(
        "read", parents=[signed], help="print every record, verifying the chain as it goes"
    )
    p_read.add_argument("ledger", type=Path, help="path to the .jsonl ledger")
    p_read.add_argument("--json", action="store_true", help="emit each record as a JSON object")
    p_read.set_defaults(func=_cmd_read)

    p_verify = sub.add_parser(
        "verify", parents=[signed], help="check the whole chain; exit 0 clean, 1 broken"
    )
    p_verify.add_argument("ledger", type=Path, help="path to the .jsonl ledger")
    p_verify.add_argument(
        "--expected-head",
        metavar="HASH",
        help="also require the ledger to end at this head hash (catches truncation)",
    )
    p_verify.set_defaults(func=_cmd_verify)

    p_head = sub.add_parser(
        "head", parents=[signed], help="print the head hash, to anchor against truncation"
    )
    p_head.add_argument("ledger", type=Path, help="path to the .jsonl ledger")
    p_head.set_defaults(func=_cmd_head)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse args and dispatch. Returns a process exit code; never raises HashChainError outward."""
    args = _build_parser().parse_args(argv)
    try:
        exit_code: int = args.func(args)
        return exit_code
    except HashChainError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
