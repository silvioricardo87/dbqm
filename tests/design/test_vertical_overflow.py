"""Guard for vertical overflow (§4 of the layout grammar).

`test_layout_inventory.py` watches WHO draws a box; this one watches what
the box does with the height. They are defects of a single family — content
pushed below the fold — and none of them is visible by reading CSS:

  - `Panel { height: auto }` did not measure the content. `#panel-body` is
    born at `1fr`, and a `1fr` inside an automatic parent stretches to the
    height of the CONTAINER. Three panels of three lines each became three
    panels of 24, the second was born at y=24 and the third at y=47 — the
    CSS looked right.
  - `#er-select-phase` measured 24 in height on a 24-line screen starting at
    y=1: the bottom border was drawn at NO HEIGHT AT ALL, and the progress
    indicator landed at y=26 while a remote `list_objects` was running.
    Whoever clicked "Procedures" saw no sign at all that anything was
    happening.

That is why every assertion here is about what the screen PAINTS (via
`rendered_lines`/`rendered_text`), and not about a style attribute: a CSS
rule can read correctly and do nothing, and a region can have height and not
be drawn.
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
# The root cause: `height: auto` on a Panel
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
    """`height: auto` on a Panel has to be worth the content, not the
    container.

    With the defect present the three panels measured 24 (the whole screen)
    and only the first one showed up. The expected height is 9: 3 lines of
    content + 2 of body padding + 1 of title + 1 of the title rule + 2 of
    border.
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
    """`height: auto` + `max-height` must not leave content out of reach.

    A body in `auto` does not see the parent's cap. Without subtracting the
    frame chrome (`Panel.CHROME`), the body is born taller than the box: the
    last lines end up clipped by the border AND out of reach of the
    scrolling, which only goes as far as the end of the BODY.
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

        # `max-height` is a CAP, not a height: with one line of content the
        # panel shrinks to 7 (1 + 2 of padding + 2 of title + 2 of border).
        # Stuck at `1fr`, the body would stretch and it would always measure
        # 8.
        assert app.query_one("#curto", Panel).region.height == 7


# ---------------------------------------------------------------------------
# C1 — the progress indicator of `exec_routine`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("tamanho", [(100, 24), (80, 24), (100, 40)])
async def test_exec_routine_indicator_visible_during_the_search(tmp_config_dir, tamanho):
    """The "listando..." feedback has to be DRAWN, at any height.

    `_load_objects` turns the `ProgressIndicator` on with `#er-select-phase`
    still visible (the panel only goes away when the objects arrive). While
    the panel measured the whole screen starting at y=1, the indicator was
    born one line past the end of the screen and the user was left with no
    sign at all during a remote call to Oracle. The screen has no
    `overflow-y`: there was not even a way to scroll down to it.
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

        # The panel's bottom border: the proof that it fits on the screen.
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
# M1 — the three sections of `oracle_clients`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_oracle_clients_sections_do_not_each_eat_the_screen(monkeypatch):
    """With one client installed, no section may take up the whole screen.

    This is the state in which the defect shows up — with an empty list the
    `EmptyState` hides the table and the arithmetic changes. The three
    sections added together go past 24 lines and the screen SCROLLS (the
    frameless version measured 59 lines and did not scroll: `Vertical` is
    born with `overflow: hidden`). What must not come back is each panel
    measuring the whole viewport and pushing the next one to y=23 and y=46.
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
        # The overflow that is left is VISIBLE: it scrolls.
        assert tela.max_scroll_y > 0
        assert tela.virtual_size.height < 48, (
            "as tres secoes somam %d linhas: duas viewports inteiras"
            % tela.virtual_size.height
        )

        # And it is reachable by keyboard, which is how one gets there.
        botao = app.query_one("#oc-install-btn")
        botao.focus()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert "Instalar selecionado" in rendered_text(app)


# ---------------------------------------------------------------------------
# m1 — the forms of `config_port`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "modo, rola",
    [
        (None, False),      # mode choice: 22 lines, fits
        ("import", False),  # import: 22 lines, fits
        ("export", True),   # export: 29 lines, goes past the fold
    ],
)
async def test_config_port_only_the_export_passes_the_fold(tmp_config_dir, modo, rola):
    """The one that overflows is the EXPORT, not the import.

    The `overflow-y` comment on this screen said the opposite. The
    difference is the three checkboxes and the second label+password pair of
    the export form.
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
            # The button that closes the flow has to be reachable.
            app.query_one("#cp-do-export").focus()
            await pilot.pause()
            await pilot.wait_for_scheduled_animations()
            await pilot.pause()
            assert "Exportar" in rendered_text(app)


# ---------------------------------------------------------------------------
# m2 — the cap of the compilation errors panel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_package_editor_compilation_errors_fit_and_scroll(tmp_config_dir):
    """A framed `max-height: 8` must not be worth two lines of text.

    Framing it consumed 4 lines of chrome; with the body's vertical padding it
    would be 6, and `max-height: 8` would leave only the header and the
    first error. The body of this panel goes without vertical padding, which
    gives back 4 lines of text, and the rest scrolls.
    """
    from dbqm.ui.screens.package_editor import PackageEditorScreen

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield PackageEditorScreen()

    app = _App()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        if len(app.screen_stack) > 1:  # the package choice modal
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

        # And the cap is a CAP, not a fixed height: a successful compilation
        # has one line and the panel has to shrink, giving the lines back to
        # the editor. With the body stuck at `1fr` it would always be 8.
        tela._on_compile_result("body", True, "", [])
        await pilot.pause()
        assert painel.region.height < 8, (
            "o painel de erro nao encolhe: `height: auto` nao esta valendo"
        )


# ---------------------------------------------------------------------------
# The frame must not become control vocabulary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adhoc_controls_do_not_wear_the_frame(tmp_config_dir):
    """A control does not draw Panel's `round` box — neither at rest nor when
    chosen.

    The DBMS output `Checkbox` drew `border: round $primary`, byte for byte
    the same rule as `Panel:focus-within`: at rest, looking like a focused
    panel. And the connection Select gained `round $ds-identity` when chosen
    — which on top of that consumed two columns and broke the connection name
    into two lines. The signal still exists; now it RECOLOURS the affordance
    the Select already draws itself.
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
