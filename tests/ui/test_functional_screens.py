"""The first UI tests that execute rather than render.

Three pilots, one per execution screen, against the seeded SQLite file
from `tests/functional/conftest.py`: the worker runs the real engine and
the widget is read afterwards. Nothing is patched -- the same rule as
`tests/functional/`, enforced there by reading the folder; here by the
absence of `monkeypatch` and `patch` in this file.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import ComposeResult
from textual.widgets import Select, Static, TextArea

from dbqm.core import paths
from dbqm.models.connection import Connection, find_connection
from dbqm.models.group import find_group
from dbqm.models.query import find_query
from dbqm.ui.screens.adhoc import AdhocScreen
from dbqm.ui.screens.browser import BrowserScreen
from dbqm.ui.screens.group_run import GroupRunScreen
from dbqm.ui.screens.query_exec import QueryExecScreen
from dbqm.ui.widgets.group_result import GroupResultWidget
from dbqm.ui.widgets.result_table import ResultTable
from tests.functional.conftest import (  # noqa: F401 -- the fixtures are re-exported for this folder
    envelope,
    local2_db,
    local_db,
)
from tests.ui._helpers import ThemedTestApp

ATIVOS = "SELECT id, nome FROM clientes WHERE status = 'A' ORDER BY id"
PED = "SELECT id, valor FROM pedidos ORDER BY id"


class QueryExecTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield QueryExecScreen()


class AdhocTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield AdhocScreen()


class GroupRunTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield GroupRunScreen()


class BrowserTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield BrowserScreen()


def _notifications(app) -> list[str]:
    return [n.message for n in app._notifications]


@pytest.mark.asyncio
async def test_query_exec_runs_a_saved_query_and_shows_the_row_count(local_db, capsys):
    """`query_exec`: pick the saved query, let the worker run it for real,
    read `#result-info` -- "2 rows" comes from the database."""
    code, _ = envelope(["query", "add", "ativos", "--connection", "local", "--sql", ATIVOS, "-f", "json"], capsys)
    assert code == 0
    query = find_query("ativos")
    conn = find_connection("local")
    assert query is not None and conn is not None

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        worker = screen._run_query(query, conn, {})
        await worker.wait()
        await pilot.pause()

        assert screen.query_one("#results-phase").display is True
        info = str(screen.query_one("#result-info", Static).content)
        assert "ativos" in info and "local" in info
        assert "2 rows" in info
        table = screen.query_one("#result-table", ResultTable)
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_adhoc_executes_a_select_and_shows_the_rows(local_db):
    """`adhoc`: choose the connection in the select, type the SQL, press
    Executar. The button path is the one a person uses."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen.query_one("#adhoc-conn-select", Select).value = "local"
        screen.query_one("#adhoc-sql-area", TextArea).text = "SELECT id, nome FROM clientes ORDER BY id"
        await pilot.pause()
        screen._handle_execute()
        await app.workers.wait_for_complete()
        await pilot.pause()

        info = str(screen.query_one("#adhoc-result-info", Static).content)
        assert "local" in info
        assert "3 rows" in info
        table = screen.query_one("#res-table", ResultTable)
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_group_run_runs_a_group_and_shows_the_verdict(local2_db, capsys):
    """`group_run`: the group over `local` and `local2` -- which differ in
    one pedido -- is run for real and the widget says DIVERGENTE."""
    for nome, conn in (("ped_local", "local"), ("ped_local2", "local2")):
        code, _ = envelope(["query", "add", nome, "--connection", conn, "--sql", PED, "-f", "json"], capsys)
        assert code == 0
    code, _ = envelope(
        ["group", "add", "pedidos", "--query", "ped_local", "--query", "ped_local2",
         "--join-key", "id", "--compare-column", "valor", "-f", "json"],
        capsys,
    )
    assert code == 0
    group = find_group("pedidos")
    assert group is not None

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        worker = screen._run_group(group, {})
        await worker.wait()
        await pilot.pause()

        assert screen.query_one("#gr-results-phase").display is True
        info = str(screen.query_one("#gr-result-info", Static).content)
        assert "pedidos" in info and "2 queries" in info
        assert "DIVERGENT" in info
        gr = screen.query_one("#gr-group-result", GroupResultWidget).group_result
        assert gr is not None and gr.all_match is False
        assert [c.column for c in gr.comparisons] == ["valor"]
        assert gr.comparisons[0].diff_count == 1


@pytest.mark.asyncio
async def test_browser_extracts_sqlite_ddl_through_the_core_dispatch(local_db):
    """`browser`: the DDL worker on a SQLite connection saves the CREATE
    TABLE under exports/ddl. The screen used to route engines itself and
    refused SQLite as unsupported."""
    conn = find_connection("local")
    assert conn is not None
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        worker = screen._run_ddl(conn, "clientes")
        await worker.wait()
        await pilot.pause()

        avisos = _notifications(app)
        assert any(a.startswith("DDL saved") for a in avisos), avisos
    arquivos = list((Path(paths.EXPORTS_DIR) / "ddl").rglob("*.sql"))
    assert arquivos, "no .sql under exports/ddl"
    assert "CREATE TABLE clientes" in "".join(a.read_text(encoding="utf-8") for a in arquivos)


@pytest.mark.asyncio
async def test_browser_tells_sql_server_it_has_no_extractor(tmp_config_dir):
    """The one engine without an extractor is told so by core's message --
    not handed to the MySQL extractor, as the screen's own routing once
    did. No connection is opened: the refusal comes before the driver."""
    conn = Connection(name="ms", db_type="sqlserver", user="u", password="p",
                      host="h", port=1433, database="d")
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        worker = screen._run_ddl(conn, "dbo.tabela")
        await worker.wait()
        await pilot.pause()
        # the mount notice ("Nenhuma conexao configurada.") is also there:
        # the connection is handed to the worker, never registered
        assert "Error: DDL extraction is not supported for sqlserver." in _notifications(app)
    assert not (Path(paths.EXPORTS_DIR) / "ddl").exists()


@pytest.mark.asyncio
async def test_group_run_warns_that_a_repeated_key_left_rows_out(local2_db, capsys):
    """The screen says what the CLI says: a comparison over an ambiguous
    key covers one row per key and is silent about the rest."""
    from dbqm.ui.screens.group_run import GroupRunScreen

    por_cliente = "SELECT cliente_id AS id, valor FROM pedidos ORDER BY id"
    for nome, conn in (("pc_local", "local"), ("pc_local2", "local2")):
        code, _ = envelope(
            ["query", "add", nome, "--connection", conn, "--sql", por_cliente, "-f", "json"], capsys,
        )
        assert code == 0
    code, _ = envelope(
        ["group", "add", "por_cliente", "--query", "pc_local", "--query", "pc_local2",
         "--join-key", "id", "--compare-column", "valor", "-f", "json"],
        capsys,
    )
    assert code == 0
    group = find_group("por_cliente")
    assert group is not None

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        worker = screen._run_group(group, {})
        await worker.wait()
        await pilot.pause()

        avisos = [n.message for n in app._notifications]
        assert avisos == [
            "Key 'id' has repeated values in 'pc_local': 2 row(s) left out of the comparison.",
            "Key 'id' has repeated values in 'pc_local2': 2 row(s) left out of the comparison.",
        ]


@pytest.mark.asyncio
async def test_group_run_says_nothing_when_the_key_is_unique(local2_db, capsys):
    from dbqm.ui.screens.group_run import GroupRunScreen

    ped = "SELECT id, valor FROM pedidos ORDER BY id"
    for nome, conn in (("ped_local", "local"), ("ped_local2", "local2")):
        code, _ = envelope(
            ["query", "add", nome, "--connection", conn, "--sql", ped, "-f", "json"], capsys,
        )
        assert code == 0
    code, _ = envelope(
        ["group", "add", "pedidos", "--query", "ped_local", "--query", "ped_local2",
         "--join-key", "id", "--compare-column", "valor", "-f", "json"],
        capsys,
    )
    assert code == 0
    group = find_group("pedidos")
    assert group is not None

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        worker = screen._run_group(group, {})
        await worker.wait()
        await pilot.pause()
        assert [n.message for n in app._notifications] == []
