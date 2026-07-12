"""Tests for UI widgets."""
import pytest
from textual.app import App, ComposeResult


# ---------------------------------------------------------------------------
# StatusBar tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.status_bar import StatusBar


class StatusBarTestApp(App):
    def compose(self) -> ComposeResult:
        yield StatusBar()


@pytest.mark.asyncio
async def test_status_bar_shows_connection():
    app = StatusBarTestApp()
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)
        sb.set_connection("ORACLE-PRD")
        await pilot.pause()
        rendered = sb.render_text()
        assert "ORACLE-PRD" in rendered


@pytest.mark.asyncio
async def test_status_bar_no_connection():
    app = StatusBarTestApp()
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)
        sb.set_connection(None)
        await pilot.pause()
        rendered = sb.render_text()
        # Should show indicator but no connection name
        assert "ORACLE-PRD" not in rendered


@pytest.mark.asyncio
async def test_status_bar_shows_counts():
    app = StatusBarTestApp()
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)
        sb.update_counts(queries=5, connections=3, groups=2)
        await pilot.pause()
        rendered = sb.render_text()
        assert "5" in rendered
        assert "3" in rendered
        assert "2" in rendered


def test_status_bar_inverted_primary_background():
    assert "background: $primary" in StatusBar.DEFAULT_CSS


# ---------------------------------------------------------------------------
# ActionBar tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.action_bar import ActionBar, ActionSelected, Action


class ActionBarTestApp(App):
    def compose(self) -> ComposeResult:
        yield ActionBar()


@pytest.mark.asyncio
async def test_action_bar_renders_actions():
    app = ActionBarTestApp()
    async with app.run_test() as pilot:
        ab = app.query_one(ActionBar)
        ab.set_actions([
            Action(label="Vertical", key="V", action_id="vertical"),
            Action(label="Exportar", key="E", action_id="export"),
        ])
        await pilot.pause()
        assert ab.display is True
        assert len(ab._actions) == 2


@pytest.mark.asyncio
async def test_action_bar_empty():
    app = ActionBarTestApp()
    async with app.run_test() as pilot:
        ab = app.query_one(ActionBar)
        ab.set_actions([])
        await pilot.pause()
        assert ab.display is False


def test_action_bar_uses_primary_key_markup():
    bar = ActionBar()
    bar._actions = [Action("Executar", "r", "run")]
    bar._rebuild()
    rendered = str(bar._Static__content)
    assert "on white" not in rendered            # no more black-on-white chip
    assert "bold $primary" in rendered or "bold #58a6ff" in rendered


# ---------------------------------------------------------------------------
# ResultTable tests
# ---------------------------------------------------------------------------
from dbqm.core.query_engine import QueryResult
from dbqm.ui.widgets.result_table import ResultTable


class ResultTableTestApp(App):
    def compose(self) -> ComposeResult:
        yield ResultTable()


@pytest.mark.asyncio
async def test_result_table_loads_data():
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id", "name", "value"],
        rows=[[1, "Alice", 100], [2, "Bob", 200], [3, "Carol", 300]],
        row_count=3,
        elapsed=0.05,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_result_table_pagination():
    rows = [[i, f"name_{i}", i * 10] for i in range(250)]
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id", "name", "value"],
        rows=rows,
        row_count=250,
        elapsed=0.1,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.page_info == "Pagina 1/3 (250 registros)"
        table.next_page()
        assert "Pagina 2/3" in table.page_info
        table.prev_page()
        assert "Pagina 1/3" in table.page_info


@pytest.mark.asyncio
async def test_result_table_empty():
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id"],
        rows=[],
        row_count=0,
        elapsed=0.01,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_result_table_vertical_toggle():
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id", "name"],
        rows=[[1, "Alice"]],
        row_count=1,
        elapsed=0.01,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert not table.vertical_mode
        table.toggle_vertical()
        assert table.vertical_mode


@pytest.mark.asyncio
async def test_result_table_none_values():
    """None values should display as empty strings."""
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id", "name"],
        rows=[[1, None], [None, "Bob"]],
        row_count=2,
        elapsed=0.01,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_result_table_page_info_and_result_info():
    result = QueryResult(
        query_name="test",
        connection_name="ORACLE-PRD",
        columns=["id"],
        rows=[[i] for i in range(250)],
        row_count=250,
        elapsed=0.34,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.result_info == "250 registros | 0.34s | ORACLE-PRD"
        assert table.page_info == "Pagina 1/3 (250 registros)"


@pytest.mark.asyncio
async def test_result_table_pagination_boundary():
    """Cannot go before first or after last page."""
    rows = [[i] for i in range(250)]
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id"],
        rows=rows,
        row_count=250,
        elapsed=0.1,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        table.prev_page()  # already at page 0
        assert "Pagina 1/3" in table.page_info
        table.next_page()
        table.next_page()
        table.next_page()  # should stop at page 3
        assert "Pagina 3/3" in table.page_info


# ---------------------------------------------------------------------------
# ProgressIndicator tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.progress import ProgressIndicator


class ProgressTestApp(App):
    def compose(self) -> ComposeResult:
        yield ProgressIndicator()


@pytest.mark.asyncio
async def test_progress_starts_hidden():
    app = ProgressTestApp()
    async with app.run_test() as pilot:
        progress = app.query_one(ProgressIndicator)
        assert not progress.display  # hidden by default


@pytest.mark.asyncio
async def test_progress_start_shows():
    app = ProgressTestApp()
    async with app.run_test() as pilot:
        progress = app.query_one(ProgressIndicator)
        progress.start("Loading...")
        assert progress.display


@pytest.mark.asyncio
async def test_progress_stop_hides():
    app = ProgressTestApp()
    async with app.run_test() as pilot:
        progress = app.query_one(ProgressIndicator)
        progress.start("Loading...")
        progress.stop()
        assert not progress.display


@pytest.mark.asyncio
async def test_progress_update_message():
    app = ProgressTestApp()
    async with app.run_test() as pilot:
        progress = app.query_one(ProgressIndicator)
        progress.start("Step 1...")
        progress.update_message("Step 2...")
        from textual.widgets import Static
        msg = progress.query_one("#progress-message", Static)
        assert str(msg._Static__content) == "Step 2..."


# ---------------------------------------------------------------------------
# QueryListWidget tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.query_list import QueryListWidget, QuerySelected


class QueryListTestApp(App):
    def compose(self) -> ComposeResult:
        yield QueryListWidget()


@pytest.mark.asyncio
async def test_query_list_loads_items():
    queries = [
        {"name": "q1", "connection": "conn1", "table": "t1", "description": "desc1", "is_favorite": False, "folder": ""},
        {"name": "q2", "connection": "conn2", "table": "t2", "description": "desc2", "is_favorite": True, "folder": ""},
    ]
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        assert len(items) == 2
        # Favorites should be first
        assert items[0].query_name == "q2"
        assert items[1].query_name == "q1"


@pytest.mark.asyncio
async def test_query_list_empty():
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries([])
        await pilot.pause()
        from textual.widgets import ListItem
        items = ql.query(ListItem)
        assert len(items) == 1  # empty-state item


@pytest.mark.asyncio
async def test_query_list_filter_folder():
    queries = [
        {"name": "q1", "connection": "c1", "table": "", "description": "", "is_favorite": False, "folder": "folderA"},
        {"name": "q2", "connection": "c2", "table": "", "description": "", "is_favorite": False, "folder": "folderB"},
        {"name": "q3", "connection": "c3", "table": "", "description": "", "is_favorite": False, "folder": "folderA"},
    ]
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        ql.filter_folder("folderA")
        await pilot.pause()
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        assert len(items) == 2
        names = {it.query_name for it in items}
        assert names == {"q1", "q3"}


@pytest.mark.asyncio
async def test_query_list_filter_folder_none_shows_all():
    queries = [
        {"name": "q1", "connection": "c1", "table": "", "description": "", "is_favorite": False, "folder": "folderA"},
        {"name": "q2", "connection": "c2", "table": "", "description": "", "is_favorite": False, "folder": "folderB"},
    ]
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        ql.filter_folder(None)
        await pilot.pause()
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        assert len(items) == 2


@pytest.mark.asyncio
async def test_query_list_posts_query_selected():
    queries = [
        {"name": "my_query", "connection": "c1", "table": "t1", "description": "d", "is_favorite": False, "folder": ""},
    ]
    messages = []

    class CapturingApp(App):
        def compose(self) -> ComposeResult:
            yield QueryListWidget()

        def on_query_selected(self, event: QuerySelected) -> None:
            messages.append(event.query_name)

    app = CapturingApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        await pilot.click(type(items[0]))
        await pilot.pause()
        assert len(messages) == 1
        assert messages[0] == "my_query"


@pytest.mark.asyncio
async def test_query_list_accepts_objects():
    """Widget should work with objects that have attributes (not just dicts)."""
    from dbqm.models.query import Query
    q = Query(name="obj_q", connection="conn", sql="SELECT 1", description="from object", is_favorite=True)
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries([q])
        await pilot.pause()
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        assert len(items) == 1
        assert items[0].query_name == "obj_q"


# ---------------------------------------------------------------------------
# GroupResultWidget tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.group_result import GroupResultWidget
from dbqm.core.group_engine import GroupResult, ComparisonResult, ComparisonRow


class GroupResultTestApp(App):
    def compose(self) -> ComposeResult:
        yield GroupResultWidget()


@pytest.mark.asyncio
async def test_group_result_loads(sample_group_result):
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        # Should render without error
        assert w.group_result is not None
        assert w.group_result.group_name == "test_group"


@pytest.mark.asyncio
async def test_group_result_default_mode_is_flat(sample_group_result):
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        assert w.mode == "flat"
        w.load_result(sample_group_result)
        assert w.mode == "flat"


@pytest.mark.asyncio
async def test_group_result_toggle_mode(sample_group_result):
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        assert w.mode == "flat"
        w.toggle_mode()
        assert w.mode == "pivoted"
        w.toggle_mode()
        assert w.mode == "flat"


@pytest.mark.asyncio
async def test_group_result_flat_renders_tables(sample_group_result):
    """Flat mode should render one DataTable per comparison column."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        await pilot.pause()
        from textual.widgets import DataTable
        tables = w.query(DataTable)
        # sample_group_result has 1 comparison column -> 1 table
        assert len(tables) == 1


@pytest.mark.asyncio
async def test_group_result_pivoted_renders_tables(sample_group_result):
    """Pivoted mode should render one DataTable per join key."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        w.toggle_mode()
        await pilot.pause()
        from textual.widgets import DataTable
        tables = w.query(DataTable)
        # sample_group_result has 2 keys -> 2 tables
        assert len(tables) == 2


@pytest.mark.asyncio
async def test_group_result_filter_status(sample_group_result):
    """Filtering by status should only show matching rows."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        w.filter_status({"DIFF"})
        await pilot.pause()
        from textual.widgets import DataTable
        tables = w.query(DataTable)
        assert len(tables) == 1
        # Only DIFF rows: key=2
        assert tables[0].row_count == 1


@pytest.mark.asyncio
async def test_group_result_filter_status_clear(sample_group_result):
    """Clearing filter should show all rows again."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        w.filter_status({"DIFF"})
        await pilot.pause()
        w.filter_status(set())
        await pilot.pause()
        from textual.widgets import DataTable
        tables = w.query(DataTable)
        assert tables[0].row_count == 2


@pytest.mark.asyncio
async def test_group_result_summary_shows(sample_group_result):
    """Summary section should contain comparison stats."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        await pilot.pause()
        from textual.widgets import Static
        summary = w.query_one("#gr-summary", Static)
        rendered = str(summary._Static__content)
        assert "DIVERGENTE" in rendered
        assert "status" in rendered


# ---------------------------------------------------------------------------
# Panel tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.panel import Panel
from textual.widgets import Static


class _PanelApp(App):
    def compose(self) -> ComposeResult:
        with Panel("⚙️  PARAMETROS", accent=True, id="p1"):
            yield Static("body", id="inner")


@pytest.mark.asyncio
async def test_panel_renders_title_and_body():
    app = _PanelApp()
    async with app.run_test() as pilot:
        panel = app.query_one("#p1", Panel)
        title_content = str(panel.query_one("#panel-title")._Static__content)
        assert title_content.startswith("⚙️  PARAMETROS")
        assert panel.has_class("accent-focus")
        assert app.query_one("#inner", Static) in panel.query_one("#panel-body").children
        # Regression guard: the title must actually PAINT, not just exist in the
        # DOM. A `height: 1` title with a `border-bottom` leaves zero rows for
        # text, so it renders blank — assert the text reaches the screen.
        assert "PARAMETROS" in app.export_screenshot()


# ---------------------------------------------------------------------------
# TemplatesSidebar tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.templates_sidebar import TemplatesSidebar


class _TemplatesSidebarApp(App):
    def compose(self) -> ComposeResult:
        yield TemplatesSidebar(id="tpl")


@pytest.mark.asyncio
async def test_templates_sidebar_starts_collapsed_and_toggles():
    app = _TemplatesSidebarApp()
    async with app.run_test() as pilot:
        sb = app.query_one("#tpl", TemplatesSidebar)
        # Starts collapsed so the app opens clean; Ctrl+B reveals it.
        assert sb.has_class("-collapsed")
        sb.toggle()
        assert not sb.has_class("-collapsed")
        sb.toggle()
        assert sb.has_class("-collapsed")


@pytest.mark.asyncio
async def test_templates_sidebar_shows_hint_when_empty():
    from textual.widgets import OptionList, Static as _Static
    app = _TemplatesSidebarApp()
    async with app.run_test() as pilot:
        sb = app.query_one("#tpl", TemplatesSidebar)
        sb._reload()  # no templates in the test config
        await pilot.pause()
        # With zero templates the hint shows and the list is hidden.
        assert sb.query_one("#tpl-empty", _Static).display is True
        assert sb.query_one("#tpl-list", OptionList).display is False
        # And the sidebar title itself paints (same border-bottom/height guard).
        sb.remove_class("-collapsed")
        await pilot.pause()
        assert "TEMPLATES" in app.export_screenshot()


@pytest.mark.asyncio
async def test_templates_sidebar_option_selected_posts_message():
    from textual.widgets import OptionList
    from textual.widgets.option_list import Option

    messages = []

    class CapturingApp(App):
        def compose(self) -> ComposeResult:
            yield TemplatesSidebar(id="tpl")

        def on_templates_sidebar_template_chosen(self, event: TemplatesSidebar.TemplateChosen) -> None:
            messages.append(event.sql)

    app = CapturingApp()
    async with app.run_test() as pilot:
        sb = app.query_one("#tpl", TemplatesSidebar)
        ol = sb.query_one("#tpl-list", OptionList)
        ol.clear_options()
        sb._sqls = {"demo": "SELECT 1 FROM DUAL"}
        ol.add_option(Option("demo", id="demo"))
        await pilot.pause()
        ol.highlighted = 0
        await pilot.press("enter")
        await pilot.pause()
        assert messages == ["SELECT 1 FROM DUAL"]
