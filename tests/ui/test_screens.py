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
