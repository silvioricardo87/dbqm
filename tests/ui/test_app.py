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
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _abrir_ferramenta_de_config(pilot, app, "portabilidade")
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
        pintado = texto_renderizado(app).upper()
        assert "EXPORTAR OU IMPORTAR" not in pintado, "o Voltar nao voltou"
        assert "MAIS CONFIGURACOES" in pintado


@pytest.mark.asyncio
async def test_nenhuma_rota_de_configuracoes_falha_em_silencio(tmp_config_dir):
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
    from tests.ui._helpers import texto_renderizado

    esperado = {
        "portabilidade": "EXPORTAR OU IMPORTAR",
        "oracle-clients": "PLATAFORMA DETECTADA",
    }
    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        for chave, marca in esperado.items():
            await _abrir_ferramenta_de_config(pilot, app, chave)
            assert marca in texto_renderizado(app).upper(), (
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
async def test_tela_hospedada_diz_qual_tecla_volta(tmp_config_dir):
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
    from tests.ui._helpers import linhas_renderizadas, texto_renderizado

    def anuncia_voltar(app):
        return any(
            "Esc" in linha and "Voltar" in linha
            for linha in linhas_renderizadas(app)
        )

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        assert not anuncia_voltar(app), (
            "nos paineis nao ha de onde voltar; anunciar `Esc` seria mentira"
        )

        await _abrir_ferramenta_de_config(pilot, app, "oracle-clients")
        assert anuncia_voltar(app), (
            "a tela hospedada nao diz como se sai dela: %r"
            % linhas_renderizadas(app)[-4:]
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
        linhas = linhas_renderizadas(app)
        y = next(
            i for i, linha in enumerate(linhas)
            if "Esc" in linha and "Voltar" in linha
        )
        await pilot.click(offset=(linhas[y].index("Voltar"), y))
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert "PLATAFORMA DETECTADA" not in texto_renderizado(app).upper()
        assert not anuncia_voltar(app), "voltou, e o anuncio ficou"


@pytest.mark.asyncio
async def test_reabrir_exportar_importar_volta_a_escolha_de_modo(tmp_config_dir):
    """Reabrir pela lista mostra o que a lista prometeu, nao a fase antiga.

    A tela continua MONTADA depois do `Esc` — isso protege o worker de
    download de 150+ MB do gerenciador de clients, que escreve na propria
    arvore. `ConfigPortScreen` nao tem nada disso, e ficar montada nela
    significava reabrir na fase em que tinha parado: quem exportou uma vez
    reencontrava o formulario de exportacao, embora a entrada que acabou de
    escolher se chame "Exportar / Importar".
    """
    from dbqm.ui.screens.config_port import ConfigPortScreen
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _abrir_ferramenta_de_config(pilot, app, "portabilidade")
        tela = app.query_one(ConfigPortScreen)
        tela._show_export_phase()
        await pilot.pause()
        assert "EXPORTAR CONFIGURACOES" in texto_renderizado(app).upper()

        await pilot.press("escape")
        await pilot.pause()
        await _abrir_ferramenta_de_config(pilot, app, "portabilidade")

        pintado = texto_renderizado(app).upper()
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
async def test_gerenciador_de_clients_abre_num_painel_com_titulo(
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
    from tests.ui._helpers import linhas_renderizadas

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await _abrir_ferramenta_de_config(pilot, app, "oracle-clients")

        # As primeiras linhas pintadas abaixo da tira de abas: e ali que
        # tem de haver um titulo de painel dizendo onde a pessoa entrou.
        topo = [linha for linha in linhas_renderizadas(app)[3:] if linha.strip()][:3]
        assert any(
            "PLATAFORMA DETECTADA" in linha or "CLIENTS INSTALADOS" in linha
            for linha in topo
        ), ("a tela abriu no meio de um painel, sem titulo a vista: %r" % topo)


@pytest.mark.asyncio
async def test_escolher_um_client_atualiza_o_status_ao_voltar(
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
    from tests.ui._helpers import texto_renderizado

    antigo = dois_clients_instalados / "instantclient_23_x64"
    novo = dois_clients_instalados / "instantclient_19_x64"
    save_settings(Settings(oracle_client_dir=str(antigo)))

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        antes = texto_renderizado(app)
        assert "instantclient_23_x64" in antes, (
            "o teste nao partiu do estado que descreve: %r" % antes[:400]
        )

        await _abrir_ferramenta_de_config(pilot, app, "oracle-clients")
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

        depois = texto_renderizado(app)
        assert "instantclient_19_x64" in depois, (
            "o `Client em uso` nao acompanhou a escolha: %r" % depois[:600]
        )
        assert "instantclient_23_x64" not in depois, (
            "o `Client em uso` ainda mostra o client anterior: %r" % depois[:600]
        )


# ======================================================================
# Ferramentas — menu e lista, e a volta e tecla (gramatica, secao 7)
# ======================================================================


async def _abrir_ferramenta(pilot, app, chave):
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
        if lista.get_option_at_index(i).nome == chave
    )
    lista.highlighted = alvo
    await pilot.press("enter")
    await pilot.pause()
    await pilot.wait_for_scheduled_animations()
    await pilot.pause()
    return lista


@pytest.mark.asyncio
async def test_ferramentas_mostra_as_cinco_a_80x24(tmp_config_dir):
    """As cinco ferramentas cabem na tela — antes, duas ficavam abaixo da dobra.

    Medido na DBQMApp real a 80x24: cinco botoes de largura total custam
    4 linhas cada (3 de botao + 1 de margem) = 20 linhas num corpo de 14,
    e `Executar Rotina` e `Executar Grupo` so apareciam depois de rolar.
    Um menu cujas ultimas entradas nao aparecem nao e um menu.

    Contra a DBQMApp e nao contra um harness de uma tela so: montada
    sozinha, `FerramentasScreen` recebe as 24 linhas inteiras; no produto
    ela tem 20, e era nessa diferenca que o defeito morava.
    """
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f8")
        await pilot.pause()
        pintado = texto_renderizado(app)
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
async def test_ferramentas_anuncia_o_esc_e_o_esc_volta(tmp_config_dir):
    """A saida de uma ferramenta e o `Esc`, e a barra de acoes o DESENHA.

    Afirma o PINTADO, nao `ActionBar._actions`: a barra existia em toda
    tela e nao renderizava em nenhuma, porque a StatusBar cobria a linha
    de texto dela — e nenhum teste viu, porque todos afirmavam o atributo.
    """
    from dbqm.ui.screens.template_manage import TemplateManageScreen
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await _abrir_ferramenta(pilot, app, "templates")
        assert app.query(TemplateManageScreen), "a ferramenta nao foi montada"

        pintado = texto_renderizado(app)
        assert "Voltar" in pintado, (
            "a unica saida da ferramenta nao esta escrita em lugar nenhum: %r"
            % pintado[-400:]
        )

        await pilot.press("escape")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = texto_renderizado(app)
        assert "FERRAMENTAS" in pintado.upper(), (
            "o Esc nao voltou para o menu: %r" % pintado[:600]
        )
        assert "Package Editor" in pintado


@pytest.mark.asyncio
async def test_o_voltar_das_ferramentas_nao_vaza_para_outra_aba(tmp_config_dir):
    """A acao fixa pertence a aba que a pos.

    `Esc Voltar` e uma promessa: apertar Esc devolve ao menu de
    Ferramentas. Em Conexoes ela nao volta para lugar nenhum, e uma barra
    que promete uma saida inexistente e pior que uma barra vazia. Reprova
    se `DBQMApp.on_tabbed_content_tab_activated` deixar de limpar a acao
    fixa ao trocar de aba.
    """
    from dbqm.ui.widgets.action_bar import ActionBar
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await _abrir_ferramenta(pilot, app, "templates")
        assert "Voltar" in texto_renderizado(app), (
            "o teste nao partiu do estado que descreve"
        )

        await pilot.press("f2")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        barra = app.query_one(ActionBar)
        assert barra._acao_fixa is None
        pintado = texto_renderizado(app)
        assert "Voltar" not in pintado, (
            "o Esc Voltar das Ferramentas sobrou em Conexoes: %r"
            % pintado[-300:]
        )
        assert "Nova" in pintado, (
            "a aba nova nem pintou suas proprias acoes: %r" % pintado[-300:]
        )

        # E voltar traz as DUAS de volta: as da ferramenta (que
        # `_reperguntar_a_ferramenta` reconstroi) e a saida.
        await pilot.press("f8")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        pintado = texto_renderizado(app)
        assert "Voltar" in pintado, (
            "a saida sumiu ao reentrar na aba: %r" % pintado[-300:]
        )
        assert "Renomear" in pintado, (
            "as acoes da ferramenta nao voltaram: %r" % pintado[-300:]
        )
        assert "Nova" not in pintado, (
            "sobrou acao da aba Conexoes: %r" % pintado[-300:]
        )
