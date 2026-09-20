"""`dbqm mcp` is a CLI command: parsed, described, and refused cleanly
without the extra. Runs without the `mcp` package installed."""
from __future__ import annotations

import json
import sys

import dbqm.mcp
from dbqm.cli import run_cli
from tests.functional.conftest import invoke


def test_describe_cli_lists_mcp_with_both_flags(tmp_config_dir, capsys):
    run_cli(["describe-cli", "-f", "json"])
    body = json.loads(capsys.readouterr().out)
    commands = {c["name"]: c for c in body["data"]["commands"]}
    flags = {a.get("flags", [None])[0] for a in commands["mcp"]["arguments"]}
    assert {"--allow-write", "--connection"} <= flags


def test_without_the_extra_it_fails_on_stderr_with_the_install_line(tmp_config_dir, capsys, monkeypatch):
    from dbqm.i18n import t
    monkeypatch.setitem(sys.modules, "dbqm.mcp.server", None)  # `import` raises ImportError
    # `from dbqm.mcp import server` reads the `server` attribute off the
    # already-imported `dbqm.mcp` package before it ever consults
    # `sys.modules["dbqm.mcp.server"]`; if an earlier test in this process
    # already imported the real submodule, the `None` entry above is never
    # seen. Removing the attribute here forces the lookup back to
    # `sys.modules`, where the `None` sentinel raises `ImportError`.
    monkeypatch.delattr(dbqm.mcp, "server", raising=False)
    code, out, err = invoke(["mcp"], capsys)
    assert code == 2
    assert out == ""
    body = json.loads(err)
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == t("mcp.not_installed")


def test_the_flags_reach_the_server(tmp_config_dir, capsys, monkeypatch):
    """The options object is built from argv and handed to `run`; the server
    itself is not started (a fake `run` records what it got)."""
    import types
    from dbqm.mcp.options import ServerOptions

    seen: list[ServerOptions] = []
    fake = types.ModuleType("dbqm.mcp.server")
    fake.run = seen.append  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "dbqm.mcp.server", fake)
    monkeypatch.delattr(dbqm.mcp, "server", raising=False)
    assert run_cli(["mcp", "--allow-write", "--connection", "a", "--connection", "b"]) is True
    assert seen == [ServerOptions(allow_write=True, connections=frozenset({"a", "b"}))]
    assert capsys.readouterr().out == ""
