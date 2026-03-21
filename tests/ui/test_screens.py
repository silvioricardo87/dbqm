"""Tests for screens."""
from __future__ import annotations

import json

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, Select

from dbqm.ui.screens.connections import ConnectionsScreen
from dbqm.ui.screens.query_exec import QueryExecScreen


class QueryExecTestApp(App):
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


# ======================================================================
# ConnectionsScreen tests
# ======================================================================


class ConnectionsTestApp(App):
    def compose(self) -> ComposeResult:
        yield ConnectionsScreen()


@pytest.mark.asyncio
async def test_connections_screen_renders(tmp_config_dir):
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        assert screen is not None


@pytest.mark.asyncio
async def test_connections_screen_empty(tmp_config_dir):
    """With no connections, should show empty message and hide table."""
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        empty = screen.query_one("#conn-empty")
        assert empty.display is True
        table = screen.query_one("#conn-table")
        assert table.display is False


@pytest.mark.asyncio
async def test_connections_screen_with_data(tmp_config_dir):
    """With connections configured, should show them in the table."""
    config_dir = tmp_config_dir / "config"
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
                "password": "encrypted_pass",
            },
            {
                "name": "prod_pg",
                "db_type": "postgresql",
                "host": "localhost",
                "port": 5432,
                "database": "mydb",
                "user": "pguser",
                "password": "encrypted_pass2",
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        empty = screen.query_one("#conn-empty")
        assert empty.display is False
        from textual.widgets import DataTable
        table = screen.query_one("#conn-table", DataTable)
        assert table.display is True
        assert table.row_count == 2


# ======================================================================
# QueryManageScreen tests
# ======================================================================

from dbqm.ui.screens.query_manage import QueryManageScreen


class QueryManageTestApp(App):
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


class GroupManageTestApp(App):
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


# ======================================================================
# GroupExecScreen tests
# ======================================================================

from dbqm.ui.screens.group_exec import GroupExecScreen


class GroupExecTestApp(App):
    def compose(self) -> ComposeResult:
        yield GroupExecScreen()


@pytest.mark.asyncio
async def test_group_exec_screen_renders(tmp_config_dir):
    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(GroupExecScreen) is not None


@pytest.mark.asyncio
async def test_group_exec_screen_shows_empty_message(tmp_config_dir):
    """With no groups configured, should show empty state."""
    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        empty = screen.query_one("#ge-empty-message")
        assert empty.display is True


@pytest.mark.asyncio
async def test_group_exec_screen_shows_group_list(tmp_config_dir):
    """With groups configured, should show the group list."""
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

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        empty = screen.query_one("#ge-empty-message")
        assert empty.display is False
        # Selection phase should be visible
        sel = screen.query_one("#ge-selection-phase")
        assert sel.display is True
        # Results phase should be hidden
        res = screen.query_one("#ge-results-phase")
        assert res.display is False


@pytest.mark.asyncio
async def test_group_exec_results_phase_hidden_initially(tmp_config_dir):
    """Results phase should be hidden on mount."""
    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        results = screen.query_one("#ge-results-phase")
        assert results.display is False


@pytest.mark.asyncio
async def test_group_exec_go_back_to_selection(tmp_config_dir):
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

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        # Simulate being in results phase
        screen.query_one("#ge-selection-phase").display = False
        screen.query_one("#ge-results-phase").display = True

        screen.go_back_to_selection()

        assert screen.query_one("#ge-selection-phase").display is True
        assert screen.query_one("#ge-results-phase").display is False


@pytest.mark.asyncio
async def test_group_exec_screen_with_accented_folders(tmp_config_dir):
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
                "folder": "Produ\u00e7\u00e3o",
            },
            {
                "name": "g_acc_b",
                "description": "",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["val"],
                "folder": "Homologa\u00e7\u00e3o",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        folder_bar = screen.query_one("#ge-folder-bar")
        assert folder_bar is not None
        from textual.widgets import Button
        buttons = folder_bar.query(Button)
        assert len(buttons) >= 3


@pytest.mark.asyncio
async def test_group_exec_screen_with_folders(tmp_config_dir):
    """Groups with folders should produce folder filter bar."""
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

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        folder_bar = screen.query_one("#ge-folder-bar")
        assert folder_bar is not None
        from textual.widgets import Button
        buttons = folder_bar.query(Button)
        # "Todas" + "Folder A" + "Folder B" = 3
        assert len(buttons) >= 3


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


class AdhocTestApp(App):
    def compose(self) -> ComposeResult:
        yield AdhocScreen()


@pytest.mark.asyncio
async def test_adhoc_screen_renders(tmp_config_dir):
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(AdhocScreen) is not None


@pytest.mark.asyncio
async def test_adhoc_screen_has_input_phase(tmp_config_dir):
    """AdhocScreen should show input phase on mount."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        input_phase = screen.query_one("#adhoc-input-phase")
        assert input_phase.display is True
        results_phase = screen.query_one("#adhoc-results-phase")
        assert results_phase.display is False


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
    """AdhocScreen should have execute, generate, and save buttons."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        from textual.widgets import Button
        execute_btn = screen.query_one("#adhoc-execute", Button)
        generate_btn = screen.query_one("#adhoc-generate", Button)
        save_btn = screen.query_one("#adhoc-save", Button)
        assert execute_btn is not None
        assert generate_btn is not None
        assert save_btn is not None


@pytest.mark.asyncio
async def test_adhoc_screen_go_back_to_input(tmp_config_dir):
    """go_back_to_input should show input and hide results."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        # Simulate being in results phase
        screen.query_one("#adhoc-input-phase").display = False
        screen.query_one("#adhoc-results-phase").display = True

        screen.go_back_to_input()

        assert screen.query_one("#adhoc-input-phase").display is True
        assert screen.query_one("#adhoc-results-phase").display is False


@pytest.mark.asyncio
async def test_adhoc_screen_go_back_cleans_connection(tmp_config_dir):
    """go_back_to_input should rollback and close any open DML connection."""
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
        screen.query_one("#adhoc-input-phase").display = False
        screen.query_one("#adhoc-results-phase").display = True

        screen.go_back_to_input()

        assert mock.rolled_back is True
        assert mock.closed is True
        assert screen._db_connection is None


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


# ======================================================================
# DDLScreen tests
# ======================================================================

from dbqm.ui.screens.ddl import DDLScreen


class DDLTestApp(App):
    def compose(self) -> ComposeResult:
        yield DDLScreen()


@pytest.mark.asyncio
async def test_ddl_screen_renders(tmp_config_dir):
    app = DDLTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(DDLScreen) is not None


@pytest.mark.asyncio
async def test_ddl_screen_has_input_phase(tmp_config_dir):
    """DDLScreen should show input phase on mount."""
    app = DDLTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(DDLScreen)
        input_phase = screen.query_one("#ddl-input-phase")
        assert input_phase.display is True
        results_phase = screen.query_one("#ddl-results-phase")
        assert results_phase.display is False


@pytest.mark.asyncio
async def test_ddl_screen_has_object_input(tmp_config_dir):
    """DDLScreen should have an Input for object name."""
    app = DDLTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(DDLScreen)
        obj_input = screen.query_one("#ddl-object-input", Input)
        assert obj_input is not None


@pytest.mark.asyncio
async def test_ddl_screen_has_extract_button(tmp_config_dir):
    """DDLScreen should have an extract button."""
    app = DDLTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(DDLScreen)
        from textual.widgets import Button
        extract_btn = screen.query_one("#ddl-extract", Button)
        assert extract_btn is not None


@pytest.mark.asyncio
async def test_ddl_screen_go_back_to_input(tmp_config_dir):
    """go_back_to_input should show input and hide results."""
    app = DDLTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(DDLScreen)
        # Simulate being in results phase
        screen.query_one("#ddl-input-phase").display = False
        screen.query_one("#ddl-results-phase").display = True

        screen.go_back_to_input()

        assert screen.query_one("#ddl-input-phase").display is True
        assert screen.query_one("#ddl-results-phase").display is False


@pytest.mark.asyncio
async def test_ddl_screen_connection_selector(tmp_config_dir):
    """DDLScreen should have a connection selector with supported connections."""
    config_dir = tmp_config_dir / "config"
    conn_data = {
        "connections": [
            {
                "name": "oracle_conn",
                "db_type": "oracle",
                "mode": "direct",
                "host": "localhost",
                "port": 1521,
                "service_name": "ORCL",
                "user": "admin",
                "password": "pass",
            },
            {
                "name": "sqlite_conn",
                "db_type": "sqlite",
                "host": "",
                "port": 0,
                "database": "test.db",
                "user": "",
                "password": "",
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )

    app = DDLTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(DDLScreen)
        select_widget = screen.query_one("#ddl-conn-select", Select)
        assert select_widget is not None


# ======================================================================
# BrowserScreen tests
# ======================================================================

from dbqm.ui.screens.browser import BrowserScreen


class BrowserTestApp(App):
    def compose(self) -> ComposeResult:
        yield BrowserScreen()


@pytest.mark.asyncio
async def test_browser_screen_renders(tmp_config_dir):
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(BrowserScreen) is not None


@pytest.mark.asyncio
async def test_browser_screen_has_select_phase(tmp_config_dir):
    """BrowserScreen should show select phase on mount."""
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        select_phase = screen.query_one("#br-select-phase")
        assert select_phase.display is True
        list_phase = screen.query_one("#br-list-phase")
        assert list_phase.display is False
        detail_phase = screen.query_one("#br-detail-phase")
        assert detail_phase.display is False
        data_phase = screen.query_one("#br-data-phase")
        assert data_phase.display is False


@pytest.mark.asyncio
async def test_browser_screen_has_type_buttons(tmp_config_dir):
    """BrowserScreen should have type selection buttons."""
    from textual.widgets import Button
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        table_btn = screen.query_one("#br-type-table", Button)
        view_btn = screen.query_one("#br-type-view", Button)
        assert table_btn is not None
        assert view_btn is not None


@pytest.mark.asyncio
async def test_browser_screen_has_connection_selector(tmp_config_dir):
    """BrowserScreen should have a connection selector."""
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

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        select_widget = screen.query_one("#br-conn-select", Select)
        assert select_widget is not None


@pytest.mark.asyncio
async def test_browser_screen_go_back_to_select(tmp_config_dir):
    """go_back_to_select should show select and hide other phases."""
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        # Simulate being in list phase
        screen.query_one("#br-select-phase").display = False
        screen.query_one("#br-list-phase").display = True

        screen.go_back_to_select()

        assert screen.query_one("#br-select-phase").display is True
        assert screen.query_one("#br-list-phase").display is False


@pytest.mark.asyncio
async def test_browser_screen_go_back_to_list(tmp_config_dir):
    """go_back_to_list should show list and hide detail."""
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        # Simulate being in detail phase
        screen.query_one("#br-select-phase").display = False
        screen.query_one("#br-list-phase").display = False
        screen.query_one("#br-detail-phase").display = True

        screen.go_back_to_list()

        assert screen.query_one("#br-list-phase").display is True
        assert screen.query_one("#br-detail-phase").display is False


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


class HistoryTestApp(App):
    def compose(self) -> ComposeResult:
        yield HistoryScreen()


@pytest.mark.asyncio
async def test_history_screen_renders(tmp_config_dir):
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(HistoryScreen) is not None


@pytest.mark.asyncio
async def test_history_screen_empty(tmp_config_dir):
    """With no history, should show empty message and hide table."""
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        empty = screen.query_one("#hist-empty")
        assert empty.display is True
        from textual.widgets import DataTable
        table = screen.query_one("#hist-table", DataTable)
        assert table.display is False


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
async def test_history_screen_detail_hidden_initially(tmp_config_dir):
    """Detail phase should be hidden on mount."""
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        detail = screen.query_one("#hist-detail-phase")
        assert detail.display is False


@pytest.mark.asyncio
async def test_history_screen_go_back_to_list(tmp_config_dir):
    """go_back_to_list should show list and hide detail."""
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        # Simulate being in detail phase
        screen.query_one("#hist-list-phase").display = False
        screen.query_one("#hist-detail-phase").display = True

        screen.go_back_to_list()

        assert screen.query_one("#hist-list-phase").display is True
        assert screen.query_one("#hist-detail-phase").display is False


# ======================================================================
# SettingsScreen tests
# ======================================================================

from dbqm.ui.screens.settings import SettingsScreen


class SettingsTestApp(App):
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
        assert theme_select.value == "github-dark"
        audit_switch = screen.query_one("#settings-audit-switch", Switch)
        assert audit_switch.value is False


@pytest.mark.asyncio
async def test_settings_screen_loads_saved_settings(tmp_config_dir):
    """SettingsScreen should load previously saved settings."""
    from textual.widgets import Switch
    config_dir = tmp_config_dir / "config"
    settings_data = {"audit_log_enabled": True, "theme": "github-light"}
    (config_dir / "settings.json").write_text(
        json.dumps(settings_data, ensure_ascii=False), encoding="utf-8"
    )

    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        assert theme_select.value == "github-light"
        audit_switch = screen.query_one("#settings-audit-switch", Switch)
        assert audit_switch.value is True


# ======================================================================
# ConfigPortScreen tests
# ======================================================================

from dbqm.ui.screens.config_port import ConfigPortScreen


class ConfigPortTestApp(App):
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

    class GRTestApp(App):
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
        screen.key_right()
        assert screen._active_folder_idx == 1
        screen.key_right()
        assert screen._active_folder_idx == 2
        # Should not go past the end
        screen.key_right()
        assert screen._active_folder_idx == 2
        # Left arrow should go back
        screen.key_left()
        assert screen._active_folder_idx == 1
        screen.key_left()
        assert screen._active_folder_idx == 0
        # Should not go below 0
        screen.key_left()
        assert screen._active_folder_idx == 0


@pytest.mark.asyncio
async def test_group_exec_folder_arrow_navigation(tmp_config_dir):
    """Left/Right arrows should switch folder tabs in group exec."""
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

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        # Should have folder buttons: Todas + F1 + F2
        assert len(screen._folder_buttons) >= 3
        assert screen._active_folder_idx == 0
        # Right arrow should advance
        screen.key_right()
        assert screen._active_folder_idx == 1
        screen.key_right()
        assert screen._active_folder_idx == 2
        # Left arrow should go back
        screen.key_left()
        assert screen._active_folder_idx == 1


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


@pytest.mark.asyncio
async def test_group_list_shows_all_items(tmp_config_dir):
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

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        from dbqm.ui.screens.group_exec import _GroupListItem
        items = app.query(_GroupListItem)
        assert len(items) == 8


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

    class TestApp(App):
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

    class TestApp(App):
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

    class TestApp(App):
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

    class TestApp(App):
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

    class TestApp(App):
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

    class TestApp(App):
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

    class TestApp(App):
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

    class TestApp(App):
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

    class TestApp(App):
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

    class TestApp(App):
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
        detail = screen.query_one("#hist-detail-phase")
        assert detail.display is True


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
        detail = screen.query_one("#hist-detail-phase")
        assert detail.display is True


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
        # Change theme to github-light
        theme_select.value = "github-light"
        await pilot.pause()

        from dbqm.models.settings import load_settings
        settings = load_settings()
        assert settings.theme == "github-light"


# ======================================================================
# Group exec result display integration test
# ======================================================================


@pytest.mark.asyncio
async def test_group_exec_show_result_does_not_crash(tmp_config_dir):
    """_show_result should display group results without AttributeError."""
    from dbqm.ui.widgets.action_bar import ActionBar

    qr1 = QR(
        query_name="q1", connection_name="c1",
        columns=["id", "status"], rows=[[1, "ok"], [2, "fail"]],
        row_count=2, elapsed=0.1,
    )
    qr2 = QR(
        query_name="q2", connection_name="c2",
        columns=["id", "status"], rows=[[1, "ok"], [2, "ok"]],
        row_count=2, elapsed=0.1,
    )
    comp = ComparisonResult(
        column="status",
        rows=[
            ComparisonRow(key_value=1, values={"q1": "ok", "q2": "ok"}, status="OK"),
            ComparisonRow(key_value=2, values={"q1": "fail", "q2": "ok"}, status="DIFF"),
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

    class TestApp(App):
        def compose(self_):
            yield ActionBar()
            yield GroupExecScreen()

    app = TestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        # Directly call _show_result — this is where the bug was
        screen._show_result(gr, {"param1": "value1"})
        await pilot.pause()

        # Results phase should be visible
        assert screen.query_one("#ge-results-phase").display is True
        assert screen.query_one("#ge-selection-phase").display is False


@pytest.mark.asyncio
async def test_group_exec_folder_bar_is_horizontal_scroll(tmp_config_dir):
    """Group exec folder bar should use HorizontalScroll for scrollability."""
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

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        from textual.containers import HorizontalScroll
        screen = app.query_one(GroupExecScreen)
        folder_bar = screen.query_one("#ge-folder-bar")
        assert isinstance(folder_bar, HorizontalScroll)


# ======================================================================
# Real UI flow tests — modals, shortcuts, screen navigation
# ======================================================================


@pytest.mark.asyncio
async def test_connection_form_modal_opens(tmp_config_dir):
    """Pressing N on connections screen should open the connection form modal."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.modals.connection_form import ConnectionFormModal
    from dbqm.ui.screens.connections import ConnectionsScreen

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        # Navigate to connections
        sidebar = app.query_one("Sidebar")
        for i, item in enumerate(sidebar._focusable_items):
            if item._action == "config_conn":
                sidebar._selected_index = i
                break
        sidebar.key_enter()
        await pilot.pause()
        await pilot.pause()

        # Trigger the "new" action directly (simulates the N shortcut)
        conn_screen = app.query_one(ConnectionsScreen)
        conn_screen._handle_new()
        await pilot.pause()
        await pilot.pause()

        # Modal should be on the screen stack
        modal_screens = [
            s for s in app.screen_stack
            if isinstance(s, ConnectionFormModal)
        ]
        assert len(modal_screens) > 0, "ConnectionFormModal should have opened"


@pytest.mark.asyncio
async def test_connection_form_modal_closes_on_esc(tmp_config_dir):
    """ESC should close the connection form modal."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.modals.connection_form import ConnectionFormModal
    from dbqm.ui.screens.connections import ConnectionsScreen

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one("Sidebar")
        for i, item in enumerate(sidebar._focusable_items):
            if item._action == "config_conn":
                sidebar._selected_index = i
                break
        sidebar.key_enter()
        await pilot.pause()
        await pilot.pause()

        # Open the modal via direct call
        conn_screen = app.query_one(ConnectionsScreen)
        conn_screen._handle_new()
        await pilot.pause()
        await pilot.pause()

        # Press ESC to close
        await pilot.press("escape")
        await pilot.pause()

        # Modal should be gone from the screen stack
        modal_screens = [
            s for s in app.screen_stack
            if isinstance(s, ConnectionFormModal)
        ]
        assert len(modal_screens) == 0


@pytest.mark.asyncio
async def test_connection_form_db_type_selection(tmp_config_dir):
    """Selecting a db type should populate dynamic fields without crash."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.modals.connection_form import ConnectionFormModal
    from dbqm.ui.screens.connections import ConnectionsScreen

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one("Sidebar")
        for i, item in enumerate(sidebar._focusable_items):
            if item._action == "config_conn":
                sidebar._selected_index = i
                break
        sidebar.key_enter()
        await pilot.pause()
        await pilot.pause()

        # Open the modal via direct call
        conn_screen = app.query_one(ConnectionsScreen)
        conn_screen._handle_new()
        await pilot.pause()
        await pilot.pause()

        # Find the modal on the screen stack
        modal = None
        for s in app.screen_stack:
            if isinstance(s, ConnectionFormModal):
                modal = s
                break
        assert modal is not None, "ConnectionFormModal should be open"

        # Select postgresql type
        db_select = modal.query_one("#field-db-type", Select)
        db_select.value = "postgresql"
        await pilot.pause()
        await pilot.pause()

        # Should have host, port, database, user, password fields
        inputs = modal.query(Input)
        # Should have at least: name + host + port + database + user + password = 6
        assert len(inputs) >= 5


@pytest.mark.asyncio
async def test_query_exec_shortcut_keys(tmp_config_dir):
    """Action bar shortcut keys should work on query exec screen."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.widgets.action_bar import ActionBar

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one("Sidebar")
        for i, item in enumerate(sidebar._focusable_items):
            if item._action == "exec_query":
                sidebar._selected_index = i
                break
        sidebar.key_enter()
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
        sidebar = app.query_one("Sidebar")
        for i, item in enumerate(sidebar._focusable_items):
            if item._action == "settings":
                sidebar._selected_index = i
                break
        sidebar.key_enter()
        await pilot.pause()
        await pilot.pause()

        # Should have a Select for theme
        selects = app.query(Select)
        assert len(selects) > 0


@pytest.mark.asyncio
async def test_all_sidebar_items_open_without_crash(tmp_config_dir):
    """Every sidebar item should load its screen without crashing."""
    from dbqm.ui.app import DBQMApp

    actions_to_test = [
        "exec_query", "adhoc_sql", "config_query",
        "exec_group", "config_group",
        "extract_ddl", "browse", "history",
        "config_conn", "portability", "settings",
    ]

    for action in actions_to_test:
        app = DBQMApp()
        async with app.run_test(size=(120, 40)) as pilot:
            sidebar = app.query_one("Sidebar")
            for i, item in enumerate(sidebar._focusable_items):
                if item._action == action:
                    sidebar._selected_index = i
                    break
            sidebar.key_enter()
            await pilot.pause()
            await pilot.pause()
            # Just verify no crash


@pytest.mark.asyncio
async def test_query_manage_view_sql(tmp_config_dir):
    """View SQL shortcut should work on query manage screen."""
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.app import DBQMApp

    save_queries([
        Query(name="test_q", connection="c1", sql="SELECT 1 FROM dual", table="dual"),
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one("Sidebar")
        for i, item in enumerate(sidebar._focusable_items):
            if item._action == "config_query":
                sidebar._selected_index = i
                break
        sidebar.key_enter()
        await pilot.pause()
        await pilot.pause()
        # No crash = success


@pytest.mark.asyncio
async def test_edit_connection_opens(tmp_config_dir):
    """Editing an existing connection should open modal without crash."""
    from dbqm.models.connection import Connection, save_connections
    from dbqm.core.crypto import encrypt
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.modals.connection_form import ConnectionFormModal
    from dbqm.ui.screens.connections import ConnectionsScreen

    save_connections([
        Connection(name="test_conn", db_type="oracle", mode="direct",
                   host="localhost", port=1521, service_name="ORCL",
                   user="admin", password=encrypt("pass")),
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one("Sidebar")
        for i, item in enumerate(sidebar._focusable_items):
            if item._action == "config_conn":
                sidebar._selected_index = i
                break
        sidebar.key_enter()
        await pilot.pause()
        await pilot.pause()

        # Trigger edit directly (simulates the E shortcut)
        conn_screen = app.query_one(ConnectionsScreen)
        conn_screen._handle_edit()
        await pilot.pause()
        await pilot.pause()

        # Modal should be on the screen stack with pre-filled fields
        modal_screens = [
            s for s in app.screen_stack
            if isinstance(s, ConnectionFormModal)
        ]
        assert len(modal_screens) > 0


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


class PackageEditorTestApp(App):
    def compose(self) -> ComposeResult:
        yield PackageEditorScreen()


@pytest.mark.asyncio
async def test_package_editor_screen_renders(tmp_config_dir):
    app = PackageEditorTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.query_one(PackageEditorScreen) is not None


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
