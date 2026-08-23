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
        # Starts collapsed (clean initial screen); Ctrl+B reveals it.
        assert sb.has_class("-collapsed")
        await pilot.press("ctrl+b")
        assert not sb.has_class("-collapsed")
        await pilot.press("ctrl+b")
        assert sb.has_class("-collapsed")


@pytest.mark.asyncio
async def test_first_run_switches_to_connections_tab(tmp_config_dir):
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
async def test_connections_tab_hosts_connections_screen(tmp_config_dir):
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
    """Activating the tab through the `TabbedContent` API switches the tab
    and leaves the target pane enabled.

    This is not "simulating a click", as the old docstring claimed — a
    mouse click comes in through `Tabs`, this assignment comes in through
    the `active` reactive. It is the BAREST of the two routes: if it is
    stable, the click route is too.

    This was the one that flickered under load (the review measured 8 out
    of 15 losing the tab). The reason was in the PRODUCT, not here, and
    the race only becomes deterministic when the delayed focus is fired by
    hand — which is why the test that guards the root cause is the
    neighbour `test_focus_in_an_inactive_pane_does_not_switch_tabs`, not
    this one.
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


@pytest.mark.asyncio
async def test_focus_in_an_inactive_pane_does_not_switch_tabs(tmp_config_dir):
    """Focusing a widget from ANOTHER tab must not drag the active tab
    along with it.

    This is the root of the instability of the three tab traversals in
    this file. The stock `TabbedContent` responds to `TabPane.Focused`
    with ``self.active = pane.id``, and every dbqm screen schedules its
    own initial focus (`call_after_refresh` in `on_mount`). Switching
    tabs during mount let the delayed focus of the previous screen undo
    the switch.

    The `focus()` below is literally what those screens do — and it works
    even with the pane already hidden by the `ContentSwitcher`, which was
    what made the race invisible. What is asserted is what the screen
    PAINTS, not just the value of `active`: with the wrong tab active, it
    is the Conexoes content that shows up.
    """
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.query_one("#main-tabs", TabbedContent)
        tabs.active = "tab-historico"
        await pilot.pause()

        intruso = next(
            w for w in app.query_one("#connections-screen").query("*") if w.can_focus
        )
        intruso.focus()
        await pilot.pause()

        assert tabs.active == "tab-historico"
        pintado = rendered_text(app)
        assert "HISTORICO" in pintado
        assert "CONEXOES" not in pintado


@pytest.mark.asyncio
async def test_function_key_at_startup_reaches_the_requested_tab(tmp_config_dir):
    """An `F5` pressed BEFORE the mount settles must not be swallowed.

    Measured in the product before the fix: `f5` with zero pauses ended up
    at `active='tab-conexoes'` with seven panes still disabled — the key
    looked as if it had never existed. Here the key is pressed at the
    earliest possible instant, with no settling pause before it.
    """
    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.press("f5")
        # The delayed focus that the Conexoes screen schedules in its own
        # `on_mount` arrives AFTER the key. Fired here on purpose, so the
        # race always happens — left loose, it only showed up once every
        # ten runs, and a test that fails 1/10 of the time guards nothing.
        intruso = next(
            w for w in app.query_one("#connections-screen").query("*") if w.can_focus
        )
        intruso.focus()
        for _ in range(4):
            await pilot.pause()
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-historico"


def test_dbqm_app_registers_and_activates_theme_on_construction(tmp_config_dir):
    """DBQMApp must register and activate the theme in __init__, before the
    first compose/mount — not in on_mount. The DEFAULT_CSS of widgets such
    as Panel uses pure tokens (e.g. `$ds-border`) which, unlike
    `$accent`/`$primary`, are not built-in Textual variables: they only
    exist when one of our themes is registered AND active. If the
    registration moves back to on_mount (or is removed), the first mount
    breaks with UnresolvedVariableError before this test even gets to run
    `run_test()`.

    On purpose it uses no helper/fixture that registers the theme from the
    outside (see tests/ui/_helpers.ThemedTestApp) — that would only prove
    that the helper works, not that the real DBQMApp manages on its own.
    """
    from dbqm.ui.theme import TEXTUAL_THEMES

    app = DBQMApp()

    for nome in TEXTUAL_THEMES:
        assert nome in app.available_themes, f"tema {nome} nao registrado na construcao"
    assert app.theme in TEXTUAL_THEMES, f"tema ativo ({app.theme!r}) nao e um dos nossos"


# ======================================================================
# Settings routes -> hosted screens
#
# These screens were UNREACHABLE from v1.17.0 until here. `#screen-area`
# went away in e02b8a8 ("single tabbed shell") and three call sites kept
# querying for it: `settings._open_portability`, `settings._open_oracle_
# clients` and `config_port._go_back_to_settings`. All of them fell into
# the `except Exception` and notified "Erro: No nodes match '#screen-area'".
#
# Why the tests here mount the REAL DBQMApp, and not the screen on its
# own: a test that did `yield OracleClientsScreen()` in a harness of its
# own would have stayed green during the six weeks in which the product
# had no way of reaching that screen. The defect was not in the screen —
# it was in the path to it. So the path is what gets exercised: switch
# tabs, choose from the list, and assert what the screen PAINTS.
# ======================================================================


async def _open_config_tool(pilot, app, key):
    """Walk the real path: Configuracoes tab -> list -> Enter."""
    from textual.widgets import OptionList

    await pilot.press("f6")
    await pilot.pause()
    lista = app.query_one("#settings-ferramentas-list", OptionList)
    lista.focus()
    await pilot.pause()
    alvo = next(
        i
        for i in range(lista.option_count)
        if lista.get_option_at_index(i).name == key
    )
    lista.highlighted = alvo
    await pilot.press("enter")
    await pilot.pause()
    await pilot.wait_for_scheduled_animations()
    await pilot.pause()
    return lista


@pytest.mark.asyncio
async def test_settings_opens_the_oracle_clients_manager(tmp_config_dir):
    """The screen that manages the Instant Client has to be reachable.

    This is not tidying up: the Instant Client is the subject of the
    v1.18.0 fix, for 32/64-bit ORACLE_HOME conflicts that were bringing
    down connections such as MGORA7ORA9 in production. With the route
    dead, the user's only way out was to edit the configuration by hand.
    """
    from dbqm.ui.screens.oracle_clients import OracleClientsScreen
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_config_tool(pilot, app, "oracle-clients")

        assert app.query(OracleClientsScreen), (
            "a tela de Oracle Instant Clients nao foi montada pela rota real"
        )
        pintado = rendered_text(app)
        assert "PLATAFORMA DETECTADA" in pintado, (
            "a tela montou mas nao e desenhada: %r" % pintado[:400]
        )
        assert "No nodes match" not in pintado


@pytest.mark.asyncio
async def test_settings_opens_export_import(tmp_config_dir):
    """Export/Import configuration was also dead since v1.17.0."""
    from dbqm.ui.screens.config_port import ConfigPortScreen
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_config_tool(pilot, app, "portabilidade")

        assert app.query(ConfigPortScreen), (
            "a tela de Exportar/Importar nao foi montada pela rota real"
        )
        assert "EXPORTAR" in rendered_text(app).upper()


@pytest.mark.asyncio
async def test_escape_returns_from_the_tool_to_settings(tmp_config_dir):
    """Going back is a key, not a button: `Esc` undoes the trip (section 7
    of the grammar).

    `OracleClientsScreen` never had a back button — without this keyboard
    route it would be a dead end inside the tab.
    """
    from dbqm.ui.screens.oracle_clients import OracleClientsScreen
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_config_tool(pilot, app, "oracle-clients")
        assert app.query(OracleClientsScreen)

        await pilot.press("escape")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = rendered_text(app)
        assert "PLATAFORMA DETECTADA" not in pintado, "Esc nao voltou"
        assert "ORACLE INSTANT CLIENT" in pintado.upper(), (
            "voltou para lugar nenhum: %r" % pintado[:400]
        )


@pytest.mark.asyncio
async def test_back_from_config_port_returns_to_settings(tmp_config_dir):
    """The way out of config_port works — and it is now `Esc`, not a button.

    History this test keeps: the "Voltar" that used to live at
    `config_port.py:177` mounted a fresh `SettingsScreen` inside
    `#screen-area`, a container removed in v1.17.0, and for six weeks it
    only notified "Erro: No nodes match". Task 7 brought the route back to
    life; Task 8 removed the BUTTON, because going back is navigation and
    section 7 of the grammar forbids a button that navigates. What is
    asserted here is the route, which is what was dead — not the widget
    that triggered it.
    """
    from dbqm.ui.screens.config_port import ConfigPortScreen
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_config_tool(pilot, app, "portabilidade")
        tela = app.query_one(ConfigPortScreen)

        # Enter a DEEP phase: that is where going back has to work from.
        tela._show_export_phase()
        await pilot.pause()
        assert tela.query_one("#cp-export-phase").display is True

        app.action_go_back()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        # The screen stays mounted (an export worker may still be alive);
        # what has to change is what the tab PAINTS.
        pintado = rendered_text(app).upper()
        assert "EXPORTAR OU IMPORTAR" not in pintado, "o Voltar nao voltou"
        assert "MAIS CONFIGURACOES" in pintado


@pytest.mark.asyncio
async def test_no_settings_route_fails_silently(tmp_config_dir):
    """The route arrives, and it arrives without reporting an error through
    ANY channel.

    The previous version of this test only looked at the toast, because
    the toast was the historical symptom (`except Exception` + `notify`).
    It passed with the REBUILT route broken: without the `except`, a
    `NoMatches` leaves the handler without turning into a toast, and the
    test stayed green with the screen not opening. A test that only
    watches yesterday's symptom does not watch the defect.

    So here all three channels through which a route failure can come out
    are checked — the screen not showing up, an error toast, a stacked
    error modal — and not just the middle one.
    """
    from tests.ui._helpers import rendered_text

    esperado = {
        "portabilidade": "EXPORTAR OU IMPORTAR",
        "oracle-clients": "PLATAFORMA DETECTADA",
    }
    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        for chave, marca in esperado.items():
            await _open_config_tool(pilot, app, chave)
            assert marca in rendered_text(app).upper(), (
                "a rota %r nao chegou: %r nao e desenhado" % (chave, marca)
            )
            assert len(app.screen_stack) == 1, (
                "a rota %r empilhou um modal (de erro?): %r"
                % (chave, app.screen_stack)
            )
            app.action_go_back()
            await pilot.pause()
        erros = [
            n.message for n in app._notifications if n.severity == "error"
        ]
        assert not erros, "rota de Configuracoes notificou erro: %r" % erros


@pytest.mark.asyncio
async def test_hosted_screen_says_which_key_goes_back(tmp_config_dir):
    """`Esc` is the only way out of a hosted screen, and it has to be SAID.

    `DBQMApp.compose` does not yield a `Footer`, so the app's
    `Binding("escape", "go_back", "Back")` shows up nowhere, and
    `OracleClientsScreen` never had a back button: the way out existed and
    nothing on the screen mentioned it. Section 7 of the grammar forbids a
    BUTTON that navigates — it does not forbid saying which key goes back.

    The assertion is about the PAINTED line, and not about
    `ActionBar._actions`: the bar measured two lines and the StatusBar
    covered the second one, so the actions were in `_actions` and on no
    screen at all.
    """
    from tests.ui._helpers import rendered_lines, rendered_text

    def anuncia_voltar(app):
        return any(
            "Esc" in linha and "Voltar" in linha
            for linha in rendered_lines(app)
        )

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        assert not anuncia_voltar(app), (
            "nos paineis nao ha de onde voltar; anunciar `Esc` seria mentira"
        )

        await _open_config_tool(pilot, app, "oracle-clients")
        assert anuncia_voltar(app), (
            "a tela hospedada nao diz como se sai dela: %r"
            % rendered_lines(app)[-4:]
        )

        # Leaving the tab and coming back must not erase the announcement:
        # the hosted screen is still in front. What restores it is
        # `SettingsScreen._set_actions`, which
        # `on_tabbed_content_tab_activated` looks up by name.
        await pilot.press("f1")
        await pilot.pause()
        await pilot.press("f6")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert anuncia_voltar(app), "trocar de aba e voltar apagou o anuncio"

        # And what it announces also works by CLICK, which is the other way
        # of triggering the bar. Clicked where it is written, and not by
        # calling `action_select_action` by hand: outside the bar's own
        # message processing the `_sender` of `ActionSelected` is not the
        # `ActionBar`, and the app's forwarding (which checks the sender so
        # as not to loop) does not happen — a test like that would measure
        # a route the click does not use.
        linhas = rendered_lines(app)
        y = next(
            i for i, linha in enumerate(linhas)
            if "Esc" in linha and "Voltar" in linha
        )
        await pilot.click(offset=(linhas[y].index("Voltar"), y))
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert "PLATAFORMA DETECTADA" not in rendered_text(app).upper()
        assert not anuncia_voltar(app), "voltou, e o anuncio ficou"


@pytest.mark.asyncio
async def test_reopening_export_import_returns_to_the_mode_choice(tmp_config_dir):
    """Reopening from the list shows what the list promised, not the old
    phase.

    The screen stays MOUNTED after the `Esc` — that protects the 150+ MB
    download worker of the clients manager, which writes into its own
    tree. `ConfigPortScreen` has nothing of the sort, and staying mounted
    there meant reopening at the phase where it had stopped: whoever
    exported once ran into the export form again, even though the entry
    they had just chosen is called "Exportar / Importar".
    """
    from dbqm.ui.screens.config_port import ConfigPortScreen
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_config_tool(pilot, app, "portabilidade")
        tela = app.query_one(ConfigPortScreen)
        tela._show_export_phase()
        await pilot.pause()
        assert "EXPORTAR CONFIGURACOES" in rendered_text(app).upper()

        await pilot.press("escape")
        await pilot.pause()
        await _open_config_tool(pilot, app, "portabilidade")

        pintado = rendered_text(app).upper()
        assert "EXPORTAR OU IMPORTAR" in pintado, (
            "reabriu numa fase que a entrada da lista nao prometeu: %r"
            % pintado[-600:]
        )
        assert "CONFIRMAR SENHA" not in pintado, (
            "o formulario de exportacao continua na frente ao reabrir"
        )


@pytest.fixture
def dois_clients_instalados(tmp_config_dir, monkeypatch):
    """Two Instant Clients installed, and the architecture validation off.

    Without this the test would depend on what exists on the machine of
    whoever runs it: `list_installed_clients` really scans `CLIENTS_DIR`
    and `validate_oracle_client_dir` opens the DLL to check 32/64 bits.
    What we want to exercise here is the screen's route, not the
    detection.
    """
    import dbqm.core.db_manager as dbm
    import dbqm.core.oracle_client_installer as oci
    import dbqm.ui.screens.oracle_clients as oc

    base = tmp_config_dir / "clients"
    base.mkdir()
    for nome in ("instantclient_19_x64", "instantclient_23_x64"):
        (base / nome).mkdir()

    monkeypatch.setattr(dbm, "validate_oracle_client_dir", lambda caminho: None)
    monkeypatch.setattr(oci, "CLIENTS_DIR", base)
    monkeypatch.setattr(oc, "CLIENTS_DIR", base)
    return base


@pytest.mark.asyncio
async def test_clients_manager_opens_in_a_titled_panel(
    dois_clients_instalados, tmp_config_dir
):
    """Opening the manager must not land in the middle of a table with no
    header.

    The screen is taller than 24 lines and Textual scrolls to whatever
    receives focus. With the initial focus on the AVAILABLE table — the
    third panel — the manager opened scrolled all the way there, and the
    first thing after choosing the list entry was a table with no title
    above it: nothing said which screen the person had just entered.

    Measured on the real path, at 80x24, which is where the scrolling
    exists: in a tall terminal the whole screen fits and the defect does
    not show up.
    """
    from tests.ui._helpers import rendered_lines

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_config_tool(pilot, app, "oracle-clients")

        # The first lines painted below the tab strip: that is where there
        # has to be a panel title saying where the person has landed.
        topo = [linha for linha in rendered_lines(app)[3:] if linha.strip()][:3]
        assert any(
            "PLATAFORMA DETECTADA" in linha or "CLIENTS INSTALADOS" in linha
            for linha in topo
        ), ("a tela abriu no meio de um painel, sem titulo a vista: %r" % topo)


@pytest.mark.asyncio
async def test_choosing_a_client_updates_the_status_on_return(
    dois_clients_instalados, tmp_config_dir
):
    """The `Client em uso` label must not contradict what was just saved.

    This is the worst possible moment for the label to go stale: the route
    to the manager was designed around it — whoever needs the manager is
    looking at `Client em uso`, and the list entry sits right next to that
    status on purpose. If after choosing a client the label keeps showing
    the previous one, the screen contradicts the configuration it has just
    written itself.

    The assertion is about the text PAINTED after the `Esc`, not about
    `load_settings()`: the defect was exactly a correct configuration with
    a wrong screen on top of it.
    """
    from textual.widgets import Button, DataTable
    from dbqm.models.settings import Settings, load_settings, save_settings
    from tests.ui._helpers import rendered_text

    antigo = dois_clients_instalados / "instantclient_23_x64"
    novo = dois_clients_instalados / "instantclient_19_x64"
    save_settings(Settings(oracle_client_dir=str(antigo)))

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        antes = rendered_text(app)
        assert "instantclient_23_x64" in antes, (
            "o teste nao partiu do estado que descreve: %r" % antes[:400]
        )

        await _open_config_tool(pilot, app, "oracle-clients")
        tabela = app.query_one("#oc-installed-table", DataTable)
        tabela.move_cursor(row=0)
        await pilot.pause()
        app.query_one("#oc-use-btn", Button).press()
        await pilot.pause()
        assert load_settings().oracle_client_dir == str(novo), (
            "o gerenciador nao gravou a escolha — o teste mediria outra coisa"
        )

        await pilot.press("escape")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        depois = rendered_text(app)
        assert "instantclient_19_x64" in depois, (
            "o `Client em uso` nao acompanhou a escolha: %r" % depois[:600]
        )
        assert "instantclient_23_x64" not in depois, (
            "o `Client em uso` ainda mostra o client anterior: %r" % depois[:600]
        )


# ======================================================================
# Tools — menu and list, and going back is a key (grammar, section 7)
# ======================================================================


async def _open_tool(pilot, app, key):
    """Walk the real path: Ferramentas tab -> list -> Enter."""
    from textual.widgets import OptionList

    await pilot.press("f8")
    await pilot.pause()
    lista = app.query_one("#ferr-menu-list", OptionList)
    lista.focus()
    await pilot.pause()
    alvo = next(
        i
        for i in range(lista.option_count)
        if lista.get_option_at_index(i).name == key
    )
    lista.highlighted = alvo
    await pilot.press("enter")
    await pilot.pause()
    await pilot.wait_for_scheduled_animations()
    await pilot.pause()
    return lista


@pytest.mark.asyncio
async def test_tools_shows_all_five_at_80x24(tmp_config_dir):
    """All five tools fit on the screen — before, two sat below the fold.

    Measured on the real DBQMApp at 80x24: five full-width buttons cost 4
    lines each (3 of button + 1 of margin) = 20 lines in a body of 14, and
    `Executar Rotina` and `Executar Grupo` only showed up after scrolling.
    A menu whose last entries do not show up is not a menu.

    Against the DBQMApp and not against a single-screen harness: mounted
    on its own, `ToolsScreen` gets the whole 24 lines; in the product it
    has 20, and it was in that difference that the defect lived.
    """
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f8")
        await pilot.pause()
        pintado = rendered_text(app)
        for nome in (
            "Gerenciar Grupos",
            "Gerenciar Templates",
            "Package Editor",
            "Executar Rotina",
            "Executar Grupo",
        ):
            assert nome in pintado, (
                "%r nao aparece a 80x24: %r" % (nome, pintado[:800])
            )


@pytest.mark.asyncio
async def test_tools_announces_esc_and_esc_goes_back(tmp_config_dir):
    """The way out of a tool is `Esc`, and the action bar DRAWS it.

    Asserts the PAINTED output, not `ActionBar._actions`: the bar existed
    on every screen and rendered on none, because the StatusBar covered
    its text line — and no test saw it, because they all asserted the
    attribute.
    """
    from dbqm.ui.screens.template_manage import TemplateManageScreen
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_tool(pilot, app, "templates")
        assert app.query(TemplateManageScreen), "a ferramenta nao foi montada"

        pintado = rendered_text(app)
        assert "Voltar" in pintado, (
            "a unica saida da ferramenta nao esta escrita em lugar nenhum: %r"
            % pintado[-400:]
        )

        await pilot.press("escape")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = rendered_text(app)
        assert "FERRAMENTAS" in pintado.upper(), (
            "o Esc nao voltou para o menu: %r" % pintado[:600]
        )
        assert "Package Editor" in pintado


@pytest.mark.asyncio
async def test_the_tools_back_action_does_not_leak_to_another_tab(tmp_config_dir):
    """The pinned action belongs to the tab that put it there.

    `Esc Voltar` is a promise: pressing Esc returns to the Ferramentas
    menu. In Conexoes it goes back nowhere, and a bar that promises a way
    out that does not exist is worse than an empty bar. Fails if
    `DBQMApp.on_tabbed_content_tab_activated` stops clearing the pinned
    action when switching tabs.
    """
    from dbqm.ui.widgets.action_bar import ActionBar
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_tool(pilot, app, "templates")
        assert "Voltar" in rendered_text(app), (
            "o teste nao partiu do estado que descreve"
        )

        await pilot.press("f2")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        barra = app.query_one(ActionBar)
        assert barra._pinned_action is None
        pintado = rendered_text(app)
        assert "Voltar" not in pintado, (
            "o Esc Voltar das Ferramentas sobrou em Conexoes: %r"
            % pintado[-300:]
        )
        assert "Nova" in pintado, (
            "a aba nova nem pintou suas proprias acoes: %r" % pintado[-300:]
        )

        # And coming back brings BOTH back: the tool's own actions (which
        # `_reask_tool` rebuilds) and the way out.
        await pilot.press("f8")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        pintado = rendered_text(app)
        assert "Voltar" in pintado, (
            "a saida sumiu ao reentrar na aba: %r" % pintado[-300:]
        )
        assert "Renomear" in pintado, (
            "as acoes da ferramenta nao voltaram: %r" % pintado[-300:]
        )
        assert "Nova" not in pintado, (
            "sobrou acao da aba Conexoes: %r" % pintado[-300:]
        )


# ======================================================================
# The Consultas list: a description continuation never in the identity
# column.
#
# This is the defect that opened the whole phase, in the maintainer's
# words: "a lista de conexoes acima de duas linhas fica dificil de
# distinguir quando termina o nome de uma conexao e quando comeca outra".
# Conexoes was cured; Consultas stayed sick at EVERY width, because
# `query_list` handed the description over as one long line and Textual's
# automatic wrapping (done at render time, after the `Content` is
# assembled) has no way of indenting the continuation.
#
# The two tests below cover the two sides of the same cure: the one above
# proves the ARITHMETIC against the mounted widget, the one below proves
# the RENDERED output. Neither on its own is enough — the sum can add up
# on paper and the screen still come out crooked, and the rendered output
# at a single size does not say that the sum holds at the others.
# ======================================================================


def _queries_with_long_description(quantidade: int = 24):
    """Enough queries for the list to SCROLL, half of them with a
    description that does not fit on one line of the panel."""
    from dbqm.models.query import Query

    longa = (
        "Descricao longa o bastante para transbordar a largura do painel "
        "e provar a hierarquia do item em mais de uma quebra por largura."
    )
    return [
        Query(
            name=f"Consulta {i:02d}",
            sql="select 1 from dual",
            connection="ASDADM",
            table="ASD",
            description=longa if i % 2 == 0 else "curta",
        )
        for i in range(quantidade)
    ]


async def _open_queries(pilot):
    await pilot.pause()
    await pilot.press("f7")
    await pilot.pause()
    await pilot.wait_for_scheduled_animations()
    await pilot.pause()


@pytest.mark.asyncio
async def test_query_list_wrap_width_fits_while_scrolling(tmp_config_dir):
    """`_TEXT_WIDTH` was derived assuming the worst case (scrollbar
    present). Proves the assumption against the mounted widget.

    Measures WITH THE LIST SCROLLING and reads `scrollable_content_region`,
    not `content_region`: the lesson that closed the same fix in Conexoes
    after three failed rounds is that `content_region` does NOT subtract
    the scrollbar — a width derived from it with a short list passes the
    test and comes out wrong in use. The assertion is the RELATION (text +
    indent fits in what is left), not a hardcoded number: a hardcoded
    number ages along with the CSS without warning.
    """
    from textual.widgets import OptionList
    from dbqm.models.query import save_queries
    from dbqm.ui.widgets.hierarchical_list import _INDENT
    from dbqm.ui.widgets.query_list import _TEXT_WIDTH

    save_queries(_queries_with_long_description())

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_queries(pilot)
        lista = app.query_one("#ql-listview", OptionList)
        assert lista.show_vertical_scrollbar, (
            "o teste so prova o pior caso se a lista estiver realmente "
            "rolando"
        )
        assert _TEXT_WIDTH + len(_INDENT) <= lista.scrollable_content_region.width


@pytest.mark.asyncio
@pytest.mark.parametrize("tamanho", [(80, 24), (120, 34)])
async def test_query_description_never_falls_into_the_identity_column(
    tmp_config_dir, tamanho
):
    """No description line may start in the identity column.

    Asserts what the screen PAINTS, on the real DBQMApp, inside the usable
    region of the `OptionList` itself — and not an attribute of the
    `Content`, which stayed green with the defect present (the `Content`
    always had the indent; what lost it was the render's wrapping).

    Measured before the fix, at both widths: the continuation of
    "Descricao longa..." came out at `indent=0`, right up against the
    column of the next `☆ Consulta ...`. Both widths are here because the
    automatic wrapping falls at different points in each one — a single
    one does not prove that the wrap width holds at the others.
    """
    from textual.widgets import OptionList
    from dbqm.models.query import save_queries
    from tests.ui._helpers import rendered_lines

    save_queries(_queries_with_long_description())

    app = DBQMApp()
    async with app.run_test(size=tamanho) as pilot:
        await _open_queries(pilot)
        lista = app.query_one("#ql-listview", OptionList)
        assert lista.show_vertical_scrollbar, (
            "o defeito so aparece com a lista rolando (a barra rouba 2 "
            "colunas): o teste nao partiu do estado que descreve"
        )

        regiao = lista.scrollable_content_region
        painted = rendered_lines(app)
        linhas = [
            painted[y][regiao.x : regiao.x + regiao.width]
            for y in range(regiao.y, min(regiao.y + regiao.height, len(painted)))
        ]

        # The identity is the only line allowed to touch column 0 — and it
        # announces itself with the favourite star.
        continuacoes = [
            linha for linha in linhas
            if linha.strip() and not linha.startswith((" ", "★", "☆"))
        ]
        assert not continuacoes, (
            "linha de descricao/desambiguacao na coluna da identidade "
            "em %sx%s: %r" % (tamanho[0], tamanho[1], continuacoes)
        )

        # And the list really did show a description of more than one line
        # — otherwise the test would pass for having nothing to check.
        recuadas = [linha for linha in linhas if linha.startswith("  Descricao longa")]
        assert recuadas, "nenhuma descricao longa foi pintada: %r" % linhas
        continuacao = [linha for linha in linhas if linha.startswith("  provar a hierarquia")]
        assert continuacao, (
            "a descricao coube numa linha so; sem transbordo nao ha o que "
            "provar: %r" % linhas
        )


# ======================================================================
# The Grupos list (Ferramentas -> Executar Grupo): the THIRD and last
# occurrence of the same defect.
#
# Conexoes was cured in Task 4, Consultas in the previous commit, and
# this list stayed sick for the exact same reason: `_group_option` handed
# the group description — free user text — whole over to
# `hierarchical_item`, the panel was elastic, and Textual's automatic
# wrapping (done at render time, after the `Content` is assembled) has no
# way of indenting the continuation. Measured on the real DBQMApp, with
# the list scrolling:
#
#   BEFORE, 80x24                               BEFORE, 120x34
#   indent 0 :: 'Grupo 00'                      indent 0 :: 'Grupo 00'
#   indent 2 :: '  2 consultas'                 indent 2 :: '  2 consultas'
#   indent 2 :: '  Descricao longa o bast...'   indent 2 :: '  Descricao longa o ba...'
#   indent 0 :: 'provar a hierarquia do ...'    indent 0 :: 'uma quebra por largura.'
#   indent 0 :: 'Grupo 01'                      indent 0 :: 'Grupo 01'
#
# The fourth line is the CONTINUATION of the third and comes out in
# column 0 — the same column as the identity of the next group.
#
# The same pair of tests as the other two lists: the one above proves the
# ARITHMETIC against the mounted widget, the one below proves the
# RENDERED output.
# ======================================================================


def _groups_with_long_description(quantidade: int = 24):
    """Enough groups for the list to SCROLL, half of them with a
    description that does not fit on one line of the panel."""
    from dbqm.models.group import Group

    longa = (
        "Descricao longa o bastante para transbordar a largura do painel "
        "e provar a hierarquia do item em mais de uma quebra por largura."
    )
    return [
        Group(
            name=f"Grupo {i:02d}",
            description=longa if i % 2 == 0 else "curta",
            queries=["q1", "q2"],
            join_key="ID",
        )
        for i in range(quantidade)
    ]


@pytest.mark.asyncio
async def test_group_list_wrap_width_fits_while_scrolling(tmp_config_dir):
    """`group_run`'s `_TEXT_WIDTH` was derived assuming the worst case
    (scrollbar present). Proves the assumption against the mounted widget.

    Measures WITH THE LIST SCROLLING and reads `scrollable_content_region`,
    not `content_region`: the lesson that cost three rounds in Conexoes is
    that `content_region` does NOT subtract the scrollbar — a width
    derived from it on a short list passes the test and comes out wrong in
    use. The assertion is the RELATION (text + indent fits in what is
    left), not a hardcoded number, which would age along with the CSS
    without warning.
    """
    from textual.widgets import OptionList
    from dbqm.models.group import save_groups
    from dbqm.ui.screens.group_run import _TEXT_WIDTH
    from dbqm.ui.widgets.hierarchical_list import _INDENT

    save_groups(_groups_with_long_description())

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_tool(pilot, app, "executar")
        lista = app.query_one("#gr-group-list", OptionList)
        assert lista.show_vertical_scrollbar, (
            "o teste so prova o pior caso se a lista estiver realmente "
            "rolando"
        )
        assert _TEXT_WIDTH + len(_INDENT) <= lista.scrollable_content_region.width


@pytest.mark.asyncio
@pytest.mark.parametrize("tamanho", [(80, 24), (120, 34)])
async def test_group_description_never_falls_into_the_identity_column(
    tmp_config_dir, tamanho
):
    """No description line may start in the identity column.

    Asserts what the screen PAINTS, on the real DBQMApp, inside the usable
    region of the `OptionList` itself — and not an attribute of the
    `Content`, which stayed green with the defect present (the `Content`
    always had the indent; what lost it was the render's wrapping).

    The identity here has no favourite star like the one in Consultas, so
    the column-0 line is checked against the group NAMES: only they may
    touch it. Both widths are here because the automatic wrapping falls at
    different points in each one — a single one does not prove that the
    wrap width holds at the others.
    """
    from textual.widgets import OptionList
    from dbqm.models.group import save_groups
    from tests.ui._helpers import rendered_lines

    grupos = _groups_with_long_description()
    save_groups(grupos)
    identidades = {g.name for g in grupos}

    app = DBQMApp()
    async with app.run_test(size=tamanho) as pilot:
        await _open_tool(pilot, app, "executar")
        lista = app.query_one("#gr-group-list", OptionList)
        assert lista.show_vertical_scrollbar, (
            "o defeito so aparece com a lista rolando (a barra rouba 2 "
            "colunas): o teste nao partiu do estado que descreve"
        )

        regiao = lista.scrollable_content_region
        painted = rendered_lines(app)
        linhas = [
            painted[y][regiao.x : regiao.x + regiao.width]
            for y in range(regiao.y, min(regiao.y + regiao.height, len(painted)))
        ]

        continuacoes = [
            linha for linha in linhas
            if linha.strip() and not linha.startswith(" ")
            and linha.strip() not in identidades
        ]
        assert not continuacoes, (
            "linha de descricao na coluna da identidade em %sx%s: %r"
            % (tamanho[0], tamanho[1], continuacoes)
        )

        # And the list really did paint a description of more than one line
        # — otherwise the test would pass for having nothing to check.
        recuadas = [linha for linha in linhas if linha.startswith("  Descricao longa")]
        assert recuadas, "nenhuma descricao longa foi pintada: %r" % linhas
        continuacao = [linha for linha in linhas if linha.startswith("  provar a hierarquia")]
        assert continuacao, (
            "a descricao coube numa linha so; sem transbordo nao ha o que "
            "provar: %r" % linhas
        )
