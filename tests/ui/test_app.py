"""Tests for main app."""
import pytest
from dbqm.ui.app import DBQMApp
from dbqm.ui.widgets.sidebar import Sidebar
from dbqm.ui.widgets.status_bar import StatusBar
from dbqm.ui.widgets.breadcrumb import Breadcrumb


@pytest.mark.asyncio
async def test_app_starts_and_shows_sidebar(tmp_config_dir):
    app = DBQMApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        assert sidebar is not None


@pytest.mark.asyncio
async def test_app_has_status_bar(tmp_config_dir):
    app = DBQMApp()
    async with app.run_test() as pilot:
        bar = app.query_one(StatusBar)
        assert bar is not None


@pytest.mark.asyncio
async def test_app_has_breadcrumb(tmp_config_dir):
    app = DBQMApp()
    async with app.run_test() as pilot:
        bc = app.query_one(Breadcrumb)
        assert bc is not None


@pytest.mark.asyncio
async def test_ctrl_b_toggles_sidebar(tmp_config_dir):
    app = DBQMApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        assert not sidebar.collapsed
        await pilot.press("ctrl+b")
        assert sidebar.collapsed


@pytest.mark.asyncio
async def test_welcome_message_shown_on_first_run(tmp_config_dir):
    """When no connections exist, a welcome message should appear."""
    app = DBQMApp()
    async with app.run_test() as pilot:
        welcome = app.query_one("#welcome-message")
        assert welcome is not None


@pytest.mark.asyncio
async def test_sidebar_item_shows_placeholder(tmp_config_dir):
    """Clicking a sidebar item shows a placeholder in the screen area."""
    from dbqm.ui.widgets.sidebar import SidebarItemSelected

    app = DBQMApp()
    async with app.run_test() as pilot:
        app.post_message(SidebarItemSelected("config_conn"))
        await pilot.pause()
        placeholder = app.query_one("#placeholder")
        assert placeholder is not None
