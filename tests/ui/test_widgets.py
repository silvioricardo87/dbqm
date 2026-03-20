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
