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


def test_dbqm_app_registra_e_ativa_tema_na_construcao(tmp_config_dir):
    """DBQMApp precisa registrar e ativar o tema em __init__, antes do
    primeiro compose/mount — nao em on_mount. O DEFAULT_CSS de widgets como
    Panel usa tokens puros (ex.: `$borda`), que ao contrario de
    `$accent`/`$primary` nao sao variavel embutida do Textual: so existem
    quando um dos nossos temas esta registrado E ativo. Se o registro
    voltar para on_mount (ou for removido), o primeiro mount quebra com
    UnresolvedVariableError antes mesmo deste teste rodar `run_test()`.

    De proposito nao usa nenhum helper/fixture que registre tema por fora
    (ver tests/ui/_helpers.ThemedTestApp) — isso provaria so que o helper
    funciona, nao que a DBQMApp real se vira sozinha.
    """
    from dbqm.ui.theme import TEMAS_TEXTUAL

    app = DBQMApp()

    for nome in TEMAS_TEXTUAL:
        assert nome in app.available_themes, f"tema {nome} nao registrado na construcao"
    assert app.theme in TEMAS_TEXTUAL, f"tema ativo ({app.theme!r}) nao e um dos nossos"


# ======================================================================
# Rotas de Configuracoes -> telas hospedadas
#
# Estas telas ficaram INALCANCAVEIS da v1.17.0 ate aqui. `#screen-area`
# saiu em e02b8a8 ("single tabbed shell") e tres chamadas continuaram
# consultando-o: `settings._open_portability`, `settings._open_oracle_
# clients` e `config_port._go_back_to_settings`. Todas caiam no
# `except Exception` e notificavam "Erro: No nodes match '#screen-area'".
#
# Por que os testes daqui montam a DBQMApp REAL, e nao a tela sozinha:
# um teste que fizesse `yield OracleClientsScreen()` num harness proprio
# teria passado verde durante as seis semanas em que o produto nao tinha
# como chegar naquela tela. O defeito nao estava na tela — estava no
# caminho ate ela. Entao o caminho e o que se exercita: trocar de aba,
# escolher na lista, e afirmar o que a tela PINTA.
# ======================================================================


async def _abrir_ferramenta_de_config(pilot, app, chave):
    """Percorre o caminho real: aba Configuracoes -> lista -> Enter."""
    from textual.widgets import OptionList

    await pilot.press("f6")
    await pilot.pause()
    lista = app.query_one("#settings-ferramentas-list", OptionList)
    lista.focus()
    await pilot.pause()
    alvo = next(
        i
        for i in range(lista.option_count)
        if lista.get_option_at_index(i).nome == chave
    )
    lista.highlighted = alvo
    await pilot.press("enter")
    await pilot.pause()
    await pilot.wait_for_scheduled_animations()
    await pilot.pause()
    return lista


@pytest.mark.asyncio
async def test_configuracoes_abre_o_gerenciador_de_oracle_clients(tmp_config_dir):
    """A tela que gerencia o Instant Client precisa ser alcancavel.

    Nao e arrumacao: o Instant Client e o assunto da correcao da v1.18.0,
    para conflitos de ORACLE_HOME 32/64 bits que derrubavam conexoes como
    MGORA7ORA9 em producao. Com a rota morta, a unica saida do usuario era
    editar a configuracao na mao.
    """
    from dbqm.ui.screens.oracle_clients import OracleClientsScreen
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _abrir_ferramenta_de_config(pilot, app, "oracle-clients")

        assert app.query(OracleClientsScreen), (
            "a tela de Oracle Instant Clients nao foi montada pela rota real"
        )
        pintado = texto_renderizado(app)
        assert "PLATAFORMA DETECTADA" in pintado, (
            "a tela montou mas nao e desenhada: %r" % pintado[:400]
        )
        assert "No nodes match" not in pintado


@pytest.mark.asyncio
async def test_configuracoes_abre_exportar_importar(tmp_config_dir):
    """Exportar/Importar configuracao tambem estava morto desde a v1.17.0."""
    from dbqm.ui.screens.config_port import ConfigPortScreen
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _abrir_ferramenta_de_config(pilot, app, "portabilidade")

        assert app.query(ConfigPortScreen), (
            "a tela de Exportar/Importar nao foi montada pela rota real"
        )
        assert "EXPORTAR" in texto_renderizado(app).upper()


@pytest.mark.asyncio
async def test_escape_volta_da_ferramenta_para_as_configuracoes(tmp_config_dir):
    """Voltar e tecla, nao botao: `Esc` desfaz a ida (secao 7 da gramatica).

    `OracleClientsScreen` nunca teve botao de voltar — sem esta rota de
    teclado ela seria um beco sem saida dentro da aba.
    """
    from dbqm.ui.screens.oracle_clients import OracleClientsScreen
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _abrir_ferramenta_de_config(pilot, app, "oracle-clients")
        assert app.query(OracleClientsScreen)

        await pilot.press("escape")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = texto_renderizado(app)
        assert "PLATAFORMA DETECTADA" not in pintado, "Esc nao voltou"
        assert "ORACLE INSTANT CLIENT" in pintado.upper(), (
            "voltou para lugar nenhum: %r" % pintado[:400]
        )


@pytest.mark.asyncio
async def test_voltar_do_config_port_devolve_as_configuracoes(tmp_config_dir):
    """O "Voltar" do proprio config_port (config_port.py:177) tambem estava morto."""
    from textual.widgets import Button
    from dbqm.ui.screens.config_port import ConfigPortScreen
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _abrir_ferramenta_de_config(pilot, app, "portabilidade")
        tela = app.query_one(ConfigPortScreen)

        # A fase de escolha de modo e a inicial quando se entra pela lista.
        tela.query_one("#cp-btn-export", Button).press()
        await pilot.pause()
        tela.query_one("#cp-export-back", Button).press()
        await pilot.pause()
        # Primeiro Voltar: volta uma FASE, dentro da propria tela.
        assert tela.query_one("#cp-mode-phase").display is True

        # O segundo sai da tela e devolve as Configuracoes.
        app.action_go_back()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        # A tela segue montada (um worker de exportacao pode estar vivo);
        # o que tem de mudar e o que a aba PINTA.
        pintado = texto_renderizado(app).upper()
        assert "EXPORTAR OU IMPORTAR" not in pintado, "o Voltar nao voltou"
        assert "MAIS CONFIGURACOES" in pintado


@pytest.mark.asyncio
async def test_nenhuma_rota_de_configuracoes_notifica_erro(tmp_config_dir):
    """Nada de `#screen-area`: o sintoma era um toast de erro, nao um crash.

    Um teste que so afirmasse "a tela montou" passaria mesmo com um erro
    notificado no caminho. Aqui o toast e o que se vigia.
    """
    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        for chave in ("portabilidade", "oracle-clients"):
            await _abrir_ferramenta_de_config(pilot, app, chave)
            app.action_go_back()
            await pilot.pause()
        erros = [
            n.message for n in app._notifications if n.severity == "error"
        ]
        assert not erros, "rota de Configuracoes notificou erro: %r" % erros
