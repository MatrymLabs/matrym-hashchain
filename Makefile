.PHONY: hooks env fix lint typecheck test coverage security bench check

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

coverage:
	pytest --cov --cov-report=term-missing --cov-report=xml --cov-fail-under=100

security:
	bandit -q -c pyproject.toml -r src   # SAST over the shipped library
	pip-audit .                          # audit THIS project's dependency closure, not the ambient venv

bench:
	python benchmarks/bench_append.py

check: lint typecheck coverage

hooks:
	git config core.hooksPath scripts/hooks
	@echo "✓ git hooks active (scripts/hooks) - commits on main are refused"
