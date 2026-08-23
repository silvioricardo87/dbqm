"""Guarda do transbordo vertical (§4 da gramatica de layout).

`test_inventario_layout.py` vigia QUEM desenha caixa; este vigia o que a
caixa faz com a altura. Sao defeitos de uma familia so — conteudo empurrado
abaixo da dobra — e nenhum deles e visivel lendo CSS:

  - `Panel { height: auto }` nao media o conteudo. `#panel-body` nasce em
    `1fr`, e um `1fr` dentro de um pai automatico estica ate a altura do
    CONTAINER. Tres paineis de tres linhas viravam tres paineis de 24, o
    segundo nascia em y=24 e o terceiro em y=47 — o CSS parecia certo.
  - `#er-select-phase` media 24 de altura numa tela de 24 comecando em y=1:
    a borda de baixo nao era desenhada em ALTURA NENHUMA, e o indicador de
    progresso caia em y=26 enquanto um `list_objects` remoto rodava. Quem
    clicava em "Procedures" nao via sinal nenhum de que algo acontecia.

Por isso todas as afirmacoes aqui sao sobre o que a tela PINTA (via
`rendered_lines`/`rendered_text`), e nao sobre atributo de estilo:
uma regra CSS pode ler certo e nao fazer nada, e uma regiao pode ter altura
e nao ser desenhada.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from dbqm.ui.widgets.panel import Panel
from tests.ui._helpers import ThemedTestApp, rendered_lines, crop, rendered_text


# ---------------------------------------------------------------------------
# A raiz: `height: auto` num Panel
# ---------------------------------------------------------------------------


class _ThreePanels(ThemedTestApp):
    CSS = """
    #raiz { height: 1fr; overflow-y: auto; }
    #raiz Panel { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="raiz"):
            for i in range(3):
                with Panel(f"SECAO {i}", id=f"p{i}"):
                    yield Static("linha 1")
                    yield Static("linha 2")
                    yield Static("linha 3")


@pytest.mark.asyncio
async def test_auto_height_panel_measures_the_content():
    """`height: auto` num Panel tem de valer o conteudo, nao o container.

    Com o defeito presente os tres paineis mediam 24 (a tela inteira) e so
    o primeiro aparecia. A altura esperada e 9: 3 linhas de conteudo + 2 de
    padding do corpo + 1 de titulo + 1 da regua do titulo + 2 de borda.
    """
    app = _ThreePanels()
    async with app.run_test(size=(60, 24)) as pilot:
        await pilot.pause()
        alturas = [app.query_one(f"#p{i}").region.height for i in range(3)]
        assert alturas == [9, 9, 9], (
            "painel de altura automatica esticou ate o container: %r" % alturas
        )
        pintado = rendered_text(app)
        for i in range(3):
            assert f"SECAO {i}" in pintado, (
                "a secao %d nasceu abaixo da dobra num terminal de 24 linhas" % i
            )


class _PanelWithCap(ThemedTestApp):
    CSS = """
    #teto, #curto { height: auto; max-height: 8; }
    """

    def compose(self) -> ComposeResult:
        with Panel("DIAGNOSTICO", id="teto"):
            for i in range(1, 9):
                yield Static(f"linha {i}")
        with Panel("RESUMO", id="curto"):
            yield Static("uma linha so")


@pytest.mark.asyncio
async def test_capped_panel_scrolls_the_excess_instead_of_clipping():
    """`height: auto` + `max-height` nao pode deixar conteudo fora de alcance.

    Um corpo em `auto` nao ve o teto do pai. Sem descontar o cromo da
    moldura (`Panel.CHROME`), o corpo nasce mais alto que a caixa: as
    ultimas linhas ficam recortadas pela borda E fora do alcance da
    rolagem, que so anda ate o fim do CORPO.
    """
    app = _PanelWithCap()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        painel = app.query_one("#teto", Panel)
        corpo = painel.body
        assert painel.region.height == 8
        assert painel.region.contains_region(corpo.region), (
            "o corpo (%r) transborda a moldura (%r): o que sobra e recortado, "
            "nao rolado" % (corpo.region, painel.region)
        )
        assert corpo.max_scroll_y > 0, "o excesso nao rola"

        corpo.scroll_end(animate=False)
        await pilot.pause()
        assert "linha 8" in rendered_text(app), (
            "a ultima linha nao e alcancavel nem rolando ate o fim"
        )

        # `max-height` e TETO, nao altura: com uma linha de conteudo o
        # painel encolhe para 7 (1 + 2 de padding + 2 de titulo + 2 de
        # borda). Preso em `1fr`, o corpo esticaria e ele mediria 8 sempre.
        assert app.query_one("#curto", Panel).region.height == 7


# ---------------------------------------------------------------------------
# C1 — o indicador de progresso de `exec_routine`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("tamanho", [(100, 24), (80, 24), (100, 40)])
async def test_exec_routine_indicator_visible_during_the_search(tmp_config_dir, tamanho):
    """O feedback de "listando..." tem de ser DESENHADO, em qualquer altura.

    `_load_objects` acende o `ProgressIndicator` com `#er-select-phase`
    ainda visivel (o painel so some quando os objetos chegam). Enquanto o
    painel media a tela inteira comecando em y=1, o indicador nascia uma
    linha depois do fim da tela e o usuario ficava sem sinal nenhum durante
    uma chamada remota ao Oracle. A tela nao tem `overflow-y`: nao havia
    nem como rolar ate ele.
    """
    from dbqm.ui.screens.exec_routine import ExecRoutineScreen
    from dbqm.ui.widgets.progress import ProgressIndicator

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield ExecRoutineScreen()

    app = _App()
    async with app.run_test(size=tamanho) as pilot:
        await pilot.pause()
        painel = app.query_one("#er-select-phase", Panel)
        assert painel.display, "a fase 1 tem de estar visivel neste ponto"

        # A borda de baixo do painel: a prova de que ele cabe na tela.
        moldura = crop(app, painel)
        assert moldura[-1].startswith("╰") and moldura[-1].endswith("╯"), (
            "a borda inferior de #er-select-phase nao e desenhada em %r: %r"
            % (tamanho, moldura[-1])
        )

        app.query_one(ProgressIndicator).start("Listando procedures...")
        await pilot.pause()
        assert "Listando procedures..." in rendered_text(app), (
            "sem sinal de progresso em %r enquanto a busca remota roda" % (tamanho,)
        )


# ---------------------------------------------------------------------------
# M1 — as tres secoes de `oracle_clients`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_oracle_clients_sections_do_not_each_eat_the_screen(monkeypatch):
    """Com um client instalado, nenhuma secao pode ocupar a tela inteira.

    Este e o estado em que o defeito aparece — com a lista vazia o
    `EmptyState` esconde a tabela e as contas mudam. As tres secoes
    somadas passam de 24 linhas e a tela ROLA (a versao sem moldura media
    59 linhas e nao rolava: `Vertical` nasce com `overflow: hidden`). O que
    nao pode voltar e cada painel medir a viewport inteira e empurrar o
    seguinte para y=23 e y=46.
    """
    from dbqm.core import oracle_client_installer as oci
    import dbqm.ui.screens.oracle_clients as tela_mod

    monkeypatch.setattr(
        tela_mod.oci,
        "list_installed_clients",
        lambda *a, **k: [
            oci.InstalledClient(path=Path("instantclient_23_9"), version="23.9.0.0.0")
        ],
    )

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield tela_mod.OracleClientsScreen()

    app = _App()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        tela = app.query_one(tela_mod.OracleClientsScreen)
        paineis = {p.id: p for p in tela.query(Panel)}
        assert set(paineis) == {
            "oc-platform-panel",
            "oc-installed-panel",
            "oc-available-panel",
        }
        for pid, painel in paineis.items():
            assert painel.outer_size.height < 24, (
                "%s ocupa a tela inteira (%d linhas) e empurra o resto abaixo "
                "da dobra" % (pid, painel.outer_size.height)
            )
        # O transbordo que sobra e VISIVEL: rola.
        assert tela.max_scroll_y > 0
        assert tela.virtual_size.height < 48, (
            "as tres secoes somam %d linhas: duas viewports inteiras"
            % tela.virtual_size.height
        )

        # E alcancavel pelo teclado, que e como se chega la.
        botao = app.query_one("#oc-install-btn")
        botao.focus()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert "Instalar selecionado" in rendered_text(app)


# ---------------------------------------------------------------------------
# m1 — os formularios de `config_port`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "modo, rola",
    [
        (None, False),      # escolha de modo: 22 linhas, cabe
        ("import", False),  # importacao: 22 linhas, cabe
        ("export", True),   # exportacao: 29 linhas, passa da dobra
    ],
)
async def test_config_port_only_the_export_passes_the_fold(tmp_config_dir, modo, rola):
    """Quem transborda e a EXPORTACAO, nao a importacao.

    O comentario do `overflow-y` desta tela dizia o contrario. A diferenca
    sao as tres checkboxes e o segundo par rotulo+senha do formulario de
    exportacao.
    """
    from dbqm.ui.screens.config_port import ConfigPortScreen

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield ConfigPortScreen(initial_mode=modo)

    app = _App()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        tela = app.query_one(ConfigPortScreen)
        assert (tela.max_scroll_y > 0) is rola, (
            "modo %r: virtual_size=%r numa tela de 24 linhas"
            % (modo, tela.virtual_size)
        )

        if rola:
            # O botao que fecha o fluxo tem de ser alcancavel.
            app.query_one("#cp-do-export").focus()
            await pilot.pause()
            await pilot.wait_for_scheduled_animations()
            await pilot.pause()
            assert "Exportar" in rendered_text(app)


# ---------------------------------------------------------------------------
# m2 — o teto do painel de erros de compilacao
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_package_editor_compilation_errors_fit_and_scroll(tmp_config_dir):
    """`max-height: 8` emoldurado nao pode valer duas linhas de texto.

    Emoldurar comeu 4 linhas de cromo; com o padding vertical do corpo
    seriam 6, e `max-height: 8` deixaria so o cabecalho e o primeiro erro.
    O corpo deste painel vai sem padding vertical, o que devolve 4 linhas
    de texto, e o resto rola.
    """
    from dbqm.ui.screens.package_editor import PackageEditorScreen

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield PackageEditorScreen()

    app = _App()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        if len(app.screen_stack) > 1:  # o modal de escolha de package
            app.pop_screen()
            await pilot.pause()

        tela = app.query_one(PackageEditorScreen)
        tela.query_one("#pe-empty").display = False
        tela.query_one("#pe-editor-panel").display = True
        tela._on_compile_result(
            "body",
            False,
            "",
            [
                {"line": 10 + i, "col": 3, "message": f"PLS-0000{i}: erro {i}"}
                for i in range(1, 8)
            ],
        )
        await pilot.pause()

        painel = app.query_one("#pe-error-panel", Panel)
        corpo = painel.body
        assert painel.region.contains_region(corpo.region), (
            "o corpo transborda a moldura: as ultimas linhas ficam recortadas"
        )

        pintado = rendered_text(app)
        assert "erro(s) de compilacao" in pintado
        assert "erro 3" in pintado, "so o cabecalho e um erro cabem no painel"

        assert corpo.max_scroll_y > 0
        corpo.scroll_end(animate=False)
        await pilot.pause()
        assert "erro 7" in rendered_text(app), (
            "o ultimo erro nao e alcancavel nem rolando ate o fim"
        )

        # E o teto e TETO, nao altura fixa: uma compilacao bem-sucedida tem
        # uma linha e o painel tem de encolher, devolvendo as linhas ao
        # editor. Com o corpo preso em `1fr` ele ficaria com 8 sempre.
        tela._on_compile_result("body", True, "", [])
        await pilot.pause()
        assert painel.region.height < 8, (
            "o painel de erro nao encolhe: `height: auto` nao esta valendo"
        )


# ---------------------------------------------------------------------------
# A moldura nao pode virar vocabulario de controle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adhoc_controls_do_not_wear_the_frame(tmp_config_dir):
    """Controle nao desenha a caixa `round` de Panel — nem parado nem escolhido.

    O `Checkbox` de saida DBMS desenhava `border: round $primary`, byte a
    byte a mesma regra de `Panel:focus-within`: parado, com cara de painel
    focado. E o Select de conexao ganhava `round $ds-identity` ao escolher —
    o que ainda comia duas colunas e quebrava o nome da conexao em duas
    linhas. O sinal continua existindo; agora ele RECOLORE a afordancia que
    o proprio Select ja desenha.
    """
    from textual.widgets import Select
    from dbqm.ui.screens.adhoc import AdhocScreen

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield AdhocScreen()

    app = _App()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        for seletor in ("#adhoc-dbms-toggle", "#adhoc-conn-select"):
            topo = crop(app, app.query_one(seletor))[0]
            assert "╭" not in topo, (
                "%s desenha a moldura de secao: %r" % (seletor, topo)
            )

        seletor_conexao = app.query_one("#adhoc-conn-select", Select)
        canto = seletor_conexao.region.offset
        antes = app.screen.get_style_at(*canto).color
        largura_antes = len(crop(app, seletor_conexao))

        seletor_conexao.add_class("--conn-selected")
        await pilot.pause()
        depois = app.screen.get_style_at(*canto).color

        assert antes != depois, "escolher a conexao nao muda nada na tela"
        assert "╭" not in crop(app, seletor_conexao)[0]
        assert len(crop(app, seletor_conexao)) == largura_antes, (
            "o sinal de conexao escolhida mudou a geometria do controle"
        )
