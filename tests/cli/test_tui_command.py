"""`dbqm tui` is the interface with a name, and neither it nor a bare
`dbqm` may hang where there is no terminal."""
from __future__ import annotations

import json

import pytest

from dbqm.cli import COMMAND_MAP, refuse_without_a_terminal
from dbqm.i18n import t
from tests.functional.conftest import invoke


def test_tui_is_a_dispatched_command():
    assert "tui" in COMMAND_MAP


def test_it_refuses_a_non_terminal_stdin_instead_of_opening(tmp_config_dir, capsys, monkeypatch):
    """The failure mode this command exists to name: a fullscreen app on a
    pipe has nothing to read and nothing to draw on."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code, out, err = invoke(["tui"], capsys)
    assert code == 2
    assert out == ""
    assert json.loads(err)["error"]["code"] == "usage"


def test_it_opens_the_app_on_a_terminal(tmp_config_dir, capsys, monkeypatch):
    """Everything up to `DBQMApp().run()`, which is the TUI suite's job."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    opened: list[str] = []
    import dbqm.ui.app as app_module

    monkeypatch.setattr(app_module.DBQMApp, "run", lambda self, *a, **k: opened.append("ran"))
    from dbqm.cli import run_cli

    assert run_cli(["tui"]) is True
    assert opened == ["ran"]


def test_the_bare_invocation_refuses_a_pipe_with_the_help(tmp_config_dir, capsys, monkeypatch):
    """`dbqm` with no arguments used to hang until something killed it."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit) as caught:
        refuse_without_a_terminal()
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert t("tui.needs_a_terminal") in captured.err
    # The caller that lands here is usually a script: give it the commands.
    assert "run-group" in captured.err and "describe-cli" in captured.err
