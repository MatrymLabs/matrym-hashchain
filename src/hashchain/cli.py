"""A thin command line over the ledger: append, read, and verify from one terminal line.

    matrym-hashchain append audit.jsonl '{"event": "created", "who": "alice"}'
    matrym-hashchain read   audit.jsonl
    matrym-hashchain verify audit.jsonl   # exit 0 clean, exit 1 broken -- scriptable

Every command is a thin caller over the library's public functions; the CLI adds no integrity logic
of its own. A broken chain or a bad payload fails loud on stderr and returns a non-zero exit code,
so `verify` slots straight into a shell gate or CI step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import HashChainError, __version__, append, read


def _load_payload(text: str) -> dict[str, Any]:
    """Parse a JSON object from CLI text; reject anything that is not an object, loud."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HashChainError(f"payload is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HashChainError('payload must be a JSON object, e.g. \'{"event": "created"}\'')
    return parsed


def _cmd_append(args: argparse.Namespace) -> int:
    text = args.payload if args.payload is not None else sys.stdin.read()
    entry = append(args.ledger, _load_payload(text))
    print(f"appended seq {entry.seq}, head {entry.content_hash[:12]}")
    return 0


def _cmd_read(args: argparse.Namespace) -> int:
    entries = read(args.ledger)  # verifies the whole chain as it goes; raises if broken
    for entry in entries:
        if args.json:
            print(json.dumps({"seq": entry.seq, "payload": entry.payload}, sort_keys=True))
        else:
            print(f"{entry.seq}\t{json.dumps(entry.payload, sort_keys=True)}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    entries = read(args.ledger)  # the actual integrity check; the reason is in the exception
    head = entries[-1].content_hash[:12] if entries else "(empty)"
    print(f"clean: {len(entries)} record(s), head {head}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="matrym-hashchain",
        description="A tamper-evident, append-only, hash-chained ledger.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_append = sub.add_parser("append", help="append one JSON-object record to the ledger")
    p_append.add_argument("ledger", type=Path, help="path to the .jsonl ledger")
    p_append.add_argument(
        "payload", nargs="?", help="a JSON object; omit to read the object from stdin"
    )
    p_append.set_defaults(func=_cmd_append)

    p_read = sub.add_parser("read", help="print every record, verifying the chain as it goes")
    p_read.add_argument("ledger", type=Path, help="path to the .jsonl ledger")
    p_read.add_argument("--json", action="store_true", help="emit each record as a JSON object")
    p_read.set_defaults(func=_cmd_read)

    p_verify = sub.add_parser("verify", help="check the whole chain; exit 0 clean, 1 broken")
    p_verify.add_argument("ledger", type=Path, help="path to the .jsonl ledger")
    p_verify.set_defaults(func=_cmd_verify)

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
