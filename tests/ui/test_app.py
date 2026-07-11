"""Tests for the main app (single tabbed shell)."""
import pytest
from textual.widgets import TabbedContent, TabPane

from dbqm.ui.app import DBQMApp
from dbqm.ui.widgets.status_bar import StatusBar
from dbqm.ui.widgets.templates_sidebar import TemplatesSidebar


@pytest.mark.asyncio
async def test_app_starts_and_shows_tabs(tmp_config_dir):
    app = DBQMApp()
    async with app.run_test() as pilot:
        tabs = app.query_one("#main-tabs", TabbedContent)
        assert tabs is not None


@pytest.mark.asyncio
async def test_app_has_status_bar(tmp_config_dir):
    app = DBQMApp()
    async with app.run_test() as pilot:
        bar = app.query_one(StatusBar)
        assert bar is not None


@pytest.mark.asyncio
async def test_app_has_templates_sidebar(tmp_config_dir):
    app = DBQMApp()
    async with app.run_test() as pilot:
        sb = app.query_one(TemplatesSidebar)
        assert sb is not None


@pytest.mark.asyncio
async def test_f_keys_switch_tabs(tmp_config_dir):
    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.press("f6")
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-config"
        await pilot.press("f2")
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-conexoes"
        await pilot.press("f3")
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-objetos"
        await pilot.press("f8")
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-ferramentas"


@pytest.mark.asyncio
async def test_ctrl_b_toggles_templates_sidebar(tmp_config_dir):
    app = DBQMApp()
    async with app.run_test() as pilot:
        sb = app.query_one(TemplatesSidebar)
        assert not sb.has_class("-collapsed")
        await pilot.press("ctrl+b")
        assert sb.has_class("-collapsed")
        await pilot.press("ctrl+b")
        assert not sb.has_class("-collapsed")


@pytest.mark.asyncio
async def test_first_run_switches_to_conexoes(tmp_config_dir):
    """When no connections exist, the app lands on the Conexoes tab."""
    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-conexoes"


@pytest.mark.asyncio
async def test_config_tab_hosts_settings_screen(tmp_config_dir):
    """Switching to the config tab exposes the SettingsScreen."""
    from dbqm.ui.screens.settings import SettingsScreen

    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.press("f6")
        assert app.query_one(SettingsScreen) is not None


@pytest.mark.asyncio
async def test_conexoes_tab_hosts_connections_screen(tmp_config_dir):
    """The Conexoes tab hosts the ConnectionsScreen and sets its actions."""
    from dbqm.ui.screens.connections import ConnectionsScreen
    from dbqm.ui.widgets.action_bar import ActionBar

    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.press("f2")
        await pilot.pause()
        assert app.query_one(ConnectionsScreen) is not None
        # ConnectionsScreen restores its contextual actions when activated.
        assert len(app.query_one(ActionBar)._actions) == 5


@pytest.mark.asyncio
async def test_all_panes_enabled_after_mount(tmp_config_dir):
    """After the initial mount focus-storm settles, no TabPane is disabled
    (so every tab header is mouse-clickable), and the intended initial tab
    (no connections configured -> Conexoes) is the active one.
    """
    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        for tab_id in DBQMApp.TAB_TO_SCREEN:
            pane = app.query_one(f"#{tab_id}", TabPane)
            assert not pane.disabled, f"{tab_id} is unexpectedly disabled"
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-conexoes"


@pytest.mark.asyncio
async def test_activating_tab_via_tabbedcontent_active_works(tmp_config_dir):
    """Simulates a mouse click on a tab header by setting
    TabbedContent.active directly, and confirms the switch takes effect and
    the target pane remains enabled.
    """
    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main-tabs", TabbedContent)
        tabs.active = "tab-historico"
        await pilot.pause()
        assert tabs.active == "tab-historico"
        pane = app.query_one("#tab-historico", TabPane)
        assert not pane.disabled
