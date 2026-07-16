"""Test twin for the CLI -- the thin command line over the ledger.

Acceptance: append writes a real chained record; read prints records in order and `--json` emits
objects; verify reports a clean chain and exits 0; a payload can arrive on stdin. Refusal (the point
of a tamper-evident tool): verify and read on a tampered chain exit non-zero and name the break on
stderr; a non-object or unparseable payload is refused before it ever reaches disk. Every test uses
tmp_path; none touches real state.
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

from hashchain import HashChainError, append, read
from hashchain.cli import main


def _ledger(root: Path) -> Path:
    return root / "chain.jsonl"


# --- acceptance --------------------------------------------------------------------------------


def test_append_writes_a_real_chained_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _ledger(tmp_path)
    assert main(["append", str(p), '{"event": "created", "who": "alice"}']) == 0
    out = capsys.readouterr().out
    assert out.startswith("appended seq 0, head ")
    # the CLI wrote a genuine record the library reads back
    entries = read(p)
    assert entries[0].payload == {"event": "created", "who": "alice"}


def test_read_prints_records_in_order(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = _ledger(tmp_path)
    append(p, {"n": 1})
    append(p, {"n": 2})
    assert main(["read", str(p)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ['0\t{"n": 1}', '1\t{"n": 2}']


def test_read_json_flag_emits_objects(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = _ledger(tmp_path)
    append(p, {"n": 1})
    assert main(["read", str(p), "--json"]) == 0
    assert capsys.readouterr().out.splitlines() == ['{"payload": {"n": 1}, "seq": 0}']


def test_verify_reports_clean_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _ledger(tmp_path)
    append(p, {"n": 1})
    assert main(["verify", str(p)]) == 0
    assert "clean: 1 record(s)" in capsys.readouterr().out


def test_verify_on_empty_store_is_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["verify", str(_ledger(tmp_path))]) == 0
    assert "clean: 0 record(s), head (empty)" in capsys.readouterr().out


def test_append_reads_payload_from_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _ledger(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO('{"from": "stdin"}'))
    assert main(["append", str(p)]) == 0  # payload omitted -> read stdin
    assert read(p)[0].payload == {"from": "stdin"}


# --- refusal / hostile -------------------------------------------------------------------------


def test_verify_on_a_tampered_chain_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _ledger(tmp_path)
    append(p, {"amount": 100})
    p.write_text(p.read_text().replace("100", "999"), encoding="utf-8")
    assert main(["verify", str(p)]) == 1
    assert "tampered" in capsys.readouterr().err


def test_read_on_a_tampered_chain_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _ledger(tmp_path)
    append(p, {"amount": 100})
    p.write_text(p.read_text().replace("100", "999"), encoding="utf-8")
    assert main(["read", str(p)]) == 1
    assert "error:" in capsys.readouterr().err


def test_a_non_object_payload_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _ledger(tmp_path)
    assert main(["append", str(p), '["not", "an", "object"]']) == 1
    assert "must be a JSON object" in capsys.readouterr().err
    assert read(p) == []  # nothing reached disk


def test_an_unparseable_payload_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _ledger(tmp_path)
    assert main(["append", str(p), "{not valid json}"]) == 1
    assert "not valid JSON" in capsys.readouterr().err
    assert read(p) == []


def test_main_never_leaks_a_hashchainerror(tmp_path: Path) -> None:
    """The CLI must translate a failure to an exit code, never raise out as a traceback."""
    p = _ledger(tmp_path)
    append(p, {"n": 1})
    p.write_text(p.read_text().replace('"n": 1', '"n": 2'), encoding="utf-8")
    try:
        assert main(["read", str(p)]) == 1  # returns, does not raise
    except HashChainError:  # pragma: no cover - this is the failure the test guards against
        pytest.fail("CLI leaked HashChainError instead of returning an exit code")


def test_version_flag_exits_clean(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0


def test_python_dash_m_entry_point_runs(tmp_path: Path) -> None:
    """`python -m hashchain ...` must reach the same CLI. Prove it two ways: the module wires the
    same `main`, and it actually runs as a real subprocess."""
    import hashchain.__main__ as dunder_main

    assert getattr(dunder_main, "main") is main  # noqa: B009  # the -m entry delegates to the CLI

    p = _ledger(tmp_path)
    append(p, {"n": 1})
    result = subprocess.run(
        [sys.executable, "-m", "hashchain", "verify", str(p)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "clean: 1 record(s)" in result.stdout
