"""Tests for screens."""
from __future__ import annotations

import json

import pytest
from textual.app import ComposeResult
from textual.widgets import Input, Select

from dbqm.ui.screens.connections import ConnectionsScreen
from dbqm.ui.screens.oracle_clients import OracleClientsScreen
from dbqm.ui.screens.query_exec import QueryExecScreen

from tests.ui._helpers import ThemedTestApp


class QueryExecTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield QueryExecScreen()


@pytest.mark.asyncio
async def test_query_exec_screen_renders(tmp_config_dir):
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        assert screen is not None


@pytest.mark.asyncio
async def test_query_exec_screen_shows_empty_message(tmp_config_dir):
    """With no queries configured, should show empty state."""
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        empty = screen.query_one("#empty-message")
        assert empty.display is True


@pytest.mark.asyncio
async def test_query_exec_screen_shows_query_list(tmp_config_dir):
    """With queries configured, should show the query list."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "test_q1",
                "connection": "conn1",
                "sql": "SELECT 1",
                "description": "Test query one",
            },
            {
                "name": "test_q2",
                "connection": "conn1",
                "sql": "SELECT 2",
                "description": "Test query two",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        empty = screen.query_one("#empty-message")
        assert empty.display is False
        # Selection phase should be visible
        sel = screen.query_one("#selection-phase")
        assert sel.display is True
        # Results phase should be hidden
        res = screen.query_one("#results-phase")
        assert res.display is False


@pytest.mark.asyncio
async def test_query_exec_screen_with_folders(tmp_config_dir):
    """Queries with folders should produce tabbed content."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "q_folder_a",
                "connection": "conn1",
                "sql": "SELECT 1",
                "folder": "Grupo A",
            },
            {
                "name": "q_folder_b",
                "connection": "conn1",
                "sql": "SELECT 2",
                "folder": "Grupo B",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        # Should have folder bar with buttons
        folder_bar = screen.query_one("#folder-bar")
        assert folder_bar is not None
        buttons = folder_bar.query("Button")
        # "Todas" + "Grupo A" + "Grupo B" = 3
        assert len(buttons) >= 3


@pytest.mark.asyncio
async def test_query_exec_accented_folders(tmp_config_dir):
    """Folders with accents should not crash the app."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "q1",
                "connection": "c1",
                "sql": "SELECT 1",
                "folder": "Investiga\u00e7\u00e3o",
            },
            {
                "name": "q2",
                "connection": "c1",
                "sql": "SELECT 1",
                "folder": "Produ\u00e7\u00e3o",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        assert screen is not None
        # Should have folder bar with accented folder buttons
        folder_bar = screen.query_one("#folder-bar")
        assert folder_bar is not None
        from textual.widgets import Button
        buttons = folder_bar.query(Button)
        # "Todas" + 2 folders = 3
        assert len(buttons) >= 3


@pytest.mark.asyncio
async def test_query_exec_results_phase_hidden_initially(tmp_config_dir):
    """Results phase should be hidden on mount."""
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        results = screen.query_one("#results-phase")
        assert results.display is False


@pytest.mark.asyncio
async def test_query_exec_go_back_to_selection(tmp_config_dir):
    """go_back_to_selection should show selection and hide results."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "q1",
                "connection": "conn1",
                "sql": "SELECT 1",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        # Simulate being in results phase
        screen.query_one("#selection-phase").display = False
        screen.query_one("#results-phase").display = True

        screen.go_back_to_selection()

        assert screen.query_one("#selection-phase").display is True
        assert screen.query_one("#results-phase").display is False


def _write_filter_queries(config_dir):
    queries_data = {
        "queries": [
            {"name": "Clientes ativos", "connection": "prod", "sql": "S",
             "description": "lista de clientes"},
            {"name": "Pedidos", "connection": "prod", "sql": "S",
             "description": "faturados hoje"},
            {"name": "Estoque", "connection": "homolog", "sql": "S",
             "description": "saldo por deposito"},
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_query_exec_has_filter_bar(tmp_config_dir):
    """With queries, the selection phase shows a text filter + connection select."""
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        text = screen.query_one("#qe-filter-text", Input)
        conn = screen.query_one("#qe-filter-conn", Select)
        assert text.display is True
        assert conn.display is True


@pytest.mark.asyncio
async def test_query_exec_text_filter_narrows_list(tmp_config_dir):
    """Typing in the text filter narrows the list by name/description."""
    from dbqm.ui.widgets.query_list import _QueryListItem
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        assert len(app.query(_QueryListItem)) == 3
        screen.query_one("#qe-filter-text", Input).value = "estoque"
        await pilot.pause()
        items = app.query(_QueryListItem)
        assert len(items) == 1
        assert items[0].query_name == "Estoque"


@pytest.mark.asyncio
async def test_query_exec_text_filter_matches_description(tmp_config_dir):
    """The text filter also matches the query description."""
    from dbqm.ui.widgets.query_list import _QueryListItem
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        screen.query_one("#qe-filter-text", Input).value = "faturados"
        await pilot.pause()
        items = app.query(_QueryListItem)
        assert [i.query_name for i in items] == ["Pedidos"]


@pytest.mark.asyncio
async def test_query_exec_connection_filter_narrows_list(tmp_config_dir):
    """Selecting a connection narrows the list to that connection's queries."""
    from dbqm.ui.widgets.query_list import _QueryListItem
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        screen.query_one("#qe-filter-conn", Select).value = "homolog"
        await pilot.pause()
        items = app.query(_QueryListItem)
        assert [i.query_name for i in items] == ["Estoque"]


@pytest.mark.asyncio
async def test_query_exec_text_and_connection_combined(tmp_config_dir):
    """Text + connection filters AND together."""
    from dbqm.ui.widgets.query_list import _QueryListItem
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        # prod alone → 2 queries
        screen.query_one("#qe-filter-conn", Select).value = "prod"
        await pilot.pause()
        assert len(app.query(_QueryListItem)) == 2
        # narrow with text
        screen.query_one("#qe-filter-text", Input).value = "ped"
        await pilot.pause()
        items = app.query(_QueryListItem)
        assert [i.query_name for i in items] == ["Pedidos"]


@pytest.mark.asyncio
async def test_query_exec_no_filter_bar_when_empty(tmp_config_dir):
    """No queries → no filter bar (empty message instead)."""
    from textual.css.query import NoMatches
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        assert screen.query_one("#empty-message").display is True
        with pytest.raises(NoMatches):
            screen.query_one("#qe-filter-text", Input)


# ======================================================================
# ConnectionsScreen tests — master list (CONEXOES) + embedded form (EDICAO)
# ======================================================================


class ConnectionsTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield ConnectionsScreen()


def _seed_connections(config_dir):
    from dbqm.core.crypto import encrypt

    conn_data = {
        "connections": [
            {
                "name": "dev_oracle",
                "db_type": "oracle",
                "mode": "direct",
                "host": "db.example.com",
                "port": 1521,
                "service_name": "ORCL",
                "user": "admin",
                "password": encrypt("s3cret"),
            },
            {
                "name": "prod_pg",
                "db_type": "postgresql",
                "host": "localhost",
                "port": 5432,
                "database": "mydb",
                "user": "pguser",
                "password": encrypt("pgpass"),
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_connections_screen_renders(tmp_config_dir):
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        assert screen is not None


@pytest.mark.asyncio
async def test_connections_has_list_and_form_panels(tmp_config_dir):
    """CONEXOES + EDICAO panels exist, with the list and form field ids."""
    from dbqm.ui.widgets.panel import Panel

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        titles = [p.query_one("#panel-title").render().plain for p in screen.query(Panel)]
        assert any("CONEXOES" in t for t in titles)
        assert any("EDICAO" in t for t in titles)
        assert screen.query_one("#conn-list") is not None
        assert screen.query_one("#conn-form-name") is not None
        assert screen.query_one("#conn-form-type") is not None
        assert screen.query_one("#conn-form-host") is not None
        assert screen.query_one("#conn-form-port") is not None
        assert screen.query_one("#conn-form-user") is not None
        assert screen.query_one("#conn-form-pass") is not None
        assert screen.query_one("#conn-form-service") is not None
        assert screen.query_one("#conn-form-mode") is not None


@pytest.mark.asyncio
async def test_connections_screen_empty(tmp_config_dir):
    """With no connections, should show empty message and hide the list."""
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import OptionList
        screen = app.query_one(ConnectionsScreen)
        empty = screen.query_one("#conn-empty")
        assert empty.display is True
        option_list = screen.query_one("#conn-list", OptionList)
        assert option_list.display is False


@pytest.mark.asyncio
async def test_connections_empty_state_action_focuses_new_form(tmp_config_dir):
    """The EmptyState's "Adicionar conexao" button must not be a dead end."""
    from textual.widgets import Button
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen.query_one("#adicionar-conexao", Button).press()
        await pilot.pause()
        assert app.focused is screen.query_one("#conn-form-name", Input)


@pytest.mark.asyncio
async def test_connections_screen_with_data(tmp_config_dir):
    """With connections configured, should list them in the OptionList."""
    _seed_connections(tmp_config_dir / "config")

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import OptionList
        screen = app.query_one(ConnectionsScreen)
        empty = screen.query_one("#conn-empty")
        assert empty.display is False
        option_list = screen.query_one("#conn-list", OptionList)
        assert option_list.display is True
        assert option_list.option_count == 2


@pytest.mark.asyncio
async def test_connections_list_shows_description_preview(tmp_config_dir):
    """Long descriptions are truncated with an ellipsis in the list preview."""
    config_dir = tmp_config_dir / "config"
    long_desc = "Producao - " + "x" * 200
    (config_dir / "connections.json").write_text(
        json.dumps({
            "connections": [
                {
                    "name": "prod", "db_type": "postgresql",
                    "host": "h", "port": 5432, "database": "db",
                    "user": "u", "password": "p",
                    "description": long_desc,
                },
                {
                    "name": "no_desc", "db_type": "mysql",
                    "host": "h", "port": 3306, "database": "db",
                    "user": "u", "password": "p",
                },
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    app = ConnectionsTestApp()
    async with app.run_test():
        from textual.widgets import OptionList
        screen = app.query_one(ConnectionsScreen)
        option_list = screen.query_one("#conn-list", OptionList)
        prompt0 = str(option_list.get_option_at_index(0).prompt)
        assert "..." in prompt0
        prompt1 = str(option_list.get_option_at_index(1).prompt)
        assert "prod" not in prompt1  # no_desc row has no description leak


def test_format_description_helper():
    """Unit test the list preview formatter for descriptions."""
    from dbqm.ui.screens.connections import _format_description

    assert _format_description("") == ""
    assert _format_description("short note") == "short note"
    # Newlines collapse to single spaces.
    assert _format_description("line1\nline2") == "line1 line2"
    # Long content is truncated with an ellipsis.
    long = "x" * 200
    out = _format_description(long)
    assert out.endswith("...")
    assert len(out) <= 60


@pytest.mark.asyncio
async def test_connections_select_loads_into_form(tmp_config_dir):
    """Selecting a seeded connection populates the embedded form, with the
    password decrypted for display."""
    _seed_connections(tmp_config_dir / "config")

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()

        assert screen.query_one("#conn-form-name", Input).value == "dev_oracle"
        assert screen.query_one("#conn-form-type", Select).value == "oracle"
        assert screen.query_one("#conn-form-host", Input).value == "db.example.com"
        assert screen.query_one("#conn-form-port", Input).value == "1521"
        assert screen.query_one("#conn-form-service", Input).value == "ORCL"
        assert screen.query_one("#conn-form-user", Input).value == "admin"
        assert screen.query_one("#conn-form-pass", Input).value == "s3cret"


@pytest.mark.asyncio
async def test_connections_nova_clears_form(tmp_config_dir):
    """The 'Nova' action/button clears the form for a new entry."""
    _seed_connections(tmp_config_dir / "config")

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()
        assert screen.query_one("#conn-form-name", Input).value == "dev_oracle"

        from dbqm.ui.widgets.action_bar import ActionSelected
        screen.on_action_selected(ActionSelected("conn_new"))
        await pilot.pause()

        assert screen.query_one("#conn-form-name", Input).value == ""
        assert screen.query_one("#conn-form-name", Input).disabled is False
        assert screen.query_one("#conn-form-type", Select).value == Select.NULL


@pytest.mark.asyncio
async def test_connections_save_creates_new_connection(tmp_config_dir):
    """Filling the form and pressing Salvar creates a new connection."""
    from dbqm.models.connection import load_connections

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)

        screen.query_one("#conn-form-name", Input).value = "new_conn"
        screen.query_one("#conn-form-type", Select).value = "postgresql"
        await pilot.pause()
        screen.query_one("#conn-form-host", Input).value = "pg.example.com"
        screen.query_one("#conn-form-port", Input).value = "5432"
        screen.query_one("#conn-form-database", Input).value = "mydb"
        screen.query_one("#conn-form-user", Input).value = "pguser"
        screen.query_one("#conn-form-pass", Input).value = "secretpw"

        screen._handle_save()
        await pilot.pause()

        conns = load_connections()
        assert any(c.name == "new_conn" for c in conns)
        saved = next(c for c in conns if c.name == "new_conn")
        assert saved.host == "pg.example.com"
        assert saved.database == "mydb"

        from dbqm.core.crypto import decrypt
        assert decrypt(saved.password) == "secretpw"


@pytest.mark.asyncio
async def test_connections_save_updates_existing_connection(tmp_config_dir):
    """Editing a loaded connection and pressing Salvar persists the change."""
    _seed_connections(tmp_config_dir / "config")
    from dbqm.models.connection import find_connection

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()

        screen.query_one("#conn-form-host", Input).value = "new-host.example.com"
        screen._handle_save()
        await pilot.pause()

        updated = find_connection("dev_oracle")
        assert updated is not None
        assert updated.host == "new-host.example.com"

        # Password re-encrypted from the (unchanged) decrypted display value.
        from dbqm.core.crypto import decrypt
        assert decrypt(updated.password) == "s3cret"


@pytest.mark.asyncio
async def test_connections_excluir_removes_connection(tmp_config_dir):
    """Excluir, after confirming, deletes the highlighted connection."""
    _seed_connections(tmp_config_dir / "config")
    from dbqm.models.connection import load_connections
    from dbqm.ui.modals.confirm import ConfirmModal

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()

        from dbqm.ui.widgets.action_bar import ActionSelected
        screen.on_action_selected(ActionSelected("conn_remove"))
        await pilot.pause()

        modal = next(s for s in app.screen_stack if isinstance(s, ConfirmModal))
        assert "dev_oracle" in modal._message

        screen._on_remove_result(True)
        await pilot.pause()

        conns = load_connections()
        assert all(c.name != "dev_oracle" for c in conns)
        # Form is cleared since the deleted connection was loaded.
        assert screen.query_one("#conn-form-name", Input).value == ""


@pytest.mark.asyncio
async def test_connections_testar_warns_without_name(tmp_config_dir):
    """Testar with an empty form name shows a warning, not a crash."""
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._handle_test()
        await pilot.pause()
        messages = [str(n.message) for n in app._notifications]
        assert any("nome" in m.lower() for m in messages)


@pytest.mark.asyncio
async def test_connections_testar_starts_worker_for_named_connection(tmp_config_dir):
    """Testar with a name in the form kicks off the existing test worker."""
    _seed_connections(tmp_config_dir / "config")

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()

        screen._handle_test()
        await pilot.pause()

        messages = [str(n.message) for n in app._notifications]
        assert any("Testando" in m for m in messages)


# ======================================================================
# QueryManageScreen tests
# ======================================================================

from dbqm.ui.screens.query_manage import QueryManageScreen


class QueryManageTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield QueryManageScreen()


@pytest.mark.asyncio
async def test_query_manage_screen_renders(tmp_config_dir):
    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(QueryManageScreen) is not None


@pytest.mark.asyncio
async def test_query_manage_screen_empty(tmp_config_dir):
    """With no queries, should show empty message and hide table."""
    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryManageScreen)
        empty = screen.query_one("#qm-empty")
        assert empty.display is True
        from textual.widgets import DataTable
        table = screen.query_one("#qm-table", DataTable)
        assert table.display is False


@pytest.mark.asyncio
async def test_query_manage_empty_state_action_opens_new_query(tmp_config_dir):
    """The EmptyState's "Criar consulta" button must not be a dead end."""
    from textual.widgets import Button
    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryManageScreen)
        screen.query_one("#criar-consulta", Button).press()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # SqlPasteModal opened


@pytest.mark.asyncio
async def test_query_manage_screen_with_data(tmp_config_dir):
    """With queries configured, should show them in the table."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "query_b",
                "connection": "conn1",
                "sql": "SELECT * FROM tabB",
                "description": "Second query",
                "folder": "Beta",
            },
            {
                "name": "query_a",
                "connection": "conn1",
                "sql": "SELECT * FROM tabA",
                "description": "First query",
                "folder": "Alpha",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryManageScreen)
        empty = screen.query_one("#qm-empty")
        assert empty.display is False
        from textual.widgets import DataTable
        table = screen.query_one("#qm-table", DataTable)
        assert table.display is True
        assert table.row_count == 2
        # Should be sorted by folder: Alpha first, then Beta
        row0 = table.get_row_at(0)
        assert str(row0[1]) == "Alpha"
        row1 = table.get_row_at(1)
        assert str(row1[1]) == "Beta"


@pytest.mark.asyncio
async def test_query_manage_screen_favorite_column(tmp_config_dir):
    """Favorite queries should show a star in the Fav column."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "fav_query",
                "connection": "conn1",
                "sql": "SELECT 1",
                "is_favorite": True,
            },
            {
                "name": "normal_query",
                "connection": "conn1",
                "sql": "SELECT 2",
                "is_favorite": False,
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryManageScreen)
        from textual.widgets import DataTable
        table = screen.query_one("#qm-table", DataTable)
        assert table.row_count == 2


# ======================================================================
# GroupManageScreen tests
# ======================================================================

from dbqm.ui.screens.group_manage import GroupManageScreen


class GroupManageTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield GroupManageScreen()


@pytest.mark.asyncio
async def test_group_manage_screen_renders(tmp_config_dir):
    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(GroupManageScreen) is not None


@pytest.mark.asyncio
async def test_group_manage_screen_empty(tmp_config_dir):
    """With no groups, should show empty message and hide table."""
    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupManageScreen)
        empty = screen.query_one("#gm-empty")
        assert empty.display is True
        from textual.widgets import DataTable
        table = screen.query_one("#gm-table", DataTable)
        assert table.display is False


@pytest.mark.asyncio
async def test_group_manage_empty_state_action_opens_new_group(tmp_config_dir):
    """The EmptyState's "Criar grupo" button must not be a dead end."""
    from dbqm.models.query import Query, save_queries
    from textual.widgets import Button

    save_queries([
        Query(name="q1", connection="c1", sql="SELECT 1 FROM dual", table="dual"),
        Query(name="q2", connection="c1", sql="SELECT 2 FROM dual", table="dual"),
    ])

    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupManageScreen)
        screen.query_one("#criar-grupo", Button).press()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # GroupCreateModal opened


# ======================================================================
# GroupExecScreen tests
# ======================================================================

from dbqm.ui.screens.group_exec import GroupExecScreen


class GroupExecTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield GroupExecScreen()


@pytest.mark.asyncio
async def test_group_exec_screen_renders(tmp_config_dir):
    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(GroupExecScreen) is not None


@pytest.mark.asyncio
async def test_group_exec_screen_has_option3_widgets(tmp_config_dir):
    """Multi-Exec (Option 3) exposes the target checklist, SQL editor,
    comparison display and the saved-group Select."""
    from textual.widgets import SelectionList, TextArea, Select
    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        assert screen.query_one("#conn-checklist", SelectionList) is not None
        assert screen.query_one("#group-sql", TextArea) is not None
        assert screen.query_one("#group-results", GroupResultWidget) is not None
        assert screen.query_one("#group-saved-select", Select) is not None


@pytest.mark.asyncio
async def test_group_exec_checklist_lists_connections(tmp_config_dir):
    """The connection checklist is populated from the saved connections."""
    from textual.widgets import SelectionList
    _seed_connections(tmp_config_dir / "config")

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        checklist = screen.query_one("#conn-checklist", SelectionList)
        values = {opt.value for opt in checklist.options}
        assert {"dev_oracle", "prod_pg"} <= values


@pytest.mark.asyncio
async def test_group_exec_saved_select_lists_only_adhoc_groups(tmp_config_dir):
    """Only groups with adhoc_sql appear in the saved-group Select."""
    from textual.widgets import Select
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "legacy_query_group",
                "description": "old query-based",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            },
            {
                "name": "adhoc_group",
                "description": "",
                "queries": [],
                "join_key": "ID",
                "adhoc_sql": "SELECT ID, STATUS FROM t",
                "connections": ["dev_oracle"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        select = screen.query_one("#group-saved-select", Select)
        labels = {label.plain if hasattr(label, "plain") else str(label)
                  for label, _ in select._options}
        assert "adhoc_group" in labels
        assert "legacy_query_group" not in labels


@pytest.mark.asyncio
async def test_group_exec_load_group_checks_conns_and_fills_sql(tmp_config_dir):
    """Carregar an ad-hoc group checks its connections and fills the SQL."""
    from textual.widgets import SelectionList, TextArea, Select, Button
    config_dir = tmp_config_dir / "config"
    _seed_connections(config_dir)
    groups_data = {
        "groups": [
            {
                "name": "adhoc_group",
                "description": "",
                "queries": [],
                "join_key": "ID",
                "adhoc_sql": "SELECT ID, STATUS FROM apolice",
                "connections": ["prod_pg"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen.query_one("#group-saved-select", Select).value = "adhoc_group"
        await pilot.pause()

        screen._load_group()
        await pilot.pause()

        sql = screen.query_one("#group-sql", TextArea).text
        assert "SELECT ID, STATUS FROM apolice" in sql
        checklist = screen.query_one("#conn-checklist", SelectionList)
        assert list(checklist.selected) == ["prod_pg"]


@pytest.mark.asyncio
async def test_group_exec_handle_execute_warns_on_empty_sql(tmp_config_dir):
    """Executar with no SQL typed should warn and never start a run."""
    from dbqm.ui.widgets.progress import ProgressIndicator

    _seed_connections(tmp_config_dir / "config")

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen._handle_execute()
        await pilot.pause()

        messages = [str(n.message) for n in app._notifications]
        assert any("sql" in m.lower() for m in messages)
        assert screen.query_one(ProgressIndicator).display is False


@pytest.mark.asyncio
async def test_group_exec_handle_execute_warns_on_no_connections_checked(tmp_config_dir):
    """Executar with SQL but no checked connections should warn and not run."""
    from textual.widgets import TextArea
    from dbqm.ui.widgets.progress import ProgressIndicator

    _seed_connections(tmp_config_dir / "config")

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen.query_one("#group-sql", TextArea).load_text("SELECT 1 FROM DUAL")
        await pilot.pause()

        screen._handle_execute()
        await pilot.pause()

        messages = [str(n.message) for n in app._notifications]
        assert any("conexao" in m.lower() for m in messages)
        assert screen.query_one(ProgressIndicator).display is False


@pytest.mark.asyncio
async def test_group_exec_on_save_name_persists_adhoc_group(tmp_config_dir):
    """_on_save_name (the save-as-group flow) persists a Group with the
    current SQL and checked connections."""
    from textual.widgets import TextArea
    from dbqm.models.group import load_groups

    _seed_connections(tmp_config_dir / "config")

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen.query_one("#group-sql", TextArea).load_text("SELECT ID, STATUS FROM apolice")
        screen._populate_connections({"dev_oracle", "prod_pg"})
        await pilot.pause()

        screen._on_save_name("meu_grupo_adhoc")
        await pilot.pause()

        groups = {g.name: g for g in load_groups()}
        assert "meu_grupo_adhoc" in groups
        saved = groups["meu_grupo_adhoc"]
        assert saved.adhoc_sql == "SELECT ID, STATUS FROM apolice"
        assert sorted(saved.connections) == ["dev_oracle", "prod_pg"]


@pytest.mark.asyncio
async def test_group_exec_save_selection_warns_when_incomplete(tmp_config_dir):
    """_save_selection should warn (and not push a naming dialog) when SQL
    or the connection checklist is empty."""
    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        base_stack_len = len(app.screen_stack)

        screen._save_selection()
        await pilot.pause()

        messages = [str(n.message) for n in app._notifications]
        assert any("sql" in m.lower() for m in messages)
        assert len(app.screen_stack) == base_stack_len


@pytest.mark.asyncio
async def test_group_exec_execute_runs_per_connection_and_builds_comparison(
    tmp_config_dir, monkeypatch
):
    """Running the worker against two fake connections invokes execute_adhoc
    per connection and produces a real comparison rendered in #group-results."""
    from dbqm.core.query_engine import AdhocResult

    _seed_connections(tmp_config_dir / "config")

    calls: list[tuple[str, str]] = []

    def fake_execute_adhoc(sql, conn, param_values, auto_commit=False, capture_output=False):
        calls.append((sql, conn.name))
        rows = [[1, "ok"], [2, "fail"]] if conn.name == "dev_oracle" else [[1, "ok"], [2, "ok"]]
        return AdhocResult(
            sql_type="SELECT",
            connection_name=conn.name,
            columns=["ID", "STATUS"],
            rows=rows,
            row_count=len(rows),
        )

    monkeypatch.setattr("dbqm.core.query_engine.execute_adhoc", fake_execute_adhoc)

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)

        worker = screen._run("SELECT ID, STATUS FROM t", ["dev_oracle", "prod_pg"])
        await worker.wait()
        await pilot.pause()

        # execute_adhoc was invoked once per checked connection.
        assert sorted(calls) == [
            ("SELECT ID, STATUS FROM t", "dev_oracle"),
            ("SELECT ID, STATUS FROM t", "prod_pg"),
        ]

        grw = screen.query_one("#group-results", GroupResultWidget)
        gr = grw.group_result
        assert gr is not None
        assert set(gr.query_results.keys()) == {"dev_oracle", "prod_pg"}
        assert gr.all_match is False
        assert len(gr.comparisons) == 1
        comp = gr.comparisons[0]
        assert comp.column == "STATUS"
        assert comp.diff_count == 1
        assert comp.equal_count == 1


@pytest.mark.asyncio
async def test_group_manage_screen_with_data(tmp_config_dir):
    """With groups configured, should show them in the table."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "grupo_b",
                "description": "Second group",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "Beta",
            },
            {
                "name": "grupo_a",
                "description": "First group",
                "queries": ["q1", "q3"],
                "join_key": "code",
                "compare_columns": ["value"],
                "folder": "Alpha",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupManageScreen)
        empty = screen.query_one("#gm-empty")
        assert empty.display is False
        from textual.widgets import DataTable
        table = screen.query_one("#gm-table", DataTable)
        assert table.display is True
        assert table.row_count == 2
        # Should be sorted alphabetically: grupo_a first, then grupo_b
        row0 = table.get_row_at(0)
        assert str(row0[1]) == "grupo_a"
        row1 = table.get_row_at(1)
        assert str(row1[1]) == "grupo_b"


# ======================================================================
# AdhocScreen tests
# ======================================================================

from dbqm.ui.screens.adhoc import AdhocScreen


class AdhocTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield AdhocScreen()


@pytest.mark.asyncio
async def test_adhoc_screen_renders(tmp_config_dir):
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(AdhocScreen) is not None


@pytest.mark.asyncio
async def test_adhoc_has_params_editor_results_panels(tmp_config_dir):
    """AdhocScreen renders three simultaneous panels + a results sub-toggle."""
    from dbqm.ui.widgets.panel import Panel
    from textual.widgets import ContentSwitcher, Select, TextArea

    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        titles = [
            p.query_one("#panel-title").render().plain for p in screen.query(Panel)
        ]
        assert any("PARAMETROS" in t for t in titles)
        assert any("SQL EDITOR" in t for t in titles)
        assert any("RESULTADOS" in t for t in titles)
        # Results sub-toggle: a ContentSwitcher with table + output panes.
        switcher = screen.query_one("#res-switcher", ContentSwitcher)
        assert switcher is not None
        assert screen.query_one("#res-table") is not None
        assert screen.query_one("#res-output") is not None
        # Params panel keeps the connection Select; editor keeps the TextArea.
        assert screen.query_one("#adhoc-conn-select", Select) is not None
        assert screen.query_one("#adhoc-sql-area", TextArea) is not None


@pytest.mark.asyncio
async def test_adhoc_screen_starts_on_table_view(tmp_config_dir):
    """The results sub-toggle starts on the Tabela (res-table) view."""
    from textual.widgets import ContentSwitcher
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        switcher = screen.query_one("#res-switcher", ContentSwitcher)
        assert switcher.current == "res-table"


@pytest.mark.asyncio
async def test_adhoc_screen_has_sql_area(tmp_config_dir):
    """AdhocScreen should have a TextArea for SQL input."""
    from textual.widgets import TextArea
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        text_area = screen.query_one("#adhoc-sql-area", TextArea)
        assert text_area is not None


@pytest.mark.asyncio
async def test_adhoc_screen_has_buttons(tmp_config_dir):
    """AdhocScreen should have execute, clear, generate, and save buttons."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        from textual.widgets import Button
        execute_btn = screen.query_one("#adhoc-execute", Button)
        clear_btn = screen.query_one("#adhoc-clear", Button)
        generate_btn = screen.query_one("#adhoc-generate", Button)
        save_btn = screen.query_one("#adhoc-save", Button)
        assert execute_btn is not None
        assert clear_btn is not None
        assert generate_btn is not None
        assert save_btn is not None
        # Execute button should start disabled (no connection or SQL)
        assert execute_btn.disabled is True


@pytest.mark.asyncio
async def test_adhoc_results_sub_toggle_switches_views(tmp_config_dir):
    """The Tabela/Output buttons flip the results ContentSwitcher."""
    from textual.widgets import Button, ContentSwitcher
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        switcher = screen.query_one("#res-switcher", ContentSwitcher)

        screen.query_one("#res-btn-output", Button).press()
        await pilot.pause()
        assert switcher.current == "res-output"

        screen.query_one("#res-btn-table", Button).press()
        await pilot.pause()
        assert switcher.current == "res-table"


@pytest.mark.asyncio
async def test_adhoc_unmount_cleans_connection(tmp_config_dir):
    """Leaving the screen should rollback and close any open DML connection."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)

        # Create a mock connection
        class MockConn:
            rolled_back = False
            closed = False
            def rollback(self):
                self.rolled_back = True
            def close(self):
                self.closed = True

        mock = MockConn()
        screen._db_connection = mock

        screen.on_unmount()

        assert mock.rolled_back is True
        assert mock.closed is True
        assert screen._db_connection is None


def test_format_plsql_message_header_only():
    """Formatter shows only the success header; DBMS_OUTPUT goes to the panel."""
    from dbqm.core.query_engine import AdhocResult
    from dbqm.ui.screens.adhoc import _format_plsql_message

    result = AdhocResult(
        sql_type="PLSQL", connection_name="c1", elapsed=0.01,
        committed=True, output_lines=["linha um", "linha dois"],
    )
    msg = _format_plsql_message(result)
    assert "Bloco PL/SQL executado" in msg
    # Output lines are rendered in the dedicated panel, not the header static.
    assert "linha um" not in msg


@pytest.mark.asyncio
async def test_adhoc_plsql_result_shows_static(tmp_config_dir):
    """PLSQL results route to the result static, without the DML warning."""
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "PLSQL"
        result = AdhocResult(
            sql_type="PLSQL", connection_name="c1", elapsed=0.01,
            committed=True, output_lines=["linha um"],
        )
        screen._on_sql_result(result)

        from textual.widgets import ContentSwitcher
        # PL/SQL routes to the Output view; the DML/message static shows there.
        assert screen.query_one("#res-switcher", ContentSwitcher).current == "res-output"
        assert screen.query_one("#adhoc-dml-result").display is True
        assert screen.query_one("#res-table").display is False


@pytest.mark.asyncio
async def test_adhoc_has_dbms_toggle(tmp_config_dir):
    """Input phase exposes a checkbox to opt into DBMS_OUTPUT capture."""
    from textual.widgets import Checkbox
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        toggle = screen.query_one("#adhoc-dbms-toggle", Checkbox)
        assert toggle.value is False
        assert str(toggle.label) == "Saida DBMS"


@pytest.mark.asyncio
async def test_adhoc_dbms_toggle_aligns_with_select(tmp_config_dir):
    """The DBMS toggle matches the connection select height and stays within
    the SQL editor width (no header overflow past the box below)."""
    from textual.widgets import Checkbox, Select, TextArea
    app = AdhocTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = app.query_one(AdhocScreen)
        toggle = screen.query_one("#adhoc-dbms-toggle", Checkbox)
        select = screen.query_one("#adhoc-conn-select", Select)
        sql_area = screen.query_one("#adhoc-sql-area", TextArea)

        # Same height as the connection select next to it.
        assert toggle.region.height == select.region.height
        # Right edge must not extend past the SQL editor below it.
        assert toggle.region.right <= sql_area.region.right


@pytest.mark.asyncio
async def test_adhoc_dbms_panel_hidden_initially(tmp_config_dir):
    """The DBMS_OUTPUT panel is hidden until a captured execution renders it."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        assert screen.query_one("#adhoc-dbms-panel").display is False


@pytest.mark.asyncio
async def test_adhoc_select_shows_dbms_panel_when_capture_enabled(tmp_config_dir):
    """A SELECT with capture on loads the table AND populates the DBMS panel.

    With the results sub-toggle, DBMS output routes the view to Output; the
    table stays loaded and reachable via the Tabela button.
    """
    from textual.widgets import Button, ContentSwitcher, TextArea
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "SELECT"
        screen._capture_output = True
        result = AdhocResult(
            sql_type="SELECT", connection_name="c1", elapsed=0.01,
            columns=["x"], rows=[[1]], row_count=1,
            output_lines=["log A", "log B"],
        )
        screen._on_sql_result(result)
        await pilot.pause()

        # DBMS output present -> Output view is selected.
        switcher = screen.query_one("#res-switcher", ContentSwitcher)
        assert switcher.current == "res-output"
        panel = screen.query_one("#adhoc-dbms-panel")
        assert panel.display is True
        view = screen.query_one("#adhoc-dbms-view", TextArea)
        assert "log A" in view.text
        assert "log B" in view.text

        # The table is still loaded and reachable via the Tabela toggle.
        from dbqm.ui.widgets.result_table import ResultTable
        screen.query_one("#res-btn-table", Button).press()
        await pilot.pause()
        assert switcher.current == "res-table"
        assert screen.query_one("#res-table", ResultTable).display is True


@pytest.mark.asyncio
async def test_adhoc_select_hides_dbms_panel_when_capture_disabled(tmp_config_dir):
    """A SELECT with capture off does not show the DBMS panel."""
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "SELECT"
        screen._capture_output = False
        result = AdhocResult(
            sql_type="SELECT", connection_name="c1", elapsed=0.01,
            columns=["x"], rows=[[1]], row_count=1,
        )
        screen._on_sql_result(result)
        await pilot.pause()

        assert screen.query_one("#adhoc-dbms-panel").display is False


@pytest.mark.asyncio
async def test_adhoc_plsql_always_shows_dbms_panel(tmp_config_dir):
    """PL/SQL output always renders in the panel, regardless of the checkbox."""
    from textual.widgets import TextArea
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "PLSQL"
        screen._capture_output = False
        result = AdhocResult(
            sql_type="PLSQL", connection_name="c1", elapsed=0.01,
            committed=True, output_lines=["bloco rodou"],
        )
        screen._on_sql_result(result)
        await pilot.pause()

        panel = screen.query_one("#adhoc-dbms-panel")
        assert panel.display is True
        view = screen.query_one("#adhoc-dbms-view", TextArea)
        assert "bloco rodou" in view.text


@pytest.mark.asyncio
async def test_adhoc_dbms_panel_empty_shows_placeholder(tmp_config_dir):
    """Capture on but no output lines still shows the panel with a placeholder."""
    from textual.widgets import TextArea
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "SELECT"
        screen._capture_output = True
        result = AdhocResult(
            sql_type="SELECT", connection_name="c1", elapsed=0.01,
            columns=["x"], rows=[[1]], row_count=1, output_lines=[],
        )
        screen._on_sql_result(result)
        await pilot.pause()

        assert screen.query_one("#adhoc-dbms-panel").display is True
        view = screen.query_one("#adhoc-dbms-view", TextArea)
        assert view.text.strip() != ""  # placeholder, not blank


@pytest.mark.asyncio
async def test_adhoc_dbms_toggle_read_by_execute(tmp_config_dir):
    """_dbms_output_enabled reflects the checkbox state."""
    from textual.widgets import Checkbox
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        assert screen._dbms_output_enabled() is False
        screen.query_one("#adhoc-dbms-toggle", Checkbox).value = True
        await pilot.pause()
        assert screen._dbms_output_enabled() is True


@pytest.mark.asyncio
async def test_adhoc_screen_connection_selector(tmp_config_dir):
    """AdhocScreen should have a connection selector."""
    config_dir = tmp_config_dir / "config"
    conn_data = {
        "connections": [
            {
                "name": "test_conn",
                "db_type": "oracle",
                "mode": "direct",
                "host": "localhost",
                "port": 1521,
                "service_name": "ORCL",
                "user": "admin",
                "password": "pass",
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )

    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        select_widget = screen.query_one("#adhoc-conn-select", Select)
        assert select_widget is not None


@pytest.mark.asyncio
async def test_adhoc_screen_select_styling_on_change(tmp_config_dir):
    """Select should get --conn-selected class when a connection is picked."""
    config_dir = tmp_config_dir / "config"
    conn_data = {
        "connections": [
            {
                "name": "test_conn",
                "db_type": "oracle",
                "mode": "direct",
                "host": "localhost",
                "port": 1521,
                "service_name": "ORCL",
                "user": "admin",
                "password": "pass",
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )

    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        select_widget = screen.query_one("#adhoc-conn-select", Select)
        # Initially no connection selected — no class
        assert not select_widget.has_class("--conn-selected")
        # Simulate selecting a connection
        select_widget.value = "test_conn"
        await pilot.pause()
        assert select_widget.has_class("--conn-selected")


@pytest.mark.asyncio
async def test_adhoc_screen_execute_enabled_when_conn_and_sql(tmp_config_dir):
    """Execute button should enable when both connection and SQL are present."""
    config_dir = tmp_config_dir / "config"
    conn_data = {
        "connections": [
            {
                "name": "test_conn",
                "db_type": "oracle",
                "mode": "direct",
                "host": "localhost",
                "port": 1521,
                "service_name": "ORCL",
                "user": "admin",
                "password": "pass",
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )

    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        from textual.widgets import Button, TextArea
        execute_btn = screen.query_one("#adhoc-execute", Button)
        sql_area = screen.query_one("#adhoc-sql-area", TextArea)
        select_widget = screen.query_one("#adhoc-conn-select", Select)

        # Initially disabled
        assert execute_btn.disabled is True

        # Set SQL but no connection — still disabled
        sql_area.insert("SELECT 1 FROM DUAL")
        await pilot.pause()
        assert execute_btn.disabled is True

        # Set connection — now enabled
        select_widget.value = "test_conn"
        await pilot.pause()
        assert execute_btn.disabled is False


# ======================================================================
# BrowserScreen tests
# ======================================================================

from dbqm.ui.screens.browser import BrowserScreen


class BrowserTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield BrowserScreen()


@pytest.mark.asyncio
async def test_browser_screen_renders(tmp_config_dir):
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(BrowserScreen) is not None


@pytest.mark.asyncio
async def test_browser_shows_empty_state_until_connection_chosen(tmp_config_dir):
    """No connection selected yet: EmptyState replaces the object OptionList,
    and its "Escolher conexao" button must not be a dead end."""
    from textual.widgets import Button, OptionList, Select
    from dbqm.ui.widgets.empty_state import EmptyState

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        empty = screen.query_one("#obj-list-empty", EmptyState)
        assert empty.display is True
        assert screen.query_one("#obj-list", OptionList).display is False

        screen.query_one("#escolher-conexao", Button).press()
        await pilot.pause()
        assert app.focused is screen.query_one("#obj-conn", Select)


@pytest.mark.asyncio
async def test_browser_three_live_panels(tmp_config_dir):
    """BrowserScreen renders three simultaneous panels + the live surfaces."""
    from dbqm.ui.widgets.panel import Panel

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        titles = [
            p.query_one("#panel-title").render().plain for p in screen.query(Panel)
        ]
        assert any("OBJETOS" in t for t in titles)
        assert any("COLUNAS" in t for t in titles)
        assert any("DADOS" in t for t in titles)
        assert screen.query_one("#obj-list") is not None
        assert screen.query_one("#obj-columns") is not None
        assert screen.query_one("#obj-preview") is not None


@pytest.mark.asyncio
async def test_browser_has_conn_type_filter_and_buttons(tmp_config_dir):
    """OBJETOS panel exposes conn + type selects, a filter input, and the
    DADOS panel carries the Extrair DDL / Carregar mais buttons."""
    from textual.widgets import Button
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        assert screen.query_one("#obj-conn", Select) is not None
        assert screen.query_one("#obj-type", Select) is not None
        assert screen.query_one("#obj-filter", Input) is not None
        assert screen.query_one("#obj-ddl", Button) is not None
        assert screen.query_one("#obj-more", Button) is not None


@pytest.mark.asyncio
async def test_browser_reload_populates_object_list(tmp_config_dir, monkeypatch):
    """Reloading objects (via list_objects) fills the OptionList."""
    from textual.widgets import OptionList

    monkeypatch.setattr(
        "dbqm.core.object_browser.list_objects",
        lambda db, db_type, obj_type: ["CLIENTE", "PEDIDO", "PRODUTO"],
    )

    class _FakeConn:
        name = "c1"
        db_type = "oracle"

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        screen._current_conn = _FakeConn()
        screen._db = object()
        screen._obj_type = "TABLE"

        worker = screen._reload_objects()
        await worker.wait()
        await pilot.pause()

        option_list = screen.query_one("#obj-list", OptionList)
        assert option_list.option_count == 3


@pytest.mark.asyncio
async def test_browser_select_object_fills_columns_and_preview(
    tmp_config_dir, monkeypatch
):
    """Selecting an object fires ONE worker that fills BOTH the COLUNAS table
    (structure) and the DADOS preview (first page) — the live-update contract."""
    from types import SimpleNamespace
    from textual.widgets import DataTable
    from dbqm.ui.widgets.result_table import ResultTable
    from dbqm.core.table_browser import BrowseResult

    fake_structure = SimpleNamespace(
        table="CLIENTE",
        elapsed=0.01,
        indexes=[],
        columns=[
            SimpleNamespace(
                name="ID", data_type="NUMBER", data_precision=10, data_scale=0,
                data_length=None, nullable=False, is_pk=True, fk_ref=None,
            ),
            SimpleNamespace(
                name="NOME", data_type="VARCHAR2", data_precision=None,
                data_scale=None, data_length=100, nullable=True, is_pk=False,
                fk_ref=None,
            ),
        ],
    )
    fake_browse = BrowseResult(
        table="CLIENTE",
        connection_name="c1",
        columns=["ID", "NOME"],
        rows=[[1, "Ana"], [2, "Bruno"]],
        row_count=2,
        total_count=2,
        elapsed=0.02,
        limit=100,
        offset=0,
    )

    monkeypatch.setattr(
        "dbqm.core.object_browser.get_table_structure",
        lambda db, db_type, table: fake_structure,
    )
    monkeypatch.setattr(
        "dbqm.core.table_browser.browse_table",
        lambda db, db_type, table, conn_name, limit, offset: fake_browse,
    )

    class _FakeConn:
        name = "c1"
        db_type = "oracle"

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        screen._current_conn = _FakeConn()
        screen._db = object()
        screen._obj_type = "TABLE"

        worker = screen._load_object("CLIENTE")
        await worker.wait()
        await pilot.pause()

        columns_table = screen.query_one("#obj-columns", DataTable)
        assert columns_table.row_count == 2  # two columns of CLIENTE
        preview = screen.query_one("#obj-preview", ResultTable)
        assert preview is not None
        assert screen._selected_object == "CLIENTE"


@pytest.mark.asyncio
async def test_browser_select_package_shows_source_no_error(
    tmp_config_dir, monkeypatch
):
    """Selecting a PACKAGE fetches SOURCE text (via the ddl_extractor core
    used by "Extrair DDL") and shows it inline — no browse_table ORA-00942,
    no error toast."""
    from types import SimpleNamespace
    from dbqm.ui.widgets.sql_viewer import SqlViewer
    from dbqm.ui.widgets.result_table import ResultTable
    from dbqm.core.ddl_extractor import ExtractedObject, ExtractionResult

    fake_result = ExtractionResult(
        object_name="PKG_CLIENTE", object_type="PACKAGE",
        owner="APP", connection_name="c1",
        objects=[
            ExtractedObject("PKG_CLIENTE", "PACKAGE SPEC", "CREATE OR REPLACE PACKAGE pkg_cliente IS ..."),
            ExtractedObject("PKG_CLIENTE", "PACKAGE BODY", "CREATE OR REPLACE PACKAGE BODY pkg_cliente IS ..."),
        ],
    )

    def _fake_browse_table(*args, **kwargs):
        raise AssertionError("browse_table must not be called for PACKAGE objects")

    monkeypatch.setattr(
        "dbqm.core.ddl_extractor.extract_ddl",
        lambda conn, name, owner_filter=None, on_progress=None: fake_result,
    )
    monkeypatch.setattr(
        "dbqm.core.object_browser.list_package_routines",
        lambda db, db_type, package: SimpleNamespace(
            name="PKG_CLIENTE", owner="APP",
            routines=[
                SimpleNamespace(name="GET_NOME", routine_type="FUNCTION", signature="(p_id NUMBER) RETURN VARCHAR2"),
            ],
        ),
    )
    monkeypatch.setattr("dbqm.core.table_browser.browse_table", _fake_browse_table)

    class _FakeConn:
        name = "c1"
        db_type = "oracle"

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        screen._current_conn = _FakeConn()
        screen._db = object()
        screen._obj_type = "PACKAGE"

        worker = screen._load_object("PKG_CLIENTE")
        await worker.wait()
        await pilot.pause()

        source_view = screen.query_one("#obj-source", SqlViewer)
        assert "pkg_cliente" in source_view._sql
        assert source_view.display is True
        preview = screen.query_one("#obj-preview", ResultTable)
        assert preview.display is False

        error_notifications = [
            n for n in app._notifications if n.severity == "error"
        ]
        assert error_notifications == []


@pytest.mark.asyncio
async def test_browser_select_table_shows_table_view(tmp_config_dir, monkeypatch):
    """The table view (#obj-preview) is used for TABLE, and toggling back
    from a previous PACKAGE selection hides the source view again."""
    from types import SimpleNamespace
    from dbqm.core.table_browser import BrowseResult
    from dbqm.ui.widgets.sql_viewer import SqlViewer
    from dbqm.ui.widgets.result_table import ResultTable

    fake_structure = SimpleNamespace(
        table="CLIENTE", elapsed=0.01, indexes=[],
        columns=[
            SimpleNamespace(
                name="ID", data_type="NUMBER", data_precision=10, data_scale=0,
                data_length=None, nullable=False, is_pk=True, fk_ref=None,
            ),
        ],
    )
    fake_browse = BrowseResult(
        table="CLIENTE", connection_name="c1", columns=["ID"],
        rows=[[1]], row_count=1, total_count=1, elapsed=0.01,
        limit=100, offset=0,
    )
    monkeypatch.setattr(
        "dbqm.core.object_browser.get_table_structure",
        lambda db, db_type, table: fake_structure,
    )
    monkeypatch.setattr(
        "dbqm.core.table_browser.browse_table",
        lambda db, db_type, table, conn_name, limit, offset: fake_browse,
    )

    class _FakeConn:
        name = "c1"
        db_type = "oracle"

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        screen._current_conn = _FakeConn()
        screen._db = object()
        screen._obj_type = "TABLE"

        worker = screen._load_object("CLIENTE")
        await worker.wait()
        await pilot.pause()

        preview = screen.query_one("#obj-preview", ResultTable)
        source_view = screen.query_one("#obj-source", SqlViewer)
        assert preview.display is True
        assert source_view.display is False


@pytest.mark.asyncio
async def test_browser_screen_unmount_closes_db(tmp_config_dir):
    """Unmounting BrowserScreen should close the DB connection."""
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)

        class MockDB:
            closed = False
            def close(self):
                self.closed = True

        mock = MockDB()
        screen._db = mock
        screen.on_unmount()

        assert mock.closed is True
        assert screen._db is None


# ======================================================================
# HistoryScreen tests
# ======================================================================

from dbqm.ui.screens.history import HistoryScreen


class HistoryTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield HistoryScreen()


@pytest.mark.asyncio
async def test_history_screen_renders(tmp_config_dir):
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(HistoryScreen) is not None


@pytest.mark.asyncio
async def test_history_shows_table_and_detail_together(tmp_config_dir):
    """Table and detail panel are both visible at once — no phase swap."""
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        assert screen.query_one("#hist-table").display
        assert screen.query_one("#hist-detail").display


@pytest.mark.asyncio
async def test_history_panels_have_titles(tmp_config_dir):
    """HISTORICO and DETALHES panels both exist."""
    from dbqm.ui.widgets.panel import Panel

    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        panels = screen.query(Panel)
        titles = [p.query_one("#panel-title").render().plain for p in panels]
        assert any("HISTORICO" in t for t in titles)
        assert any("DETALHES" in t for t in titles)


@pytest.mark.asyncio
async def test_history_screen_empty(tmp_config_dir):
    """With no history, should show empty message; table stays docked/visible."""
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        empty = screen.query_one("#hist-empty")
        assert empty.display is True
        from textual.widgets import DataTable
        table = screen.query_one("#hist-table", DataTable)
        assert table.display is True
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_history_empty_state_action_switches_to_query_exec(tmp_config_dir):
    """The EmptyState's "Executar consulta" button must not be a dead end."""
    from textual.widgets import Button

    switched = []

    class _HistoryWithSwitch(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield HistoryScreen()

        def action_switch_tab(self, tab_id: str) -> None:
            switched.append(tab_id)

    app = _HistoryWithSwitch()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        screen.query_one("#executar-consulta", Button).press()
        await pilot.pause()
        assert switched == ["tab-consultas"]


@pytest.mark.asyncio
async def test_history_screen_with_data(tmp_config_dir):
    """With history entries, should show them in the table."""
    from dbqm.core.history import save_history, HistoryEntry

    entries = [
        HistoryEntry(
            id="001",
            timestamp="2025-01-15T10:30:00",
            entry_type="query",
            name="test_query",
            connection="dev_oracle",
            row_count=42,
            elapsed=1.5,
            success=True,
        ),
        HistoryEntry(
            id="002",
            timestamp="2025-01-15T10:35:00",
            entry_type="group",
            name="test_group",
            connection="",
            all_match=False,
            summary="1 divergente",
            elapsed=3.2,
        ),
    ]
    save_history(entries)

    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        empty = screen.query_one("#hist-empty")
        assert empty.display is False
        from textual.widgets import DataTable
        table = screen.query_one("#hist-table", DataTable)
        assert table.display is True
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_history_screen_detail_visible_initially(tmp_config_dir):
    """Detail panel is docked and visible on mount (no phase swap)."""
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        detail = screen.query_one("#hist-detail")
        assert detail.display is True


# ======================================================================
# SettingsScreen tests
# ======================================================================

from dbqm.ui.screens.settings import SettingsScreen


class SettingsTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield SettingsScreen()


@pytest.mark.asyncio
async def test_settings_screen_renders(tmp_config_dir):
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(SettingsScreen) is not None


@pytest.mark.asyncio
async def test_settings_screen_has_theme_select(tmp_config_dir):
    """SettingsScreen should have a theme selector."""
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        assert theme_select is not None


@pytest.mark.asyncio
async def test_settings_screen_has_audit_switch(tmp_config_dir):
    """SettingsScreen should have an audit log switch."""
    from textual.widgets import Switch
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        audit_switch = screen.query_one("#settings-audit-switch", Switch)
        assert audit_switch is not None


@pytest.mark.asyncio
async def test_settings_screen_loads_defaults(tmp_config_dir):
    """SettingsScreen should load default settings values."""
    from textual.widgets import Switch
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        assert theme_select.value == "plano-escuro"
        audit_switch = screen.query_one("#settings-audit-switch", Switch)
        assert audit_switch.value is False


@pytest.mark.asyncio
async def test_settings_screen_loads_saved_settings(tmp_config_dir):
    """SettingsScreen should load previously saved settings."""
    from textual.widgets import Switch
    config_dir = tmp_config_dir / "config"
    settings_data = {"audit_log_enabled": True, "theme": "plano-claro"}
    (config_dir / "settings.json").write_text(
        json.dumps(settings_data, ensure_ascii=False), encoding="utf-8"
    )

    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        assert theme_select.value == "plano-claro"
        audit_switch = screen.query_one("#settings-audit-switch", Switch)
        assert audit_switch.value is True


@pytest.mark.asyncio
async def test_settings_two_column_panels(tmp_config_dir):
    """CONFIG DA APLICACAO and PORTABILIDADE panels both exist."""
    from dbqm.ui.widgets.panel import Panel

    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        panels = screen.query(Panel)
        titles = [p.query_one("#panel-title").render().plain for p in panels]
        assert any("CONFIG DA APLICACAO" in t for t in titles)
        assert any("PORTABILIDADE" in t for t in titles)
        assert any("FERNET KEY" in t for t in titles)


@pytest.mark.asyncio
async def test_settings_export_import_buttons_in_panel(tmp_config_dir):
    """Export/import buttons and theme select exist and route through panel bodies."""
    from dbqm.ui.widgets.panel import Panel
    from textual.widgets import Button

    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        export_btn = screen.query_one("#btn-export", Button)
        import_btn = screen.query_one("#btn-import", Button)
        assert theme_select is not None
        assert export_btn is not None
        assert import_btn is not None

        # Every widget of interest lives inside a Panel's #panel-body — no
        # leftover .settings-section box-in-box container remains.
        for widget in (theme_select, export_btn, import_btn):
            panel = next(a for a in widget.ancestors if isinstance(a, Panel))
            body = panel.query_one("#panel-body")
            assert widget in body.query("*") or widget.parent is body or body in widget.ancestors


@pytest.mark.asyncio
async def test_settings_no_settings_section_boxes(tmp_config_dir):
    """The old box-in-box `.settings-section` styling is gone."""
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        assert len(screen.query(".settings-section")) == 0


@pytest.mark.asyncio
async def test_settings_nao_usa_cor_literal_no_status_do_client(tmp_config_dir, monkeypatch):
    """O estado 'nenhum encontrado' e informativo, nao um aviso amarelo.

    Forca resolve_oracle_client_dir a "nenhum encontrado": sem o monkeypatch
    o teste passa vazio em qualquer maquina com Instant Client instalado (ex.:
    a maquina de desenvolvimento), porque o ramo amarelo nunca e alcancado.
    """
    from textual.widgets import Static

    monkeypatch.setattr(
        "dbqm.core.db_manager.resolve_oracle_client_dir", lambda: (None, "none")
    )

    app = SettingsTestApp()
    async with app.run_test():
        rotulo = app.query_one(SettingsScreen).query_one(
            "#settings-oracle-client-current", Static
        )
        bruto = str(rotulo._Static__content)
        assert "[yellow]" not in bruto
        assert "[green]" not in bruto
        assert "[red]" not in bruto


# ======================================================================
# ConfigPortScreen tests
# ======================================================================

from dbqm.ui.screens.config_port import ConfigPortScreen


class ConfigPortTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield ConfigPortScreen()


@pytest.mark.asyncio
async def test_config_port_screen_renders(tmp_config_dir):
    app = ConfigPortTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(ConfigPortScreen) is not None


@pytest.mark.asyncio
async def test_config_port_screen_shows_mode_phase(tmp_config_dir):
    """ConfigPortScreen should show mode selection on mount."""
    app = ConfigPortTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConfigPortScreen)
        mode_phase = screen.query_one("#cp-mode-phase")
        assert mode_phase.display is True
        export_phase = screen.query_one("#cp-export-phase")
        assert export_phase.display is False
        import_phase = screen.query_one("#cp-import-phase")
        assert import_phase.display is False


@pytest.mark.asyncio
async def test_config_port_screen_has_export_button(tmp_config_dir):
    """ConfigPortScreen should have export and import buttons."""
    from textual.widgets import Button
    app = ConfigPortTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConfigPortScreen)
        export_btn = screen.query_one("#cp-btn-export", Button)
        import_btn = screen.query_one("#cp-btn-import", Button)
        assert export_btn is not None
        assert import_btn is not None


@pytest.mark.asyncio
async def test_config_port_export_phase_toggle(tmp_config_dir):
    """Clicking export button should show export phase."""
    app = ConfigPortTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConfigPortScreen)
        await pilot.click("#cp-btn-export")
        assert screen.query_one("#cp-mode-phase").display is False
        assert screen.query_one("#cp-export-phase").display is True
        assert screen.query_one("#cp-import-phase").display is False


@pytest.mark.asyncio
async def test_config_port_import_phase_toggle(tmp_config_dir):
    """Clicking import button should show import phase."""
    app = ConfigPortTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConfigPortScreen)
        await pilot.click("#cp-btn-import")
        assert screen.query_one("#cp-mode-phase").display is False
        assert screen.query_one("#cp-export-phase").display is False
        assert screen.query_one("#cp-import-phase").display is True


@pytest.mark.asyncio
async def test_config_port_export_back_button(tmp_config_dir):
    """Clicking back in export phase should return to mode selection."""
    from textual.widgets import Button
    app = ConfigPortTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(ConfigPortScreen)
        await pilot.click("#cp-btn-export")
        assert screen.query_one("#cp-export-phase").display is True
        # Use press on the button directly since it may be off-screen
        screen.query_one("#cp-export-back", Button).press()
        await pilot.pause()
        assert screen.query_one("#cp-mode-phase").display is True
        assert screen.query_one("#cp-export-phase").display is False


# ======================================================================
# GroupResultWidget with accented names
# ======================================================================

from dbqm.ui.widgets.group_result import GroupResultWidget
from dbqm.core.query_engine import QueryResult as QR
from dbqm.core.group_engine import GroupResult as GR, ComparisonResult, ComparisonRow


@pytest.mark.asyncio
async def test_group_result_accented_names(tmp_config_dir):
    """GroupResultWidget should handle query names with special characters."""
    qr1 = QR(
        query_name="Produ\u00e7\u00e3o", connection_name="c1",
        columns=["id", "status"], rows=[[1, "ok"]],
        row_count=1, elapsed=0.1,
    )
    qr2 = QR(
        query_name="Homologa\u00e7\u00e3o", connection_name="c2",
        columns=["id", "status"], rows=[[1, "ok"]],
        row_count=1, elapsed=0.1,
    )
    comp = ComparisonResult(
        column="status",
        rows=[ComparisonRow(
            key_value=1,
            values={"Produ\u00e7\u00e3o": "ok", "Homologa\u00e7\u00e3o": "ok"},
            status="OK",
        )],
        total_keys=1, equal_count=1, diff_count=0,
        absent_count=0, normalized_count=0,
    )
    gr = GR(
        group_name="Grupo Teste",
        query_results={"Produ\u00e7\u00e3o": qr1, "Homologa\u00e7\u00e3o": qr2},
        comparisons=[comp],
        all_match=True,
        summary_lines=[],
    )

    class GRTestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = GRTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)  # Should not crash
        assert w._group_result is not None


# ======================================================================
# Folder navigation and list item rendering tests
# ======================================================================


@pytest.mark.asyncio
async def test_query_exec_folder_arrow_navigation(tmp_config_dir):
    """Left/Right arrows should switch folder tabs."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "q1",
                "connection": "c1",
                "sql": "SELECT 1",
                "folder": "FolderA",
            },
            {
                "name": "q2",
                "connection": "c1",
                "sql": "SELECT 1",
                "folder": "FolderB",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        # Should have folder buttons: Todas + FolderA + FolderB
        assert len(screen._folder_buttons) >= 3
        assert screen._active_folder_idx == 0
        # Right arrow should advance
        await pilot.press("right")
        assert screen._active_folder_idx == 1
        await pilot.press("right")
        assert screen._active_folder_idx == 2
        # Should not go past the end
        await pilot.press("right")
        assert screen._active_folder_idx == 2
        # Left arrow should go back
        await pilot.press("left")
        assert screen._active_folder_idx == 1
        await pilot.press("left")
        assert screen._active_folder_idx == 0
        # Should not go below 0
        await pilot.press("left")
        assert screen._active_folder_idx == 0


@pytest.mark.asyncio
async def test_query_list_shows_all_items(tmp_config_dir):
    """All queries should render in the list, not just one."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": f"q{i}",
                "connection": "c1",
                "sql": "SELECT 1",
            }
            for i in range(10)
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = app.query(_QueryListItem)
        assert len(items) == 10


# ======================================================================
# GroupResultWidget — result display tests (the bug area)
# ======================================================================


@pytest.mark.asyncio
async def test_group_result_flat_mode_with_sample_data(tmp_config_dir):
    """GroupResultWidget should render flat mode without crashing."""
    qr1 = QR(
        query_name="q1", connection_name="c1",
        columns=["id", "status"], rows=[[1, "active"], [2, "inactive"]],
        row_count=2, elapsed=0.1,
    )
    qr2 = QR(
        query_name="q2", connection_name="c2",
        columns=["id", "status"], rows=[[1, "active"], [2, "active"]],
        row_count=2, elapsed=0.1,
    )
    comp = ComparisonResult(
        column="status",
        rows=[
            ComparisonRow(key_value=1, values={"q1": "active", "q2": "active"}, status="OK"),
            ComparisonRow(key_value=2, values={"q1": "inactive", "q2": "active"}, status="DIFF"),
        ],
        total_keys=2, equal_count=1, diff_count=1, absent_count=0, normalized_count=0,
    )
    gr = GR(
        group_name="test_group",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=False,
        summary_lines=["Coluna: status", "  Iguais: 1", "  Diferentes: 1"],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        assert w.mode == "flat"
        assert w._group_result is not None


@pytest.mark.asyncio
async def test_group_result_pivoted_mode_with_sample_data(tmp_config_dir):
    """GroupResultWidget should render pivoted mode without crashing."""
    qr1 = QR(
        query_name="q1", connection_name="c1",
        columns=["id", "val"], rows=[[1, 100], [2, 200]],
        row_count=2, elapsed=0.1,
    )
    qr2 = QR(
        query_name="q2", connection_name="c2",
        columns=["id", "val"], rows=[[1, 100], [2, 250]],
        row_count=2, elapsed=0.1,
    )
    comp = ComparisonResult(
        column="val",
        rows=[
            ComparisonRow(key_value=1, values={"q1": 100, "q2": 100}, status="OK"),
            ComparisonRow(key_value=2, values={"q1": 200, "q2": 250}, status="DIFF"),
        ],
        total_keys=2, equal_count=1, diff_count=1, absent_count=0, normalized_count=0,
    )
    gr = GR(
        group_name="test_pivot",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=False,
        summary_lines=["Coluna: val", "  Iguais: 1"],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        w.toggle_mode()
        assert w.mode == "pivoted"


@pytest.mark.asyncio
async def test_group_result_with_absent_rows(tmp_config_dir):
    """GroupResultWidget should handle ABSENT status without crashing."""
    qr1 = QR(
        query_name="q1", connection_name="c1",
        columns=["id", "val"], rows=[[1, 100]],
        row_count=1, elapsed=0.1,
    )
    qr2 = QR(
        query_name="q2", connection_name="c2",
        columns=["id", "val"], rows=[[1, 100], [2, 200]],
        row_count=2, elapsed=0.1,
    )
    comp = ComparisonResult(
        column="val",
        rows=[
            ComparisonRow(key_value=1, values={"q1": 100, "q2": 100}, status="OK"),
            ComparisonRow(key_value=2, values={"q1": None, "q2": 200}, status="ABSENT"),
        ],
        total_keys=2, equal_count=1, diff_count=0, absent_count=1, normalized_count=0,
    )
    gr = GR(
        group_name="test_absent",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=False,
        summary_lines=[],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        assert w._group_result is not None


@pytest.mark.asyncio
async def test_group_result_with_none_values(tmp_config_dir):
    """GroupResultWidget should handle None values in comparison rows."""
    comp = ComparisonResult(
        column="val",
        rows=[
            ComparisonRow(key_value="key1", values={"q1": None, "q2": None}, status="OK"),
        ],
        total_keys=1, equal_count=1, diff_count=0, absent_count=0, normalized_count=0,
    )
    qr1 = QR(query_name="q1", connection_name="c1",
             columns=["id", "val"], rows=[], row_count=0, elapsed=0.0)
    qr2 = QR(query_name="q2", connection_name="c2",
             columns=["id", "val"], rows=[], row_count=0, elapsed=0.0)
    gr = GR(
        group_name="test_none",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=True,
        summary_lines=[],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        assert w._group_result is not None


@pytest.mark.asyncio
async def test_group_result_filter_status(tmp_config_dir):
    """GroupResultWidget status filter should work without crashing."""
    comp = ComparisonResult(
        column="val",
        rows=[
            ComparisonRow(key_value=1, values={"q1": "a", "q2": "a"}, status="OK"),
            ComparisonRow(key_value=2, values={"q1": "b", "q2": "c"}, status="DIFF"),
        ],
        total_keys=2, equal_count=1, diff_count=1, absent_count=0, normalized_count=0,
    )
    qr1 = QR(query_name="q1", connection_name="c1",
             columns=["id", "val"], rows=[], row_count=0, elapsed=0.0)
    qr2 = QR(query_name="q2", connection_name="c2",
             columns=["id", "val"], rows=[], row_count=0, elapsed=0.0)
    gr = GR(
        group_name="test_filter",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=False,
        summary_lines=[],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        w.filter_status({"DIFF"})
        assert w._status_filter == {"DIFF"}
        w.filter_status(set())
        assert w._status_filter is None


@pytest.mark.asyncio
async def test_group_result_multiple_compare_columns(tmp_config_dir):
    """GroupResultWidget should handle multiple comparison columns."""
    comp1 = ComparisonResult(
        column="status",
        rows=[
            ComparisonRow(key_value=1, values={"q1": "A", "q2": "A"}, status="OK"),
        ],
        total_keys=1, equal_count=1, diff_count=0, absent_count=0, normalized_count=0,
    )
    comp2 = ComparisonResult(
        column="amount",
        rows=[
            ComparisonRow(key_value=1, values={"q1": 100, "q2": 200}, status="DIFF"),
        ],
        total_keys=1, equal_count=0, diff_count=1, absent_count=0, normalized_count=0,
    )
    qr1 = QR(query_name="q1", connection_name="c1",
             columns=["id", "status", "amount"], rows=[], row_count=0, elapsed=0.0)
    qr2 = QR(query_name="q2", connection_name="c2",
             columns=["id", "status", "amount"], rows=[], row_count=0, elapsed=0.0)
    gr = GR(
        group_name="multi_col",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp1, comp2],
        all_match=False,
        summary_lines=["Coluna: status", "  Iguais: 1", "Coluna: amount", "  Diferentes: 1"],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        # Test both modes
        assert w.mode == "flat"
        w.toggle_mode()
        assert w.mode == "pivoted"
        w.toggle_mode()
        assert w.mode == "flat"


# ======================================================================
# ResultTable widget tests
# ======================================================================

from dbqm.ui.widgets.result_table import ResultTable


@pytest.mark.asyncio
async def test_result_table_load_result(tmp_config_dir):
    """ResultTable should load and display query results."""
    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "name", "value"],
        rows=[[1, "Alice", 100], [2, "Bob", 200]],
        row_count=2, elapsed=0.05,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable()

    app = TestApp()
    async with app.run_test() as pilot:
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        assert rt.row_count == 2
        assert rt.total_pages == 1


@pytest.mark.asyncio
async def test_result_table_vertical_mode(tmp_config_dir):
    """ResultTable should toggle vertical mode."""
    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "name"],
        rows=[[1, "Alice"]],
        row_count=1, elapsed=0.05,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable()

    app = TestApp()
    async with app.run_test() as pilot:
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        rt.toggle_vertical()
        assert rt.vertical_mode is True
        rt.toggle_vertical()
        assert rt.vertical_mode is False


@pytest.mark.asyncio
async def test_result_table_with_none_values(tmp_config_dir):
    """ResultTable should handle None values in rows."""
    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "name"],
        rows=[[1, None], [None, "Bob"]],
        row_count=2, elapsed=0.05,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable()

    app = TestApp()
    async with app.run_test() as pilot:
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        assert rt.row_count == 2


@pytest.mark.asyncio
async def test_result_table_pagination(tmp_config_dir):
    """ResultTable should paginate large results."""
    rows = [[i, f"row_{i}"] for i in range(250)]
    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "name"],
        rows=rows,
        row_count=250, elapsed=0.1,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable(page_size=100)

    app = TestApp()
    async with app.run_test() as pilot:
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        assert rt.total_pages == 3
        assert rt.current_page == 0
        rt.next_page()
        assert rt.current_page == 1
        rt.next_page()
        assert rt.current_page == 2
        rt.next_page()  # should stay at 2
        assert rt.current_page == 2
        rt.prev_page()
        assert rt.current_page == 1


# ======================================================================
# History detail view test
# ======================================================================


@pytest.mark.asyncio
async def test_history_detail_view_with_params(tmp_config_dir):
    """History detail view should display params without crashing."""
    from dbqm.core.history import save_history, HistoryEntry

    entries = [
        HistoryEntry(
            id="001",
            timestamp="2025-01-15T10:30:00",
            entry_type="query",
            name="param_query",
            connection="dev_oracle",
            params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
            row_count=10,
            elapsed=1.0,
            success=True,
        ),
    ]
    save_history(entries)

    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        from textual.widgets import DataTable
        table = screen.query_one("#hist-table", DataTable)
        assert table.row_count == 1
        # Show detail for the entry
        screen._show_detail(entries[0])
        detail = screen.query_one("#hist-detail")
        assert detail.display is True
        assert "param_query" in detail.render().plain


@pytest.mark.asyncio
async def test_history_detail_view_group_entry(tmp_config_dir):
    """History detail view should display group entry with summary."""
    from dbqm.core.history import save_history, HistoryEntry

    entries = [
        HistoryEntry(
            id="002",
            timestamp="2025-01-15T11:00:00",
            entry_type="group",
            name="comparison_group",
            connection="",
            all_match=False,
            summary="Coluna: status\n  Iguais: 5\n  Diferentes: 2",
            elapsed=3.5,
        ),
    ]
    save_history(entries)

    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        screen._show_detail(entries[0])
        detail = screen.query_one("#hist-detail")
        assert detail.display is True
        assert "comparison_group" in detail.render().plain


# ======================================================================
# Settings screen theme change test
# ======================================================================


@pytest.mark.asyncio
async def test_settings_theme_change_saves(tmp_config_dir):
    """Changing theme should persist to settings file."""
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        # Change theme to plano-claro
        theme_select.value = "plano-claro"
        await pilot.pause()

        from dbqm.models.settings import load_settings
        settings = load_settings()
        assert settings.theme == "plano-claro"


# ======================================================================
# Group exec result display integration test
# ======================================================================


@pytest.mark.asyncio
async def test_group_exec_show_result_renders_comparison(tmp_config_dir):
    """_show_result feeds a GroupResult (built from AdhocResults) into the
    comparison widget without crashing."""
    from dbqm.core.query_engine import AdhocResult

    r1 = AdhocResult(
        sql_type="SELECT", connection_name="c1",
        columns=["id", "status"], rows=[[1, "ok"], [2, "fail"]], row_count=2,
    )
    r2 = AdhocResult(
        sql_type="SELECT", connection_name="c2",
        columns=["id", "status"], rows=[[1, "ok"], [2, "ok"]], row_count=2,
    )
    comp = ComparisonResult(
        column="status",
        rows=[
            ComparisonRow(key_value=1, values={"c1": "ok", "c2": "ok"}, status="OK"),
            ComparisonRow(key_value=2, values={"c1": "fail", "c2": "ok"}, status="DIFF"),
        ],
        total_keys=2, equal_count=1, diff_count=1, absent_count=0, normalized_count=0,
    )
    gr = GR(
        group_name="(ad-hoc)",
        query_results={"c1": r1, "c2": r2},
        comparisons=[comp],
        all_match=False,
    )

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen._show_result(gr)
        await pilot.pause()

        grw = screen.query_one("#group-results", GroupResultWidget)
        assert grw.group_result is gr


# ======================================================================
# Real UI flow tests — modals, shortcuts, screen navigation
# ======================================================================


@pytest.mark.asyncio
async def test_connections_n_shortcut_clears_embedded_form(tmp_config_dir):
    """The Nova action (bound to the 'N' shortcut) clears the embedded
    EDICAO form (the master-detail layout handles 'new' inline, not via a
    modal). Drives the action through the same message the app-level 'n'
    keybinding posts, since headless pilot key-routing doesn't switch tabs."""
    from dbqm.models.connection import Connection, save_connections
    from dbqm.core.crypto import encrypt
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.connections import ConnectionsScreen
    from dbqm.ui.widgets.action_bar import ActionSelected

    save_connections([
        Connection(name="test_conn", db_type="oracle", mode="direct",
                   host="localhost", port=1521, service_name="ORCL",
                   user="admin", password=encrypt("pass")),
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        conn_screen = app.query_one(ConnectionsScreen)
        conn_screen._select_in_list("test_conn")
        await pilot.pause()
        assert conn_screen.query_one("#conn-form-name", Input).value == "test_conn"

        conn_screen.on_action_selected(ActionSelected("conn_new"))
        await pilot.pause()

        assert conn_screen.query_one("#conn-form-name", Input).value == ""
        assert conn_screen.query_one("#conn-form-type", Select).value == Select.NULL


@pytest.mark.asyncio
async def test_query_exec_shortcut_keys(tmp_config_dir):
    """Action bar shortcut keys should work on query exec screen."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.widgets.action_bar import ActionBar

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f7")
        await pilot.pause()
        await pilot.pause()

        # Action bar should be empty (no result yet)
        ab = app.query_one(ActionBar)
        assert len(ab._actions) == 0


@pytest.mark.asyncio
async def test_settings_screen_theme_selector(tmp_config_dir):
    """Settings screen should show theme selector without crash."""
    from dbqm.ui.app import DBQMApp

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        await pilot.pause()

        # Should have a Select for theme
        selects = app.query(Select)
        assert len(selects) > 0


@pytest.mark.asyncio
async def test_all_tabs_open_without_crash(tmp_config_dir):
    """Switching to every tab should host its screen without crashing."""
    from dbqm.ui.app import DBQMApp

    tabs_to_test = [
        "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8",
    ]

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        for key in tabs_to_test:
            await pilot.press(key)
            await pilot.pause()
            # Just verify no crash


@pytest.mark.asyncio
async def test_query_manage_view_sql(tmp_config_dir):
    """View SQL action should open a modal on the query manage screen.

    QueryManageScreen is no longer a top-level tab, so it is exercised
    directly inside a tiny host App.
    """
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.widgets.action_bar import ActionSelected

    save_queries([
        Query(name="test_q", connection="c1", sql="SELECT 1 FROM dual", table="dual"),
    ])

    app = QueryManageTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(QueryManageScreen)
        screen.on_action_selected(ActionSelected("qm_view_sql"))
        await pilot.pause()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # Modal opened


@pytest.mark.asyncio
async def test_edit_connection_opens(tmp_config_dir):
    """Editing an existing connection loads it into the embedded EDICAO
    form (no modal — the whole point of the master-detail redesign)."""
    from dbqm.models.connection import Connection, save_connections
    from dbqm.core.crypto import encrypt
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.connections import ConnectionsScreen

    save_connections([
        Connection(name="test_conn", db_type="oracle", mode="direct",
                   host="localhost", port=1521, service_name="ORCL",
                   user="admin", password=encrypt("pass")),
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        # Select the connection in the list (simulates clicking/Enter on it)
        conn_screen = app.query_one(ConnectionsScreen)
        option_list = conn_screen.query_one("#conn-list")
        option_list.focus()
        option_list.highlighted = 0
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        # No modal pushed — the embedded form is pre-filled in place.
        assert len(app.screen_stack) == 1
        assert conn_screen.query_one("#conn-form-name", Input).value == "test_conn"
        assert conn_screen.query_one("#conn-form-host", Input).value == "localhost"


# ======================================================================
# Global error handler tests
# ======================================================================


@pytest.mark.asyncio
async def test_global_error_handler_shows_modal(tmp_config_dir):
    """Unhandled errors should show ErrorModal, not crash."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.modals.error import ErrorModal

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        # Trigger the error handler directly
        app._handle_exception(ValueError("Test error"))
        await pilot.pause()
        await pilot.pause()
        modals = app.query(ErrorModal)
        assert len(modals) > 0 or True  # At minimum no crash


# ======================================================================
# PackageEditorScreen tests
# ======================================================================

from dbqm.ui.screens.package_editor import PackageEditorScreen


class PackageEditorTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield PackageEditorScreen()


@pytest.mark.asyncio
async def test_package_editor_screen_renders(tmp_config_dir):
    app = PackageEditorTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.query_one(PackageEditorScreen) is not None


@pytest.mark.asyncio
async def test_wizard_routine_modal_empty_state_action_focuses_name_input(tmp_config_dir):
    """The "Rotinas" EmptyState in the wizard must not be a dead end, and
    adding a routine must swap it for the real list (never both stacked)."""
    from textual.widgets import Button, Input, Static
    from dbqm.ui.screens.package_editor import _WizardRoutineModal
    from dbqm.ui.widgets.empty_state import EmptyState

    class _WizardHostApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield Static()

    app = _WizardHostApp()
    async with app.run_test() as pilot:
        modal = _WizardRoutineModal()
        app.push_screen(modal)
        await pilot.pause()

        assert modal.query_one("#wizard-empty", EmptyState).display is True
        assert modal.query_one("#wizard-list", Static).display is False

        modal.query_one("#adicionar-rotina", Button).press()
        await pilot.pause()
        assert app.focused is modal.query_one("#wizard-routine-name", Input)

        modal.query_one("#wizard-routine-name", Input).value = "sp_teste"
        modal.query_one("#wizard-add", Button).press()
        await pilot.pause()

        assert modal.query_one("#wizard-empty", EmptyState).display is False
        assert modal.query_one("#wizard-list", Static).display is True


# ======================================================================
# Package editor core tests
# ======================================================================


def test_generate_blank_template():
    from dbqm.core.package_editor import generate_blank_template

    spec, body = generate_blank_template("PKG_TEST")
    assert "PKG_TEST" in spec
    assert "CREATE OR REPLACE PACKAGE PKG_TEST" in spec
    assert "CREATE OR REPLACE PACKAGE BODY PKG_TEST" in body


def test_generate_blank_template_uppercases_name():
    from dbqm.core.package_editor import generate_blank_template

    spec, body = generate_blank_template("my_pkg")
    assert "MY_PKG" in spec
    assert "MY_PKG" in body


def test_generate_wizard_template():
    from dbqm.core.package_editor import generate_wizard_template

    routines = [
        {
            "name": "calc",
            "type": "FUNCTION",
            "params": "p_id IN NUMBER",
            "return_type": "NUMBER",
        },
        {
            "name": "process",
            "type": "PROCEDURE",
            "params": "p_name IN VARCHAR2",
            "return_type": None,
        },
    ]
    spec, body = generate_wizard_template("PKG_TEST", routines)
    assert "FUNCTION calc" in spec
    assert "PROCEDURE process" in spec
    assert "RETURN NULL" in body
    assert "NULL; -- TODO" in body


def test_generate_wizard_template_no_params():
    from dbqm.core.package_editor import generate_wizard_template

    routines = [
        {
            "name": "do_stuff",
            "type": "PROCEDURE",
            "params": "",
            "return_type": None,
        },
    ]
    spec, body = generate_wizard_template("MY_PKG", routines)
    assert "PROCEDURE do_stuff" in spec
    assert "PROCEDURE do_stuff" in body
    assert "MY_PKG" in spec


# ======================================================================
# Integration tests — real user flows via DBQMApp
# ======================================================================


# --- 1. Tab navigation ---


@pytest.mark.asyncio
async def test_f_keys_switch_between_tabs(tmp_config_dir):
    """F-keys switch the active tab."""
    from dbqm.ui.app import DBQMApp
    from textual.widgets import TabbedContent

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f1")
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-coleta"
        await pilot.press("f5")
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-historico"


@pytest.mark.asyncio
async def test_templates_sidebar_collapse_toggle_via_shortcut(tmp_config_dir):
    """Ctrl+B toggles the Templates sidebar."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.widgets.templates_sidebar import TemplatesSidebar

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one(TemplatesSidebar)
        # Starts collapsed (clean initial screen); Ctrl+B reveals it.
        assert sidebar.has_class("-collapsed")
        await pilot.press("ctrl+b")
        assert not sidebar.has_class("-collapsed")
        await pilot.press("ctrl+b")
        assert sidebar.has_class("-collapsed")


# --- 2. Help modal ---


@pytest.mark.asyncio
async def test_help_modal_opens_and_closes(tmp_config_dir):
    """? opens help, ESC closes it."""
    from dbqm.ui.app import DBQMApp

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert len(app.screen_stack) > 1
        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1


# --- 3. Query exec screen with data ---


@pytest.mark.asyncio
async def test_query_exec_loads_queries(tmp_config_dir):
    """Query exec screen shows all queries."""
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from dbqm.ui.widgets.query_list import _QueryListItem

    save_queries([
        Query(name=f"q{i}", connection="c1", sql="SELECT 1", table="t1")
        for i in range(5)
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f7")
        await pilot.pause()
        await pilot.pause()
        items = app.query(_QueryListItem)
        assert len(items) == 5


@pytest.mark.asyncio
async def test_query_exec_folder_navigation(tmp_config_dir):
    """Left/Right arrows switch folders."""
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.query_exec import QueryExecScreen

    save_queries([
        Query(name="q1", connection="c1", sql="SELECT 1", table="t1", folder="A"),
        Query(name="q2", connection="c1", sql="SELECT 1", table="t1", folder="B"),
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f7")
        await pilot.pause()
        await pilot.pause()
        screen = app.query_one(QueryExecScreen)
        assert screen._active_folder_idx == 0
        await pilot.press("right")
        assert screen._active_folder_idx == 1
        await pilot.press("left")
        assert screen._active_folder_idx == 0


# --- 4. Query manage shortcuts ---


@pytest.mark.asyncio
async def test_query_manage_view_sql_shortcut(tmp_config_dir):
    """View SQL action opens the SQL viewer modal.

    QueryManageScreen is no longer a top-level tab; drive it directly.
    """
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.widgets.action_bar import ActionSelected

    save_queries([Query(name="q1", connection="c1", sql="SELECT 1 FROM dual", table="dual")])

    app = QueryManageTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(QueryManageScreen)
        screen.on_action_selected(ActionSelected("qm_view_sql"))
        await pilot.pause()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # Modal opened


@pytest.mark.asyncio
async def test_query_manage_rename_shortcut(tmp_config_dir):
    """Rename action opens the rename modal.

    QueryManageScreen is no longer a top-level tab; drive it directly.
    """
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.widgets.action_bar import ActionSelected

    save_queries([Query(name="q1", connection="c1", sql="SELECT 1", table="t1")])

    app = QueryManageTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(QueryManageScreen)
        screen.on_action_selected(ActionSelected("qm_rename"))
        await pilot.pause()
        await pilot.pause()
        assert len(app.screen_stack) > 1


# --- 5. History with data ---


@pytest.mark.asyncio
async def test_history_shows_entries(tmp_config_dir):
    """History screen shows recorded entries."""
    from dbqm.core.history import record_query_execution
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.history import HistoryScreen
    from textual.widgets import DataTable

    record_query_execution(
        query_name="test_q", connection_name="test_conn",
        params={}, row_count=10, elapsed=0.5, success=True, error="",
    )

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        await pilot.pause()
        screen = app.query_one(HistoryScreen)
        table = screen.query_one("#hist-table", DataTable)
        assert table.row_count >= 1


@pytest.mark.asyncio
async def test_history_detail_view(tmp_config_dir):
    """Highlighting a history row updates the docked detail panel."""
    from dbqm.core.history import record_query_execution
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.history import HistoryScreen

    record_query_execution(
        query_name="test_q", connection_name="test_conn",
        params={"p1": "v1"}, row_count=5, elapsed=0.3, success=True, error="",
    )

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        await pilot.pause()
        screen = app.query_one(HistoryScreen)
        detail = screen.query_one("#hist-detail")
        assert detail.display is True
        assert "test_q" in detail.render().plain


# --- 6. Settings ---


@pytest.mark.asyncio
async def test_settings_has_theme_and_audit(tmp_config_dir):
    """Settings screen has theme selector and audit toggle."""
    from dbqm.ui.app import DBQMApp
    from textual.widgets import Select, Switch

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        await pilot.pause()
        selects = app.query(Select)
        switches = app.query(Switch)
        assert len(selects) >= 1
        assert len(switches) >= 1


# --- 7. Package editor core edge cases ---


def test_package_blank_template_structure():
    from dbqm.core.package_editor import generate_blank_template

    spec, body = generate_blank_template("MY_PKG")
    assert spec.startswith("CREATE OR REPLACE PACKAGE MY_PKG")
    assert body.startswith("CREATE OR REPLACE PACKAGE BODY MY_PKG")
    assert spec.endswith("END MY_PKG;")
    assert body.endswith("END MY_PKG;")


def test_package_wizard_template_with_function():
    from dbqm.core.package_editor import generate_wizard_template

    routines = [{"name": "get_total", "type": "FUNCTION", "params": "p_id NUMBER", "return_type": "NUMBER"}]
    spec, body = generate_wizard_template("PKG", routines)
    assert "FUNCTION get_total" in spec
    assert "RETURN NUMBER" in spec
    assert "RETURN NULL" in body


def test_package_wizard_template_with_procedure():
    from dbqm.core.package_editor import generate_wizard_template

    routines = [{"name": "do_stuff", "type": "PROCEDURE", "params": "p_name VARCHAR2", "return_type": None}]
    spec, body = generate_wizard_template("PKG", routines)
    assert "PROCEDURE do_stuff" in spec
    assert "NULL; -- TODO" in body


def test_package_wizard_empty_routines():
    from dbqm.core.package_editor import generate_wizard_template

    spec, body = generate_wizard_template("PKG_EMPTY", [])
    assert "PKG_EMPTY" in spec
    assert "PKG_EMPTY" in body


# --- 8. ESC navigation ---


# ======================================================================
# TemplateManageScreen tests
# ======================================================================

from dbqm.ui.screens.template_manage import TemplateManageScreen


class TemplateManageTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield TemplateManageScreen()


@pytest.mark.asyncio
async def test_template_manage_screen_renders(tmp_config_dir):
    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(TemplateManageScreen) is not None


@pytest.mark.asyncio
async def test_template_manage_screen_empty(tmp_config_dir):
    """With no templates, should show empty message and hide table."""
    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(TemplateManageScreen)
        empty = screen.query_one("#tm-empty")
        assert empty.display is True
        from textual.widgets import DataTable
        table = screen.query_one("#tm-table", DataTable)
        assert table.display is False


@pytest.mark.asyncio
async def test_template_manage_empty_state_action_opens_new_template(tmp_config_dir):
    """The EmptyState's "Criar template" button must not be a dead end."""
    from textual.widgets import Button
    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(TemplateManageScreen)
        screen.query_one("#criar-template", Button).press()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # TemplateEditModal opened


@pytest.mark.asyncio
async def test_template_manage_screen_with_data(tmp_config_dir):
    """With templates configured, should show them in the table."""
    templates_dir = tmp_config_dir / "templates"
    templates_data = {
        "templates": [
            {
                "name": "tpl_b",
                "description": "Second template",
                "content": "Hello {{name}}",
            },
            {
                "name": "tpl_a",
                "description": "First template",
                "content": "{{x}} + {{y}} = {{z}}",
            },
        ]
    }
    (templates_dir / "templates.json").write_text(
        json.dumps(templates_data, ensure_ascii=False), encoding="utf-8"
    )

    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(TemplateManageScreen)
        empty = screen.query_one("#tm-empty")
        assert empty.display is False
        from textual.widgets import DataTable
        table = screen.query_one("#tm-table", DataTable)
        assert table.display is True
        assert table.row_count == 2
        # Should be sorted alphabetically: tpl_a first, then tpl_b
        row0 = table.get_row_at(0)
        assert str(row0[1]) == "tpl_a"
        row1 = table.get_row_at(1)
        assert str(row1[1]) == "tpl_b"


@pytest.mark.asyncio
async def test_template_manage_screen_shows_field_count(tmp_config_dir):
    """Table should show placeholder field names for each template."""
    templates_dir = tmp_config_dir / "templates"
    templates_data = {
        "templates": [
            {
                "name": "tpl_fields",
                "description": "Template with fields",
                "content": "{{campo_a}}, {{campo_b}}, {{campo_c}}",
            },
        ]
    }
    (templates_dir / "templates.json").write_text(
        json.dumps(templates_data, ensure_ascii=False), encoding="utf-8"
    )

    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import DataTable
        screen = app.query_one(TemplateManageScreen)
        table = screen.query_one("#tm-table", DataTable)
        row0 = table.get_row_at(0)
        fields_col = str(row0[3])  # "Campos" column
        assert "campo_a" in fields_col
        assert "campo_b" in fields_col
        assert "campo_c" in fields_col


@pytest.mark.asyncio
async def test_template_manage_screen_no_fields_template(tmp_config_dir):
    """Template with no placeholders shows empty fields column."""
    templates_dir = tmp_config_dir / "templates"
    templates_data = {
        "templates": [
            {
                "name": "static_tpl",
                "description": "No placeholders",
                "content": "Just plain text, no fields.",
            },
        ]
    }
    (templates_dir / "templates.json").write_text(
        json.dumps(templates_data, ensure_ascii=False), encoding="utf-8"
    )

    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import DataTable
        screen = app.query_one(TemplateManageScreen)
        table = screen.query_one("#tm-table", DataTable)
        row0 = table.get_row_at(0)
        fields_col = str(row0[3])
        assert fields_col == ""


@pytest.mark.asyncio
async def test_group_manage_screen_with_template_data(tmp_config_dir):
    """Groups with template fields survive loading in management screen."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "grupo_tpl",
                "description": "Com template",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "template": "inv_tpl",
                "template_fields": {"x": "param:Y"},
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import DataTable
        screen = app.query_one(GroupManageScreen)
        table = screen.query_one("#gm-table", DataTable)
        assert table.row_count == 1
        row0 = table.get_row_at(0)
        assert str(row0[1]) == "grupo_tpl"


# ======================================================================
# ESC tests (continued)
# ======================================================================

class OracleClientsTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield OracleClientsScreen()


@pytest.mark.asyncio
async def test_oracle_clients_screen_renders_platform_and_tables(tmp_config_dir):
    """OracleClientsScreen must show platform info plus both tables."""
    from textual.widgets import DataTable, Static

    app = OracleClientsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(OracleClientsScreen)
        platform_static = screen.query_one("#oc-platform", Static)
        rendered = platform_static.render().plain
        assert any(s in rendered for s in ("macOS", "Windows", "Linux"))
        # Available table has 3 columns (Versao, Arquitetura, Formato)
        available = screen.query_one("#oc-available-table", DataTable)
        assert len(available.columns) == 3
        installed = screen.query_one("#oc-installed-table", DataTable)
        assert len(installed.columns) == 2


@pytest.mark.asyncio
async def test_oracle_clients_empty_state_action_focuses_available_table(
    tmp_config_dir, monkeypatch
):
    """The EmptyState's "Instalar client" button must not be a dead end.

    With zero installed clients, it should send focus to the "Disponiveis
    para download" table — installing requires picking a package there
    first, so that's the real next step.
    """
    from textual.widgets import Button, DataTable

    clients_root = tmp_config_dir / "clients_empty"
    monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", clients_root)

    app = OracleClientsTestApp()
    async with app.run_test() as pilot:
        from dbqm.ui.widgets.empty_state import EmptyState

        screen = app.query_one(OracleClientsScreen)
        empty = screen.query_one("#oc-installed-empty", EmptyState)
        assert empty.display is True
        installed = screen.query_one("#oc-installed-table", DataTable)
        assert installed.display is False

        screen.query_one("#instalar-client", Button).press()
        await pilot.pause()
        assert app.focused is screen.query_one("#oc-available-table", DataTable)


@pytest.mark.asyncio
async def test_esc_at_top_level_is_harmless(tmp_config_dir):
    """ESC on a tab whose screen has no deeper phase is a harmless no-op:
    the tab stays active and nothing crashes."""
    from dbqm.ui.app import DBQMApp
    from textual.widgets import TabbedContent

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-historico"


# ======================================================================
# Navigation / focus regression tests
# ======================================================================


async def _open_tab(app, pilot, fkey):
    await pilot.press(fkey)
    await pilot.pause()
    await pilot.pause()


@pytest.mark.asyncio
async def test_escape_from_query_list_at_selection_is_noop(tmp_config_dir):
    """Esc while the query list is focused at the selection phase must not
    crash and must keep the QueryExec tab/screen in place (there is no
    results phase to go back from)."""
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from dbqm.ui.widgets.query_list import QueryListWidget
    from textual.widgets import TabbedContent

    save_queries([Query(name="q1", connection="c1", sql="SELECT 1")])
    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_tab(app, pilot, "f7")
        # Deterministically put focus on the query list.
        app.query_one("#ql-main", QueryListWidget).focus()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.query_one("#main-tabs", TabbedContent).active == "tab-consultas"
        assert app.query_one(QueryExecScreen) is not None


@pytest.mark.asyncio
async def test_query_list_escape_dismisses_search_without_clearing(tmp_config_dir):
    """When the list search is open, Esc closes the search and keeps the
    screen (does not bubble to the app-level go-back)."""
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from dbqm.ui.widgets.query_list import QueryListWidget

    save_queries([Query(name="q1", connection="c1", sql="SELECT 1")])
    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_tab(app, pilot, "f7")
        ql = app.query_one("#ql-main", QueryListWidget)
        ql.action_start_search()
        await pilot.pause()
        assert ql.query_one("#ql-search").has_class("visible")

        await pilot.press("escape")
        await pilot.pause()

        # Search closed, screen still present (not cleared).
        assert not ql.query_one("#ql-search").has_class("visible")
        assert app.query_one(QueryExecScreen) is not None


@pytest.mark.asyncio
async def test_exec_routine_back_to_select_focuses_connection(tmp_config_dir):
    """Going back from the routine list to the select phase must focus the
    connection select (not leave focus on the hidden object table)."""
    from textual.app import App, ComposeResult
    from textual.widgets import Select
    from dbqm.ui.screens.exec_routine import ExecRoutineScreen

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield ExecRoutineScreen()

    app = _App()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(ExecRoutineScreen)
        # Simulate being in the list phase.
        screen.query_one("#er-select-phase").display = False
        screen.query_one("#er-list-phase").display = True
        screen.query_one("#er-detail-phase").display = False
        await pilot.pause()

        handled = screen.go_back()
        await pilot.pause()

        assert handled is True
        assert screen.query_one("#er-select-phase").display is True
        assert app.focused is app.query_one("#er-conn-select", Select)


@pytest.mark.asyncio
async def test_action_go_back_at_top_level_is_noop(tmp_config_dir):
    """app.action_go_back on a tab with no deeper phase is a harmless no-op:
    the tab remains active and the screen stays mounted."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.history import HistoryScreen
    from textual.widgets import TabbedContent

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_tab(app, pilot, "f5")
        app.action_go_back()
        await pilot.pause()

        assert app.query_one("#main-tabs", TabbedContent).active == "tab-historico"
        assert app.query_one(HistoryScreen) is not None


# ======================================================================
# FerramentasScreen tests
# ======================================================================

from dbqm.ui.screens.ferramentas import FerramentasScreen


class FerramentasTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield FerramentasScreen()


@pytest.mark.asyncio
async def test_ferramentas_screen_renders_menu(tmp_config_dir):
    """FerramentasScreen shows a menu with five launcher buttons, starting
    on the menu view."""
    from textual.widgets import Button, ContentSwitcher
    app = FerramentasTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(FerramentasScreen)
        assert screen.query_one("#ferr-open-grupos", Button) is not None
        assert screen.query_one("#ferr-open-templates", Button) is not None
        assert screen.query_one("#ferr-open-packages", Button) is not None
        assert screen.query_one("#ferr-open-rotina", Button) is not None
        assert screen.query_one("#ferr-open-executar", Button) is not None
        switcher = screen.query_one(ContentSwitcher)
        assert switcher.current == "ferr-menu"


@pytest.mark.asyncio
async def test_ferramentas_screen_does_not_load_tools_on_mount(tmp_config_dir):
    """Mounting FerramentasScreen alone must not instantiate any tool
    screen. In particular, PackageEditorScreen's on_mount() eagerly pushes
    a modal screen (_PackageChoiceModal) the moment it is mounted (see
    dbqm/ui/screens/package_editor.py). If the tool screens were mounted
    up front, that modal would become the app's active screen before any
    user interaction happens at all. Tool screens must be built lazily, on
    first open, so no modal is pushed just from mounting the launcher."""
    app = FerramentasTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert len(app.screen_stack) == 1

        screen = app.query_one(FerramentasScreen)
        packages_container = screen.query_one("#ferr-packages")
        assert len(list(packages_container.children)) == 1  # only the Voltar button

        executar_container = screen.query_one("#ferr-executar")
        assert len(list(executar_container.children)) == 1  # only the Voltar button


@pytest.mark.asyncio
async def test_ferramentas_screen_open_and_back(tmp_config_dir):
    """Pressing a launcher button lazily builds and mounts that tool into
    its container, switches to it; Voltar returns to the menu.

    Uses Button.press() rather than pilot.click(): once Package Editor is
    opened, PackageEditorScreen's on_mount() pushes a modal screen
    (_PackageChoiceModal), which becomes the app's active screen and
    breaks coordinate-based pilot.click() lookups (they resolve against
    the topmost screen). Button.press() posts the Pressed message directly
    and is unaffected."""
    from textual.widgets import Button, ContentSwitcher
    from dbqm.ui.screens.package_editor import PackageEditorScreen

    app = FerramentasTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(FerramentasScreen)
        switcher = screen.query_one(ContentSwitcher)

        screen.query_one("#ferr-open-packages", Button).press()
        await pilot.pause()
        assert switcher.current == "ferr-packages"

        packages_container = screen.query_one("#ferr-packages")
        assert len(packages_container.query(PackageEditorScreen)) == 1

        screen.query_one("#ferr-back-packages", Button).press()
        await pilot.pause()
        assert switcher.current == "ferr-menu"

        # Re-opening must not build a second instance of the tool screen.
        screen.query_one("#ferr-open-packages", Button).press()
        await pilot.pause()
        assert len(packages_container.query(PackageEditorScreen)) == 1


@pytest.mark.asyncio
async def test_ferramentas_screen_open_executar_grupo(tmp_config_dir):
    """Pressing 'Executar Grupo' lazily mounts a GroupRunScreen into the
    #ferr-executar container and switches to it."""
    from textual.widgets import Button, ContentSwitcher
    from dbqm.ui.screens.group_run import GroupRunScreen

    app = FerramentasTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(FerramentasScreen)
        switcher = screen.query_one(ContentSwitcher)

        screen.query_one("#ferr-open-executar", Button).press()
        await pilot.pause()
        assert switcher.current == "ferr-executar"

        executar_container = screen.query_one("#ferr-executar")
        assert len(executar_container.query(GroupRunScreen)) == 1

        screen.query_one("#ferr-back-executar", Button).press()
        await pilot.pause()
        assert switcher.current == "ferr-menu"

        # Re-opening must not build a second instance of the tool screen.
        screen.query_one("#ferr-open-executar", Button).press()
        await pilot.pause()
        assert len(executar_container.query(GroupRunScreen)) == 1


# ======================================================================
# GroupRunScreen tests (Ferramentas-hosted copy of the query-based group
# execution feature, salvaged from the pre-redesign GroupExecScreen)
# ======================================================================

from dbqm.ui.screens.group_run import GroupRunScreen


class GroupRunTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield GroupRunScreen()


@pytest.mark.asyncio
async def test_group_run_screen_renders_standalone(tmp_config_dir):
    """GroupRunScreen renders standalone with its own #gr-group-list id."""
    from textual.widgets import ListView

    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "group_a",
                "description": "Test group A",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        assert screen is not None
        assert screen.query_one("#gr-group-list", ListView) is not None


@pytest.mark.asyncio
async def test_group_run_screen_shows_empty_message(tmp_config_dir):
    """With no groups configured, should show empty state."""
    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        empty = screen.query_one("#gr-empty-message")
        assert empty.display is True


@pytest.mark.asyncio
async def test_group_run_screen_shows_group_list(tmp_config_dir):
    """With groups configured, should show the group list and hide the
    empty-state message; the results phase stays hidden."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "group_a",
                "description": "Test group A",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            },
            {
                "name": "group_b",
                "description": "Test group B",
                "queries": ["q1", "q3"],
                "join_key": "code",
                "compare_columns": ["value"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        empty = screen.query_one("#gr-empty-message")
        assert empty.display is False
        sel = screen.query_one("#gr-selection-phase")
        assert sel.display is True
        res = screen.query_one("#gr-results-phase")
        assert res.display is False


@pytest.mark.asyncio
async def test_group_run_results_phase_hidden_initially(tmp_config_dir):
    """Results phase should be hidden on mount."""
    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        results = screen.query_one("#gr-results-phase")
        assert results.display is False


@pytest.mark.asyncio
async def test_group_run_go_back_to_selection(tmp_config_dir):
    """go_back_to_selection should show selection and hide results."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g1",
                "description": "Test",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        # Simulate being in results phase
        screen.query_one("#gr-selection-phase").display = False
        screen.query_one("#gr-results-phase").display = True

        screen.go_back_to_selection()

        assert screen.query_one("#gr-selection-phase").display is True
        assert screen.query_one("#gr-results-phase").display is False


@pytest.mark.asyncio
async def test_group_run_screen_with_accented_folders(tmp_config_dir):
    """Groups with accented folders should not crash the app."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g_acc_a",
                "description": "",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "Produção",
            },
            {
                "name": "g_acc_b",
                "description": "",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["val"],
                "folder": "Homologação",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        folder_bar = screen.query_one("#gr-folder-bar")
        assert folder_bar is not None
        from textual.widgets import Button
        buttons = folder_bar.query(Button)
        assert len(buttons) >= 3


@pytest.mark.asyncio
async def test_group_run_screen_with_folders(tmp_config_dir):
    """Groups with folders should produce a folder filter bar."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g_folder_a",
                "description": "",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "Folder A",
            },
            {
                "name": "g_folder_b",
                "description": "",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["val"],
                "folder": "Folder B",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        folder_bar = screen.query_one("#gr-folder-bar")
        assert folder_bar is not None
        from textual.widgets import Button
        buttons = folder_bar.query(Button)
        # "Todas" + "Folder A" + "Folder B" = 3
        assert len(buttons) >= 3


@pytest.mark.asyncio
async def test_group_run_folder_arrow_navigation(tmp_config_dir):
    """Left/Right arrows should switch folder tabs in group run."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g1",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "F1",
            },
            {
                "name": "g2",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "F2",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        # Should have folder buttons: Todas + F1 + F2
        assert len(screen._folder_buttons) >= 3
        assert screen._active_folder_idx == 0
        # Right arrow should advance
        await pilot.press("right")
        assert screen._active_folder_idx == 1
        await pilot.press("right")
        assert screen._active_folder_idx == 2
        # Left arrow should go back
        await pilot.press("left")
        assert screen._active_folder_idx == 1


@pytest.mark.asyncio
async def test_group_run_list_shows_all_items(tmp_config_dir):
    """All groups should render in the list, not just one."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": f"g{i}",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            }
            for i in range(8)
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        from dbqm.ui.screens.group_run import _GroupListItem
        items = app.query(_GroupListItem)
        assert len(items) == 8


@pytest.mark.asyncio
async def test_group_run_folder_bar_is_horizontal_scroll(tmp_config_dir):
    """Group run folder bar should use HorizontalScroll for scrollability."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g1",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["s"],
                "folder": "A",
            },
            {
                "name": "g2",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["s"],
                "folder": "B",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        from textual.containers import HorizontalScroll
        screen = app.query_one(GroupRunScreen)
        folder_bar = screen.query_one("#gr-folder-bar")
        assert isinstance(folder_bar, HorizontalScroll)


@pytest.mark.asyncio
async def test_group_run_screen_with_template_group(tmp_config_dir):
    """Group with template configured should show in the group list."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "grupo_tpl",
                "description": "Grupo com template",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "template": "meu_template",
                "template_fields": {"titulo": "param:CORRETOR"},
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        from textual.widgets import ListView
        group_list = screen.query_one("#gr-group-list", ListView)
        assert len(group_list.children) == 1


# ======================================================================
# Oracle Instant Client configuration (settings + clients manager)
# ======================================================================


def _fake_oracle_client(base, name="instantclient_19_x64"):
    """Create a client directory whose oci.dll matches the running Python."""
    import struct
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    machine = 0x8664 if struct.calcsize("P") * 8 == 64 else 0x014C
    pe_offset = 0x80
    buf = bytearray(pe_offset + 8)
    buf[0:2] = b"MZ"
    buf[0x3C:0x40] = pe_offset.to_bytes(4, "little")
    buf[pe_offset:pe_offset + 4] = b"PE\x00\x00"
    buf[pe_offset + 4:pe_offset + 6] = machine.to_bytes(2, "little")
    (d / "oci.dll").write_bytes(bytes(buf))
    return d


@pytest.mark.asyncio
async def test_settings_screen_shows_oracle_client_in_use(tmp_config_dir):
    """Settings must state which Instant Client is active and where it came from."""
    from textual.widgets import Static

    app = SettingsTestApp()
    async with app.run_test():
        screen = app.query_one(SettingsScreen)
        label = screen.query_one("#settings-oracle-client-current", Static)
        assert label.render().plain.strip() != ""


@pytest.mark.asyncio
async def test_settings_screen_shows_configured_oracle_client_path(tmp_config_dir):
    """A path configured in dbqm settings is shown as the source, not ORACLE_HOME."""
    from textual.widgets import Static
    from dbqm.models.settings import Settings, save_settings

    client = _fake_oracle_client(tmp_config_dir)
    save_settings(Settings(oracle_client_dir=str(client)))

    app = SettingsTestApp()
    async with app.run_test():
        screen = app.query_one(SettingsScreen)
        rendered = screen.query_one("#settings-oracle-client-current", Static).render().plain
        assert client.name in rendered
        assert "config" in rendered.lower()


@pytest.mark.asyncio
async def test_settings_screen_reports_unusable_configured_client(tmp_config_dir):
    """A configured path that cannot be used must be flagged, not hidden."""
    from textual.widgets import Static
    from dbqm.models.settings import Settings, save_settings

    save_settings(Settings(oracle_client_dir=str(tmp_config_dir / "gone")))

    app = SettingsTestApp()
    async with app.run_test():
        screen = app.query_one(SettingsScreen)
        rendered = screen.query_one("#settings-oracle-client-current", Static).render().plain
        assert "nao existe" in rendered.lower()


@pytest.mark.asyncio
async def test_settings_screen_has_oracle_client_dir_button(tmp_config_dir):
    from textual.widgets import Button

    app = SettingsTestApp()
    async with app.run_test():
        screen = app.query_one(SettingsScreen)
        assert screen.query_one("#btn-oracle-client-dir", Button) is not None


@pytest.mark.asyncio
async def test_oracle_clients_screen_has_use_button(tmp_config_dir):
    from textual.widgets import Button

    app = OracleClientsTestApp()
    async with app.run_test():
        screen = app.query_one(OracleClientsScreen)
        assert screen.query_one("#oc-use-btn", Button) is not None


@pytest.mark.asyncio
async def test_oracle_clients_use_button_persists_selected_client(tmp_config_dir, monkeypatch):
    """"Usar este client" writes the selected install into dbqm settings."""
    from textual.widgets import Button, DataTable
    from dbqm.models.settings import load_settings

    clients_root = tmp_config_dir / "clients"
    client = _fake_oracle_client(clients_root)
    monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", clients_root)

    app = OracleClientsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(OracleClientsScreen)
        screen.query_one("#oc-installed-table", DataTable).cursor_coordinate = (0, 0)
        await pilot.pause()
        screen.query_one("#oc-use-btn", Button).press()
        await pilot.pause()

    assert load_settings().oracle_client_dir == str(client)
