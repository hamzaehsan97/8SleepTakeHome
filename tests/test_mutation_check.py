"""The mutation tool's own logic, with the pytest subprocess stubbed out.

The tool is never actually run here: no real pytest process starts and no file
is mutated. What is checked is how it classifies a layer's result, because
counting a crash as "caught" would make a broken run look like a perfect score.
"""

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "mutation_check.py"


@pytest.fixture
def tool():
    spec = importlib.util.spec_from_file_location("mutation_check_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stub_exit_code(monkeypatch, tool, code):
    monkeypatch.setattr(
        tool.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=code)
    )


def test_exit_code_1_is_caught(monkeypatch, tool):
    stub_exit_code(monkeypatch, tool, 1)
    assert tool.run_layer(Path("."), []) == tool.FAILED


def test_exit_code_0_is_a_survivor(monkeypatch, tool):
    stub_exit_code(monkeypatch, tool, 0)
    assert tool.run_layer(Path("."), []) == tool.PASSED


@pytest.mark.parametrize("code", [2, 5])
def test_collection_error_and_nothing_collected_are_errors_not_caught(monkeypatch, tool, code):
    stub_exit_code(monkeypatch, tool, code)
    assert tool.run_layer(Path("."), []) == tool.ERROR


def test_timeout_is_an_error_not_caught(monkeypatch, tool):
    def hang(*a, **k):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=300)

    monkeypatch.setattr(tool.subprocess, "run", hang)
    assert tool.run_layer(Path("."), []) == tool.ERROR


def test_failing_baseline_stops_the_run_before_any_mutant(monkeypatch, tool, capsys):
    stub_exit_code(monkeypatch, tool, 1)  # unmutated code fails its own tests

    def must_not_run(*a, **k):
        raise AssertionError("a mutant was checked despite a failing baseline")

    monkeypatch.setattr(tool, "check", must_not_run)
    assert tool.main() == 2
    assert "baseline" in capsys.readouterr().out


def test_errored_mutant_is_reported_separately_and_not_counted_as_caught(
    monkeypatch, tool, capsys
):
    stub_exit_code(monkeypatch, tool, 0)  # baseline passes
    monkeypatch.setattr(tool, "MUTANTS", [("broken", "", ""), ("good", "", "")])
    outcomes = {
        "broken": (tool.ERROR, tool.ERROR),
        "good": (tool.FAILED, tool.PASSED),
    }
    monkeypatch.setattr(tool, "check", lambda i, m: (m[0], *outcomes[m[0]]))

    assert tool.main() == 3
    out = capsys.readouterr().out
    assert "1/2 caught" in out
    assert "error: broken" in out


def test_survivor_gives_exit_code_1(monkeypatch, tool):
    stub_exit_code(monkeypatch, tool, 0)
    monkeypatch.setattr(tool, "MUTANTS", [("alive", "", "")])
    monkeypatch.setattr(tool, "check", lambda i, m: (m[0], tool.PASSED, tool.PASSED))
    assert tool.main() == 1
