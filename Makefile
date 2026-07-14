.PHONY: env fix lint typecheck test check

env:
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

check: lint typecheck test
