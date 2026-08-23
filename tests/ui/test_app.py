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
    """Ativar a aba pela API do `TabbedContent` troca a aba e deixa o
    painel de destino habilitado.

    Nao e "simular um clique", como dizia a docstring antiga — clique de
    mouse entra por `Tabs`, esta atribuicao entra pela reativa `active`. E
    a rota mais NUA das duas: se ela e estavel, a do clique tambem e.

    Era ela que piscava sob carga (a revisao mediu 8 de 15 perdendo a
    aba). O motivo estava no PRODUTO, nao aqui, e a corrida so vira
    deterministica quando se dispara o foco atrasado a mao — por isso o
    teste que guarda a raiz e o vizinho
    `test_focus_in_an_inactive_pane_does_not_switch_tabs`, nao este.
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
    """Focar um widget de OUTRA aba nao pode arrastar a aba ativa junto.

    E a raiz da instabilidade das tres travessias de aba deste arquivo. O
    `TabbedContent` de fabrica responde a `TabPane.Focused` com
    ``self.active = pane.id``, e toda tela do dbqm agenda o proprio foco
    inicial (`call_after_refresh` no `on_mount`). Trocar de aba durante a
    montagem deixava o foco atrasado da tela anterior desfazer a troca.

    O `focus()` abaixo e literalmente o que essas telas fazem — e funciona
    mesmo com o painel ja escondido pelo `ContentSwitcher`, que era o que
    tornava a corrida invisivel. Afirma-se o que a tela PINTA, nao so o
    valor de `active`: com a aba errada ativa, e o conteudo de Conexoes
    que aparece.
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
    """Um `F5` apertado ANTES de a montagem assentar nao pode ser engolido.

    Medido no produto antes da correcao: `f5` com zero pausas terminava em
    `active='tab-conexoes'` com sete paineis ainda desabilitados — a tecla
    parecia nao ter existido. Aqui a tecla e apertada no primeiro instante
    possivel, sem nenhuma pausa de assentamento antes dela.
    """
    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.press("f5")
        # O foco atrasado que a tela de Conexoes agenda no proprio `on_mount`
        # chega DEPOIS da tecla. Disparado aqui de proposito, para que a
        # corrida aconteca sempre — solta, ela so aparecia uma vez a cada
        # dez execucoes, e um teste que falha 1/10 nao guarda nada.
        intruso = next(
            w for w in app.query_one("#connections-screen").query("*") if w.can_focus
        )
        intruso.focus()
        for _ in range(4):
            await pilot.pause()
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-historico"


def test_dbqm_app_registers_and_activates_theme_on_construction(tmp_config_dir):
    """DBQMApp precisa registrar e ativar o tema em __init__, antes do
    primeiro compose/mount — nao em on_mount. O DEFAULT_CSS de widgets como
    Panel usa tokens puros (ex.: `$ds-border`), que ao contrario de
    `$accent`/`$primary` nao sao variavel embutida do Textual: so existem
    quando um dos nossos temas esta registrado E ativo. Se o registro
    voltar para on_mount (ou for removido), o primeiro mount quebra com
    UnresolvedVariableError antes mesmo deste teste rodar `run_test()`.

    De proposito nao usa nenhum helper/fixture que registre tema por fora
    (ver tests/ui/_helpers.ThemedTestApp) — isso provaria so que o helper
    funciona, nao que a DBQMApp real se vira sozinha.
    """
    from dbqm.ui.theme import TEXTUAL_THEMES

    app = DBQMApp()

    for nome in TEXTUAL_THEMES:
        assert nome in app.available_themes, f"tema {nome} nao registrado na construcao"
    assert app.theme in TEXTUAL_THEMES, f"tema ativo ({app.theme!r}) nao e um dos nossos"


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


async def _open_config_tool(pilot, app, key):
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
    """A tela que gerencia o Instant Client precisa ser alcancavel.

    Nao e arrumacao: o Instant Client e o assunto da correcao da v1.18.0,
    para conflitos de ORACLE_HOME 32/64 bits que derrubavam conexoes como
    MGORA7ORA9 em producao. Com a rota morta, a unica saida do usuario era
    editar a configuracao na mao.
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
    """Exportar/Importar configuracao tambem estava morto desde a v1.17.0."""
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
    """Voltar e tecla, nao botao: `Esc` desfaz a ida (secao 7 da gramatica).

    `OracleClientsScreen` nunca teve botao de voltar — sem esta rota de
    teclado ela seria um beco sem saida dentro da aba.
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
    """A saida do config_port funciona — e agora e o `Esc`, nao um botao.

    Historico que este teste guarda: o "Voltar" que vivia em
    `config_port.py:177` montava uma `SettingsScreen` nova dentro de
    `#screen-area`, um container removido na v1.17.0, e por seis semanas
    so notificava "Erro: No nodes match". A Task 7 ressuscitou a rota; a
    Task 8 tirou o BOTAO, porque voltar e navegacao e a secao 7 da
    gramatica proibe botao que navega. O que se afirma aqui e a rota, que
    e o que estava morto — nao o widget que a acionava.
    """
    from dbqm.ui.screens.config_port import ConfigPortScreen
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_config_tool(pilot, app, "portabilidade")
        tela = app.query_one(ConfigPortScreen)

        # Entrar numa fase FUNDA: e de la que a volta precisa funcionar.
        tela._show_export_phase()
        await pilot.pause()
        assert tela.query_one("#cp-export-phase").display is True

        app.action_go_back()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        # A tela segue montada (um worker de exportacao pode estar vivo);
        # o que tem de mudar e o que a aba PINTA.
        pintado = rendered_text(app).upper()
        assert "EXPORTAR OU IMPORTAR" not in pintado, "o Voltar nao voltou"
        assert "MAIS CONFIGURACOES" in pintado


@pytest.mark.asyncio
async def test_no_settings_route_fails_silently(tmp_config_dir):
    """A rota chega, e chega sem reportar erro por canal NENHUM.

    A versao anterior deste teste so olhava o toast, porque o toast era o
    sintoma historico (`except Exception` + `notify`). Ela passava com a
    rota REMONTADA quebrada: sem o `except`, um `NoMatches` sai do handler
    sem virar toast, e o teste seguia verde com a tela nao abrindo. Um
    teste que so vigia o sintoma de ontem nao vigia o defeito.

    Entao aqui se cobram os tres canais por onde uma falha de rota pode
    sair — a tela nao aparecer, um toast de erro, um modal de erro
    empilhado — e nao so o do meio.
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
    """`Esc` e a unica saida de uma tela hospedada, e ela precisa ser DITA.

    `DBQMApp.compose` nao rende `Footer`, entao o
    `Binding("escape", "go_back", "Back")` do app nao aparece em lugar
    nenhum, e `OracleClientsScreen` nunca teve botao de voltar: a saida
    existia e nada na tela a mencionava. A secao 7 da gramatica proibe um
    BOTAO que navega — nao proibe dizer qual tecla volta.

    A afirmacao e sobre a linha PINTADA, e nao sobre `ActionBar._actions`:
    a barra media duas linhas e a StatusBar cobria a segunda, entao as
    acoes estavam em `_actions` e em tela nenhuma.
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

        # Sair da aba e voltar nao pode apagar o anuncio: a tela hospedada
        # continua na frente. Quem repoe e `SettingsScreen._set_actions`,
        # que `on_tabbed_content_tab_activated` procura pelo nome.
        await pilot.press("f1")
        await pilot.pause()
        await pilot.press("f6")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert anuncia_voltar(app), "trocar de aba e voltar apagou o anuncio"

        # E o que ele anuncia funciona tambem por CLIQUE, que e a outra
        # forma de acionar a barra. Clicado onde esta escrito, e nao
        # chamando `action_select_action` na mao: fora do processamento de
        # mensagem da propria barra o `_sender` da `ActionSelected` nao e a
        # `ActionBar`, e o encaminhamento do app (que confere o remetente
        # para nao entrar em laco) nao acontece — um teste assim mediria
        # uma rota que o clique nao usa.
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
    """Reabrir pela lista mostra o que a lista prometeu, nao a fase antiga.

    A tela continua MONTADA depois do `Esc` — isso protege o worker de
    download de 150+ MB do gerenciador de clients, que escreve na propria
    arvore. `ConfigPortScreen` nao tem nada disso, e ficar montada nela
    significava reabrir na fase em que tinha parado: quem exportou uma vez
    reencontrava o formulario de exportacao, embora a entrada que acabou de
    escolher se chame "Exportar / Importar".
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
    """Dois Instant Clients instalados, e a validacao de arquitetura desligada.

    Sem isto o teste dependeria do que existe na maquina de quem roda:
    `list_installed_clients` varre `CLIENTS_DIR` de verdade e
    `validate_oracle_client_dir` abre a DLL para conferir 32/64 bits. O que
    se quer exercitar aqui e a rota da tela, nao a deteccao.
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
    """Abrir o gerenciador nao pode cair no meio de uma tabela sem cabecalho.

    A tela e mais alta que 24 linhas e o Textual rola ate quem recebe foco.
    Com o foco inicial na tabela de DISPONIVEIS — o terceiro painel — o
    gerenciador abria rolado ate la, e a primeira coisa depois de escolher
    a entrada da lista era uma tabela sem titulo em cima: nada dizia em que
    tela a pessoa tinha acabado de entrar.

    Medido no caminho real, a 80x24, que e onde a rolagem existe: num
    terminal alto a tela inteira cabe e o defeito nao aparece.
    """
    from tests.ui._helpers import rendered_lines

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_config_tool(pilot, app, "oracle-clients")

        # As primeiras linhas pintadas abaixo da tira de abas: e ali que
        # tem de haver um titulo de painel dizendo onde a pessoa entrou.
        topo = [linha for linha in rendered_lines(app)[3:] if linha.strip()][:3]
        assert any(
            "PLATAFORMA DETECTADA" in linha or "CLIENTS INSTALADOS" in linha
            for linha in topo
        ), ("a tela abriu no meio de um painel, sem titulo a vista: %r" % topo)


@pytest.mark.asyncio
async def test_choosing_a_client_updates_the_status_on_return(
    dois_clients_instalados, tmp_config_dir
):
    """O rotulo `Client em uso` nao pode contradizer o que se acabou de salvar.

    Este e o pior momento possivel para o rotulo envelhecer: a rota ate o
    gerenciador foi desenhada em volta dele — quem precisa do gerenciador
    esta olhando para o `Client em uso`, e a entrada da lista fica encostada
    nesse status de proposito. Se depois de escolher um client o rotulo
    continuar mostrando o anterior, a tela desmente a configuracao que ela
    mesma acabou de gravar.

    A afirmacao e sobre o texto PINTADO depois do `Esc`, nao sobre
    `load_settings()`: o defeito era exatamente uma configuracao correta com
    uma tela errada em cima dela.
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
# Ferramentas — menu e lista, e a volta e tecla (gramatica, secao 7)
# ======================================================================


async def _open_tool(pilot, app, key):
    """Percorre o caminho real: aba Ferramentas -> lista -> Enter."""
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
    """As cinco ferramentas cabem na tela — antes, duas ficavam abaixo da dobra.

    Medido na DBQMApp real a 80x24: cinco botoes de largura total custam
    4 linhas cada (3 de botao + 1 de margem) = 20 linhas num corpo de 14,
    e `Executar Rotina` e `Executar Grupo` so apareciam depois de rolar.
    Um menu cujas ultimas entradas nao aparecem nao e um menu.

    Contra a DBQMApp e nao contra um harness de uma tela so: montada
    sozinha, `ToolsScreen` recebe as 24 linhas inteiras; no produto
    ela tem 20, e era nessa diferenca que o defeito morava.
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
    """A saida de uma ferramenta e o `Esc`, e a barra de acoes o DESENHA.

    Afirma o PINTADO, nao `ActionBar._actions`: a barra existia em toda
    tela e nao renderizava em nenhuma, porque a StatusBar cobria a linha
    de texto dela — e nenhum teste viu, porque todos afirmavam o atributo.
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
    """A acao fixa pertence a aba que a pos.

    `Esc Voltar` e uma promessa: apertar Esc devolve ao menu de
    Ferramentas. Em Conexoes ela nao volta para lugar nenhum, e uma barra
    que promete uma saida inexistente e pior que uma barra vazia. Reprova
    se `DBQMApp.on_tabbed_content_tab_activated` deixar de limpar a acao
    fixa ao trocar de aba.
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

        # E voltar traz as DUAS de volta: as da ferramenta (que
        # `_reask_tool` reconstroi) e a saida.
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
# A lista de Consultas: continuacao de descricao nunca na coluna da
# identidade.
#
# Este e o defeito que abriu a fase inteira, nas palavras do mantenedor:
# "a lista de conexoes acima de duas linhas fica dificil de distinguir
# quando termina o nome de uma conexao e quando comeca outra". Conexoes
# foi curada; Consultas seguia doente em TODA largura, porque
# `query_list` entregava a descricao como uma linha longa e a quebra
# automatica do Textual (feita no render, depois do `Content` montado)
# nao tem como recuar a continuacao.
#
# Os dois testes abaixo cobrem os dois lados da mesma cura: o de cima
# prova a ARITMETICA contra o widget montado, o de baixo prova o
# RENDERIZADO. Nenhum dos dois sozinho basta — a conta pode fechar no
# papel e a tela sair torta, e o renderizado de um tamanho so nao diz
# que a conta vale nos outros.
# ======================================================================


def _queries_with_long_description(quantidade: int = 24):
    """Consultas suficientes pra lista ROLAR, metade com descricao que
    nao cabe numa linha do painel."""
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
    """`_TEXT_WIDTH` foi derivada assumindo o pior caso (barra de
    rolagem presente). Prova a suposicao contra o widget montado.

    Mede COM A LISTA ROLANDO e le `scrollable_content_region`, nao
    `content_region`: a licao que fechou a mesma correcao em Conexoes
    depois de tres rodadas falhas e que `content_region` NAO desconta a
    barra de rolagem — uma largura derivada dele com uma lista curta
    passa no teste e sai errada em uso. A afirmacao e a RELACAO (texto +
    recuo cabe no que sobra), nao um numero cravado: um numero cravado
    envelhece junto com o CSS sem avisar.
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
    """Nenhuma linha de descricao pode comecar na coluna da identidade.

    Afirma o que a tela PINTA, na DBQMApp real, dentro da regiao util do
    proprio `OptionList` — e nao um atributo do `Content`, que continuava
    verde com o defeito presente (o `Content` sempre teve o recuo; quem o
    perdia era a quebra do render).

    Medido antes da correcao, nas duas larguras: a continuacao de
    "Descricao longa..." saia em `indent=0`, encostada na coluna do
    `☆ Consulta ...` seguinte. As duas larguras estao aqui porque a
    quebra automatica cai em pontos diferentes em cada uma — uma so nao
    prova que a largura de quebra vale nas outras.
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

        # Identidade e a unica linha que pode encostar na coluna 0 — e ela
        # se anuncia pela estrela de favorito.
        continuacoes = [
            linha for linha in linhas
            if linha.strip() and not linha.startswith((" ", "★", "☆"))
        ]
        assert not continuacoes, (
            "linha de descricao/desambiguacao na coluna da identidade "
            "em %sx%s: %r" % (tamanho[0], tamanho[1], continuacoes)
        )

        # E a lista realmente mostrou uma descricao de mais de uma linha —
        # senao o teste passaria por nao ter o que checar.
        recuadas = [linha for linha in linhas if linha.startswith("  Descricao longa")]
        assert recuadas, "nenhuma descricao longa foi pintada: %r" % linhas
        continuacao = [linha for linha in linhas if linha.startswith("  provar a hierarquia")]
        assert continuacao, (
            "a descricao coube numa linha so; sem transbordo nao ha o que "
            "provar: %r" % linhas
        )


# ======================================================================
# A lista de Grupos (Ferramentas -> Executar Grupo): a TERCEIRA e ultima
# ocorrencia do mesmo defeito.
#
# Conexoes foi curada na Task 4, Consultas no commit anterior, e esta
# lista seguia doente pelo mesmo motivo exato: `_group_option` entregava
# a descricao do grupo — texto livre do usuario — inteira para
# `hierarchical_item`, o painel era elastico, e a quebra automatica do
# Textual (feita no render, depois do `Content` montado) nao tem como
# recuar a continuacao. Medido na DBQMApp real, com a lista rolando:
#
#   ANTES, 80x24                                ANTES, 120x34
#   indent 0 :: 'Grupo 00'                      indent 0 :: 'Grupo 00'
#   indent 2 :: '  2 consultas'                 indent 2 :: '  2 consultas'
#   indent 2 :: '  Descricao longa o bast...'   indent 2 :: '  Descricao longa o ba...'
#   indent 0 :: 'provar a hierarquia do ...'    indent 0 :: 'uma quebra por largura.'
#   indent 0 :: 'Grupo 01'                      indent 0 :: 'Grupo 01'
#
# A quarta linha e a CONTINUACAO da terceira e sai na coluna 0 — a mesma
# coluna da identidade do grupo seguinte.
#
# Mesma dupla de testes das outras duas listas: o de cima prova a
# ARITMETICA contra o widget montado, o de baixo prova o RENDERIZADO.
# ======================================================================


def _groups_with_long_description(quantidade: int = 24):
    """Grupos suficientes pra lista ROLAR, metade com descricao que nao
    cabe numa linha do painel."""
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
    """`_TEXT_WIDTH` de `group_run` foi derivada assumindo o pior caso
    (barra de rolagem presente). Prova a suposicao contra o widget montado.

    Mede COM A LISTA ROLANDO e le `scrollable_content_region`, nao
    `content_region`: a licao que custou tres rodadas em Conexoes e que
    `content_region` NAO desconta a barra de rolagem — uma largura
    derivada dele numa lista curta passa no teste e sai errada em uso. A
    afirmacao e a RELACAO (texto + recuo cabe no que sobra), nao um
    numero cravado, que envelheceria junto com o CSS sem avisar.
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
    """Nenhuma linha de descricao pode comecar na coluna da identidade.

    Afirma o que a tela PINTA, na DBQMApp real, dentro da regiao util do
    proprio `OptionList` — e nao um atributo do `Content`, que continuava
    verde com o defeito presente (o `Content` sempre teve o recuo; quem o
    perdia era a quebra do render).

    A identidade aqui nao tem estrela de favorito como a de Consultas,
    entao a linha da coluna 0 e checada contra os NOMES dos grupos: so
    eles podem encostar nela. As duas larguras estao aqui porque a quebra
    automatica cai em pontos diferentes em cada uma — uma so nao prova
    que a largura de quebra vale nas outras.
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

        # E a lista realmente pintou uma descricao de mais de uma linha —
        # senao o teste passaria por nao ter o que checar.
        recuadas = [linha for linha in linhas if linha.startswith("  Descricao longa")]
        assert recuadas, "nenhuma descricao longa foi pintada: %r" % linhas
        continuacao = [linha for linha in linhas if linha.startswith("  provar a hierarquia")]
        assert continuacao, (
            "a descricao coube numa linha so; sem transbordo nao ha o que "
            "provar: %r" % linhas
        )
