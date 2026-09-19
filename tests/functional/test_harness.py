"""The harness proves itself before anything is built on it."""
from __future__ import annotations

import json
from pathlib import Path

from dbqm.cli import run_cli


def test_the_fixture_registers_a_connection_that_really_answers(local_db, capsys):
    """No mocks. If this fails, every functional test after it is meaningless."""
    assert run_cli(["test", "local", "-f", "json"]) is True
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is True
    assert body["command"] == "test"


def test_the_seed_is_what_the_documents_describe(local_db, capsys):
    """Three clientes, four pedidos, one view -- the numbers every QA
    scenario in docs/qa/ counts on. Change the seed, change the documents."""
    assert run_cli(["sql", "SELECT COUNT(*) AS n FROM clientes", "local", "-f", "json"]) is True
    assert json.loads(capsys.readouterr().out)["data"]["rows"] == [[3]]
    assert run_cli(["sql", "SELECT COUNT(*) AS n FROM pedidos", "local", "-f", "json"]) is True
    assert json.loads(capsys.readouterr().out)["data"]["rows"] == [[4]]


def test_a_functional_test_cannot_patch_deps():
    """The rule, enforced by reading the folder. A functional test that
    patches `dbqm.cli.deps` is a unit test in the wrong directory: it would
    prove the mock, not the program."""
    folder = Path(__file__).parent
    source = "".join(p.read_text(encoding="utf-8") for p in folder.glob("*.py"))
    # The needle is assembled, not written: this file is in the folder it
    # reads, and a literal here would be the first thing it found.
    target = "dbqm.cli." + "deps"
    for quotes in ('"', "'"):
        assert f"patch({quotes}{target}" not in source
