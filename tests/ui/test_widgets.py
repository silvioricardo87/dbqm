"""Tests for UI widgets."""
import pytest
from textual.app import App, ComposeResult
from dbqm.ui.widgets.sidebar import Sidebar, SidebarItemSelected


class SidebarTestApp(App):
    def compose(self) -> ComposeResult:
        yield Sidebar()


@pytest.mark.asyncio
async def test_sidebar_renders():
    app = SidebarTestApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        assert sidebar is not None


@pytest.mark.asyncio
async def test_sidebar_has_menu_items():
    app = SidebarTestApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        items = sidebar.query(".sidebar-item")
        assert len(items) >= 11  # At least 11 menu items


@pytest.mark.asyncio
async def test_sidebar_collapse_toggle():
    app = SidebarTestApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        assert not sidebar.collapsed
        sidebar.toggle_collapse()
        assert sidebar.collapsed
        assert sidebar.has_class("sidebar--collapsed")
        sidebar.toggle_collapse()
        assert not sidebar.collapsed
        assert not sidebar.has_class("sidebar--collapsed")


@pytest.mark.asyncio
async def test_sidebar_set_active():
    app = SidebarTestApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        sidebar.set_active("exec_query")
        active_items = sidebar.query(".sidebar-item--active")
        assert len(active_items) == 1


@pytest.mark.asyncio
async def test_sidebar_set_active_changes():
    """Setting a new active item removes the previous one."""
    app = SidebarTestApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        sidebar.set_active("exec_query")
        sidebar.set_active("adhoc_sql")
        active_items = sidebar.query(".sidebar-item--active")
        assert len(active_items) == 1


@pytest.mark.asyncio
async def test_sidebar_item_click_posts_message():
    """Clicking a menu item posts SidebarItemSelected."""
    messages = []

    class CapturingApp(App):
        def compose(self) -> ComposeResult:
            yield Sidebar()

        def on_sidebar_item_selected(self, event: SidebarItemSelected) -> None:
            messages.append(event.action)

    app = CapturingApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        items = sidebar.query(".sidebar-item")
        # Click the first item via pilot
        await pilot.click(type(items[0]), offset=(1, 0))
        await pilot.pause()
        assert len(messages) == 1
        assert messages[0] == "exec_query"


@pytest.mark.asyncio
async def test_sidebar_has_section_labels():
    app = SidebarTestApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        labels = sidebar.query(".sidebar-section-label")
        assert len(labels) == 4  # CONSULTAS, GRUPOS, FERRAMENTAS, SISTEMA


# ---------------------------------------------------------------------------
# Breadcrumb tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.breadcrumb import Breadcrumb, BreadcrumbNavigated


class BreadcrumbTestApp(App):
    def compose(self) -> ComposeResult:
        yield Breadcrumb()


@pytest.mark.asyncio
async def test_breadcrumb_renders_path():
    app = BreadcrumbTestApp()
    async with app.run_test() as pilot:
        bc = app.query_one(Breadcrumb)
        bc.set_path(["Consultas", "Executar", "saldo_cliente"])
        await pilot.pause()
        rendered = bc.render_text()
        assert "Consultas" in rendered
        assert "Executar" in rendered
        assert "saldo_cliente" in rendered


@pytest.mark.asyncio
async def test_breadcrumb_empty_path():
    app = BreadcrumbTestApp()
    async with app.run_test() as pilot:
        bc = app.query_one(Breadcrumb)
        bc.set_path([])
        await pilot.pause()
        rendered = bc.render_text()
        assert rendered.strip() == ""


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
        rendered = ab.render_text()
        assert "Vertical" in rendered
        assert "Exportar" in rendered


@pytest.mark.asyncio
async def test_action_bar_empty():
    app = ActionBarTestApp()
    async with app.run_test() as pilot:
        ab = app.query_one(ActionBar)
        ab.set_actions([])
        await pilot.pause()
        rendered = ab.render_text()
        assert rendered.strip() == ""
