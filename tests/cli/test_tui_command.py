"""`dbqm tui` is the interface with a name, and neither it nor a bare
`dbqm` may hang where there is no terminal."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dbqm.cli import COMMAND_MAP, refuse_without_a_terminal
from dbqm.cli.terminal import has_a_console
from dbqm.i18n import t
from tests.functional.conftest import invoke


def test_tui_is_a_dispatched_command():
    assert "tui" in COMMAND_MAP


# --- has_a_console: the real check, not the abstraction that stands in for
# it in the command/bare-invocation tests below. `isatty()` alone says True
# for `NUL` on Windows -- a character device, not a console -- which is the
# defect this module exists to close.


def test_has_a_console_is_false_for_a_real_devnull_stdin(monkeypatch):
    """`dbqm < NUL` on Windows: `isatty()` on a devnull handle answers True,
    but there is no console behind it."""
    devnull = Path(os.devnull).open()
    try:
        monkeypatch.setattr("sys.stdin", devnull)
        assert has_a_console() is False
    finally:
        devnull.close()


def test_has_a_console_is_false_for_a_pipe_like_stdin(monkeypatch):
    """A pipe already answers `isatty()` correctly; the console check must
    not regress that case."""
    class _Pipe:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr("sys.stdin", _Pipe())
    assert has_a_console() is False


def test_it_refuses_a_non_terminal_stdin_instead_of_opening(tmp_config_dir, capsys, monkeypatch):
    """The failure mode this command exists to name: a fullscreen app on a
    pipe has nothing to read and nothing to draw on."""
    monkeypatch.setattr("dbqm.cli.commands.tui_cmd.has_a_console", lambda: False)
    code, out, err = invoke(["tui"], capsys)
    assert code == 2
    assert out == ""
    assert json.loads(err)["error"]["code"] == "usage"


def test_it_opens_the_app_on_a_terminal(tmp_config_dir, capsys, monkeypatch):
    """Everything up to `DBQMApp().run()`, which is the TUI suite's job."""
    monkeypatch.setattr("dbqm.cli.commands.tui_cmd.has_a_console", lambda: True)
    opened: list[str] = []
    import dbqm.ui.app as app_module

    monkeypatch.setattr(app_module.DBQMApp, "run", lambda self, *a, **k: opened.append("ran"))
    from dbqm.cli import run_cli

    assert run_cli(["tui"]) is True
    assert opened == ["ran"]


def test_the_bare_invocation_refuses_a_pipe_with_the_help(tmp_config_dir, capsys, monkeypatch):
    """`dbqm` with no arguments used to hang until something killed it."""
    with pytest.raises(SystemExit) as caught:
        refuse_without_a_terminal()
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert t("tui.needs_a_terminal") in captured.err
    # The caller that lands here is usually a script: give it the commands.
    assert "run-group" in captured.err and "describe-cli" in captured.err
