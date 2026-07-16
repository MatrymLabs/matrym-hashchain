"""Enable `python -m hashchain ...`, delegating to the same CLI as the `matrym-hashchain` script."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
