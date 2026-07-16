.PHONY: hooks env fix lint typecheck test bench check

env: hooks
	python -m venv .venv && .venv/bin/pip install -e '.[dev]'

fix:
	ruff format .
	ruff check . --fix

lint:
	ruff format --check .
	ruff check .

typecheck:
	mypy

test:
	pytest -q

bench:
	python benchmarks/bench_append.py

check: lint typecheck test

hooks:
	git config core.hooksPath scripts/hooks
	@echo "✓ git hooks active (scripts/hooks) - commits on main are refused"
