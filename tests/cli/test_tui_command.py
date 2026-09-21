"""`dbqm tui` is the interface with a name, and neither it nor a bare
`dbqm` may hang where there is no terminal."""
from __future__ import annotations

import json
import os
from pathlib import Path

from dbqm.cli import COMMAND_MAP
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
    pipe has nothing to read and nothing to draw on.

    The message is the command-path one, not the bare-invocation one: the
    user just ran `dbqm tui` themselves, so "use a command below" would
    read circularly -- there is no list below a JSON envelope.
    """
    monkeypatch.setattr("dbqm.cli.commands.tui_cmd.has_a_console", lambda: False)
    code, out, err = invoke(["tui"], capsys)
    assert code == 2
    assert out == ""
    error = json.loads(err)["error"]
    assert error["code"] == "usage"
    assert error["message"] == t("tui.needs_a_terminal_here")


def test_it_opens_the_app_on_a_terminal(tmp_config_dir, capsys, monkeypatch):
    """Everything up to `DBQMApp().run()`, which is the TUI suite's job."""
    monkeypatch.setattr("dbqm.cli.commands.tui_cmd.has_a_console", lambda: True)
    opened: list[str] = []
    import dbqm.ui.app as app_module

    monkeypatch.setattr(app_module.DBQMApp, "run", lambda self, *a, **k: opened.append("ran"))
    from dbqm.cli import run_cli

    assert run_cli(["tui"]) is True
    assert opened == ["ran"]


def test_the_bare_invocation_prints_the_help(tmp_config_dir, capsys):
    """Since 3.0.0 `dbqm` with no arguments is the help, not the interface.

    On stdout and exit 0: it is what the maintainer asked the default to
    be, not a usage error. The notice at the top of that help is what
    tells someone who has typed `dbqm` for years where the interface went.
    """
    from dbqm.cli import print_the_help
    from dbqm.i18n import t

    print_the_help()
    captured = capsys.readouterr()
    assert captured.err == ""
    assert t("cli.tui_moved").splitlines()[0] in captured.out
    assert "run-group" in captured.out and "describe-cli" in captured.out


def test_the_bare_invocation_does_not_need_a_terminal(tmp_config_dir, capsys, monkeypatch):
    """The hazard the 2.14.0 refusal existed for is gone rather than
    handled: printing the help needs no console, so there is nothing left
    to refuse and no way to hang."""
    from dbqm.cli import print_the_help

    monkeypatch.setattr("dbqm.cli.terminal.has_a_console", lambda: False)
    print_the_help()
    assert capsys.readouterr().out != ""
