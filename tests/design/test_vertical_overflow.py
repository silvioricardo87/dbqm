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
        heights = [app.query_one(f"#p{i}").region.height for i in range(3)]
        assert heights == [9, 9, 9], (
            "painel de altura automatica esticou ate o container: %r" % heights
        )
        painted = rendered_text(app)
        for i in range(3):
            assert f"SECAO {i}" in painted, (
                'section %d was born below the fold on a 24-line terminal' % i
            )


class _PanelWithCap(ThemedTestApp):
    CSS = """
    #ceiling, #short { height: auto; max-height: 8; }
    """

    def compose(self) -> ComposeResult:
        with Panel("DIAGNOSTICO", id="ceiling"):
            for i in range(1, 9):
                yield Static(f"linha {i}")
        with Panel("RESUMO", id="short"):
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
        panel = app.query_one("#ceiling", Panel)
        body = panel.body
        assert panel.region.height == 8
        assert panel.region.contains_region(body.region), (
            'the body (%r) overflows the frame (%r): what is left over is clipped, not scrolled' % (body.region, panel.region)
        )
        assert body.max_scroll_y > 0, 'the excess does not scroll'

        body.scroll_end(animate=False)
        await pilot.pause()
        assert "linha 8" in rendered_text(app), (
            'the last line cannot be reached even by scrolling to the end'
        )

        # `max-height` is a CAP, not a height: with one line of content the
        # panel shrinks to 7 (1 + 2 of padding + 2 of title + 2 of border).
        # Stuck at `1fr`, the body would stretch and it would always measure
        # 8.
        assert app.query_one("#short", Panel).region.height == 7


# ---------------------------------------------------------------------------
# C1 — the progress indicator of `exec_routine`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(100, 24), (80, 24), (100, 40)])
async def test_exec_routine_indicator_visible_during_the_search(tmp_config_dir, size):
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
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        panel = app.query_one("#er-select-phase", Panel)
        assert panel.display, 'phase 1 has to be visible at this point'

        # The panel's bottom border: the proof that it fits on the screen.
        frame = crop(app, panel)
        assert frame[-1].startswith("╰") and frame[-1].endswith("╯"), (
            'the bottom border of #er-select-phase is not drawn at %r: %r' % (size, frame[-1])
        )

        app.query_one(ProgressIndicator).start("Listando procedures...")
        await pilot.pause()
        assert "Listando procedures..." in rendered_text(app), (
            'no progress signal at %r while the remote search runs' % (size,)
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
    import dbqm.ui.screens.oracle_clients as screen_mod

    monkeypatch.setattr(
        screen_mod.oci,
        "list_installed_clients",
        lambda *a, **k: [
            oci.InstalledClient(path=Path("instantclient_23_9"), version="23.9.0.0.0")
        ],
    )

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield screen_mod.OracleClientsScreen()

    app = _App()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        screen = app.query_one(screen_mod.OracleClientsScreen)
        panels = {p.id: p for p in screen.query(Panel)}
        assert set(panels) == {
            "oc-platform-panel",
            "oc-installed-panel",
            "oc-available-panel",
        }
        for pid, panel in panels.items():
            assert panel.outer_size.height < 24, (
                '%s takes the whole screen (%d lines) and pushes the rest below the fold' % (pid, panel.outer_size.height)
            )
        # The overflow that is left is VISIBLE: it scrolls.
        assert screen.max_scroll_y > 0
        assert screen.virtual_size.height < 48, (
            "as tres secoes somam %d linhas: duas viewports inteiras"
            % screen.virtual_size.height
        )

        # And it is reachable by keyboard, which is how one gets there.
        button = app.query_one("#oc-install-btn")
        button.focus()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        assert "Install the selected one" in rendered_text(app)


# ---------------------------------------------------------------------------
# m1 — the forms of `config_port`
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode, scrolls",
    [
        (None, False),      # mode choice: 22 lines, fits
        ("import", False),  # import: 22 lines, fits
        ("export", True),   # export: 29 lines, goes past the fold
    ],
)
async def test_config_port_only_the_export_passes_the_fold(tmp_config_dir, mode, scrolls):
    """The one that overflows is the EXPORT, not the import.

    The `overflow-y` comment on this screen said the opposite. The
    difference is the three checkboxes and the second label+password pair of
    the export form.
    """
    from dbqm.ui.screens.config_port import ConfigPortScreen

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield ConfigPortScreen(initial_mode=mode)

    app = _App()
    async with app.run_test(size=(80, 24)) as pilot:
        from tests.ui._helpers import wait_until

        await pilot.pause()
        screen = app.query_one(ConfigPortScreen)
        # `max_scroll_y` is 0 until layout has run once, whichever mode is
        # mounted -- reading it after a single pause was a bet on the clock
        # that 3.10 lost. Wait for the layout, then judge the fold.
        await wait_until(pilot, lambda: screen.virtual_size.height > 0,
                         what="the config-port screen laid out")
        assert (screen.max_scroll_y > 0) is scrolls, (
            'mode %r: virtual_size=%r on a 24-line screen' % (mode, screen.virtual_size)
        )

        if scrolls:
            # The button that closes the flow has to be reachable -- which
            # means the screen SCROLLS rather than truncates. Scroll to it
            # explicitly, without animation, and read the compositor's
            # strips rather than the screenshot: `focus()` relied on an
            # implicit animated scroll that never landed within 40 frames
            # on 3.10 (five runs in six), and `export_screenshot()` is the
            # reader the roadmap already records as lagging a frame behind.
            from tests.ui._helpers import rendered_lines

            app.query_one("#cp-do-export").scroll_visible(animate=False)
            await wait_until(
                pilot,
                lambda: any("Export" in line for line in rendered_lines(app)),
                what="the Export button scrolled into view",
            )


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

        screen = app.query_one(PackageEditorScreen)
        screen.query_one("#pe-empty").display = False
        screen.query_one("#pe-editor-panel").display = True
        screen._on_compile_result(
            "body",
            False,
            "",
            [
                {"line": 10 + i, "col": 3, "message": f"PLS-0000{i}: error {i}"}
                for i in range(1, 8)
            ],
        )
        # Three reads below used to follow a single `pause()` each. On 3.10
        # the panel was not always laid out by then; each one now waits for
        # the fact it is about to assert.
        from tests.ui._helpers import wait_until

        await wait_until(pilot, lambda: "error 3" in rendered_text(app),
                         what="the error panel painted its first rows")

        panel = app.query_one("#pe-error-panel", Panel)
        body = panel.body
        assert panel.region.contains_region(body.region), (
            "the body overflows the frame: the last rows are clipped"
        )

        painted = rendered_text(app)
        assert "compilation error(s)" in painted
        assert "error 3" in painted, "only the header and one error fit in the panel"

        assert body.max_scroll_y > 0
        body.scroll_end(animate=False)
        await wait_until(pilot, lambda: "error 7" in rendered_text(app),
                         what="the last error scrolled into view")

        # And the cap is a CAP, not a fixed height: a successful compilation
        # has one line and the panel has to shrink, giving the lines back to
        # the editor. With the body stuck at `1fr` it would always be 8.
        screen._on_compile_result("body", True, "", [])
        await wait_until(pilot, lambda: panel.region.height < 8,
                         what="the error panel shrank after a clean compile")
        assert panel.region.height < 8, (
            'the error panel does not shrink: `height: auto` is not in force'
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
        # Two pauses, not one: on a cold start the first frame is not always
        # painted after a single pause, and the crop read an empty line.
        await pilot.pause()
        await pilot.pause()
        for selector in ("#adhoc-dbms-toggle", "#adhoc-conn-select"):
            top = crop(app, app.query_one(selector))[0]
            assert "╭" not in top, (
                "%s desenha a moldura de secao: %r" % (selector, top)
            )

        connection_selector = app.query_one("#adhoc-conn-select", Select)
        corner = connection_selector.region.offset
        before = app.screen.get_style_at(*corner).color
        width_before = len(crop(app, connection_selector))

        connection_selector.add_class("--conn-selected")
        await pilot.pause()
        await pilot.pause()
        after = app.screen.get_style_at(*corner).color

        assert before != after, 'choosing the connection changes nothing on screen'
        assert "╭" not in crop(app, connection_selector)[0]
        assert len(crop(app, connection_selector)) == width_before, (
            'the chosen-connection marker changed the control\'s geometry'
        )
