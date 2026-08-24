"""Tests for UI widgets."""
import pytest
from textual.app import ComposeResult

from tests.ui._helpers import ThemedTestApp, rendered_names, crop


# ---------------------------------------------------------------------------
# StatusBar tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.status_bar import StatusBar


class StatusBarTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield StatusBar()


@pytest.mark.asyncio
async def test_status_bar_shows_connection():
    app = StatusBarTestApp()
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)
        sb.set_connection("ORACLE-PRD")
        await pilot.pause()
        rendered = sb.render_text()
        assert "ORACLE-PRD" in rendered


@pytest.mark.asyncio
async def test_status_bar_no_connection():
    app = StatusBarTestApp()
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)
        sb.set_connection(None)
        await pilot.pause()
        rendered = sb.render_text()
        # Should show indicator but no connection name
        assert "ORACLE-PRD" not in rendered


@pytest.mark.asyncio
async def test_status_bar_shows_counts():
    app = StatusBarTestApp()
    async with app.run_test() as pilot:
        sb = app.query_one(StatusBar)
        sb.update_counts(queries=5, connections=3, groups=2)
        await pilot.pause()
        rendered = sb.render_text()
        assert "5" in rendered
        assert "3" in rendered
        assert "2" in rendered


def test_status_bar_inverted_primary_background():
    assert "background: $primary" in StatusBar.DEFAULT_CSS


@pytest.mark.asyncio
async def test_status_bar_dot_contrasts_with_the_bar_background():
    """The connection dot has to contrast with the background of the bar
    itself.

    The original bug was never "the dot uses the wrong token" — it was "the
    dot does not contrast with what is behind it". That is why this test
    names no token: neither the dot's one (it already comes resolved from
    the rendered content), nor the bar background's one. The background is
    read from `barra.styles.background` — the colour Textual actually
    resolved and is going to paint behind the mounted widget, whatever the
    CSS rule that produced it. If `StatusBar.DEFAULT_CSS` switches from
    `background: $primary` to another token, this test keeps measuring the
    real pair; naming `$primary` here would be the same trap the previous
    assertion had against `$background` — tied to a spelling, not to the
    relation.
    """
    from textual.style import Style

    from tests.design._contraste import ratio

    app = StatusBarTestApp()
    async with app.run_test():
        barra = app.query_one(StatusBar)
        barra.set_connection("MGORA7ORA9")
        await app.workers.wait_for_complete()
        content = barra.render()
        pecas = list(content.render(Style.null(), end="", parse_style=Style.parse))
        cor_bolinha = next(
            estilo.foreground for texto, estilo in pecas if "●" in texto
        )
        cor_fundo_barra = barra.styles.background

        contraste = ratio(cor_bolinha.hex, cor_fundo_barra.hex)
        assert contraste >= 3.0, (
            f"bolinha ({cor_bolinha.hex}) sobre o fundo real da barra "
            f"({cor_fundo_barra.hex}) = {contraste:.2f}:1, abaixo do piso de interface"
        )


# ---------------------------------------------------------------------------
# Veredito / StatusOperacao tests
# ---------------------------------------------------------------------------

def test_verdict_communicates_state_beyond_color():
    """Accessibility floor: colour alone does not communicate state."""
    from dbqm.ui.widgets.verdict import mark_verdict

    glifos = {mark_verdict(v).split("]")[1].split("[")[0] for v in
              ("match", "match-normalized", "diff", "absent")}
    assert len(glifos) == 4, f"glifos repetidos: {glifos}"


def test_match_verdict_uses_the_token_of_its_own_axis():
    from dbqm.ui.widgets.verdict import mark_verdict

    assert "$ds-verdict-match" in mark_verdict("match")


def test_verdict_rejects_an_unknown_status():
    from dbqm.ui.widgets.verdict import mark_verdict

    with pytest.raises(ValueError, match="status"):
        mark_verdict("talvez")


def test_successful_operation_gets_no_ink():
    """Success is the absence of alarm, but not of weight: `ok` may not
    carry ANY colour token (not just `$ds-op-failure` — any `$token`,
    including a verdict token pasted in by mistake), and keeps `[bold]`. An
    earlier version of this test only checked for the absence of
    `$ds-op-failure`, which would pass even if success were painted with a
    verdict colour."""
    from dbqm.ui.widgets.verdict import mark_operation

    ok = mark_operation("ok")
    assert "$" not in ok, f"operacao bem sucedida nao deve carregar token de cor: {ok!r}"
    assert "[bold]" in ok, f"operacao bem sucedida perde peso sem cor: {ok!r}"
    assert "$ds-op-failure" in mark_operation("failure")


def test_successful_operation_keeps_weight_in_manual_call_sites():
    """The four sites that assemble success markup by hand — outside
    `mark_operation`, because the message also carries the elapsed time —
    have to follow the same rule: no colour token, with `[bold]` preserved.
    Nothing tested this until now; a `[bold]` deleted at one of those sites
    would pass the whole suite in silence."""
    from pathlib import Path

    raiz_screens = Path(__file__).resolve().parents[2] / "dbqm" / "ui" / "screens"
    sites = {
        "adhoc.py": [
            'return f"[bold]Bloco PL/SQL executado[/] ({result.elapsed:.2f}s)"',
            'f"[bold]DDL executado com sucesso[/] ({result.elapsed:.2f}s)"',
        ],
        "exec_routine.py": [
            'lines = [f"[bold]Executado com sucesso[/] ({result.elapsed:.2f}s)"]',
        ],
        "package_editor.py": [
            'f"[bold]  {target.capitalize()} compilado com sucesso![/]"',
        ],
    }
    for nome_arquivo, trechos in sites.items():
        texto = (raiz_screens / nome_arquivo).read_text(encoding="utf-8")
        for trecho in trechos:
            assert trecho in texto, (
                f"{nome_arquivo}: markup de sucesso mudou ou perdeu o [bold]: {trecho!r}"
            )


def test_operation_rejects_an_unknown_state():
    from dbqm.ui.widgets.verdict import mark_operation

    with pytest.raises(ValueError, match="estado"):
        mark_operation("talvez")


def test_mark_verdict_label_swaps_the_label_and_keeps_glyph_and_token():
    """`texto` lets the caller colour its own word without duplicating the
    component's default label next to it (a finding of the Task 11 review:
    `_render_summary` produced "= OK Iguais:" before this parameter
    existed).

    The glyph and the token still come only from `VERDICTS` — `texto` never
    exposes the token name for the caller to assemble `[$token]` on the
    outside; if it did, it would reopen exactly the hand-assembly hole that
    the rest of this module closes.
    """
    from dbqm.ui.widgets.verdict import mark_verdict

    padrao = mark_verdict("diff")
    customizado = mark_verdict("diff", label="DIVERGENTE")

    assert "DIVERGENTE" in customizado
    assert "DIFERE" not in customizado
    assert "$ds-verdict-diff" in customizado
    # same glyph as the default, without duplicating its "DIFERE" label
    assert customizado.split("]")[1].split(" ", 1)[0] == padrao.split("]")[1].split(" ", 1)[0]


def test_mark_verdict_escapes_the_label_so_markup_cannot_leak():
    """`texto` exists for a label, not to inject markup. No caller today
    passes text coming from data (they are all fixed literals), but nothing
    stops a future caller from passing something derived from data — and a
    `[/]` or a `$token` inside that value must not close the component's
    tag early nor open a different style in the middle of the marker.
    """
    from textual.content import Content
    from dbqm.ui.widgets.verdict import mark_verdict

    perigoso = "fim[/][$ds-op-failure]injetado"
    saida = mark_verdict("match", label=perigoso)

    # only the component's own legitimate closing tag is left unescaped
    assert saida.count("[/]") == 1
    assert saida.endswith("[/]")

    # the whole markup resolves as ONE SINGLE span, with the state's token —
    # if the dangerous text had escaped the escaping, a second span would
    # show up (the injected "[$ds-op-failure]" opening a style of its own)
    # or the "injetado" text would end up outside any span.
    conteudo = Content.from_markup(saida)
    assert len(conteudo.spans) == 1
    assert conteudo.spans[0].style == "$ds-verdict-match"
    assert "fim" in conteudo.plain
    assert "injetado" in conteudo.plain


def test_no_hand_rolled_verdict_markup_outside_the_component():
    """Closes the door that was left open after the first round of Task 11:
    nothing outside `verdict.py` may write `$veredito-*`/`$ds-op-failure`
    straight into markup without this test calling it out — not today, and
    not a fifth case tomorrow.

    The distinction that decides what goes into
    `PROSA_DE_ERRO_FORA_DO_ESCOPO` below: a MARKER names a state within a
    closed vocabulary (`igual`/`difere`/`ausente`/`ok`/`falha`/...) and for
    that reason NEEDS a glyph — colour alone is never enough, because the
    vocabulary is finite and repeated all over the interface. PROSE already
    names the failure in words of its own, written once for that specific
    error ("DDL executado com erros de compilacao", "Erro na execucao") —
    the colour only reinforces what the sentence already says, so painting
    that prose with `$ds-op-failure` is not the same hole this test closes.

    The verdict axis (`$veredito-*`) is only ever a marker, never prose,
    anywhere in the interface today — which is why it stays a genuinely
    closed door, with no exception: any occurrence outside `verdict.py`
    fails.

    The operation axis (`$ds-op-failure`) has both uses: `mark_operation`
    for the marker (converted) and, on five screens Task 11 never touched
    (DDL, routine, Oracle client, settings), colouring of error prose that
    already names the failure in words — outside the scope of
    `mark_operation` by nature, not out of laziness; converting those
    screens would prepend "x FALHA" in front of sentences such as "Erro na
    execucao", the same duplication the `texto` parameter has just removed
    from the comparison summary. `PROSA_DE_ERRO_FORA_DO_ESCOPO` locks the
    exact number of occurrences per file so that the door closes for any
    NEW occurrence (in those files or in any other) without reopening the
    conversation about these five. If one of them is rewritten to cite a
    state from the closed vocabulary instead of prose, the number here
    changes with it — the test calls it out in both directions.

    `DEFAULT_CSS` blocks are ignored: they are static style declaration for
    the widget (the same use `theme.py` makes of the tokens), not dynamic
    markup — they do not have the "state communicated by colour alone"
    problem this test watches for.

    Deliberate limit of this test, accepted at review (do not widen it
    without reopening the conversation): it is a text scan over `dbqm/ui/`,
    so it does not catch a token reassembled by interpolation or split
    across concatenated literals, it does not catch a token constant
    defined outside `dbqm/ui` and merely referenced here, and it does not
    catch markup assembled in `dbqm/core`/`dbqm/cli.py` and only rendered
    by a UI widget.
    """
    import re
    from pathlib import Path

    raiz_ui = Path(__file__).resolve().parents[2] / "dbqm" / "ui"
    padrao_token = re.compile(r"\$veredito-[a-z]+|\$ds-op-failure")
    padrao_css = re.compile(r'DEFAULT_CSS\s*=\s*""".*?"""', re.DOTALL)

    # Error prose that already names the failure in words of its own —
    # outside the scope of mark_operation by nature (see the docstring).
    # Path relative to dbqm/ui -> exact number of occurrences of
    # `$ds-op-failure` today.
    PROSA_DE_ERRO_FORA_DO_ESCOPO: dict[str, int] = {
        "screens/adhoc.py": 2,  # header + DDL compilation error detail
        "screens/exec_routine.py": 2,  # header + execution error detail
        "screens/oracle_clients.py": 1,  # info/ok/err level of free messages
        "screens/package_editor.py": 2,  # count + compilation error message
        "screens/settings.py": 1,  # exception text embedded in a label
    }

    ofensores = []
    for arquivo in sorted(raiz_ui.rglob("*.py")):
        rel = str(arquivo.relative_to(raiz_ui)).replace("\\", "/")
        if rel == "widgets/verdict.py":
            continue
        texto_fonte = arquivo.read_text(encoding="utf-8")
        texto_sem_css = padrao_css.sub("", texto_fonte)
        n = len(padrao_token.findall(texto_sem_css))
        permitido = PROSA_DE_ERRO_FORA_DO_ESCOPO.get(rel, 0)
        if n != permitido:
            ofensores.append(f"{rel}: {n} ocorrencia(s), esperado {permitido}")

    assert not ofensores, (
        "markup de veredito/operacao montado a mao fora de verdict.py, "
        f"alem da prosa de erro documentada em PROSA_DE_ERRO_FORA_DO_ESCOPO: {ofensores}"
    )


# ---------------------------------------------------------------------------
# ActionBar tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.action_bar import ActionBar, ActionSelected, Action


class ActionBarTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield ActionBar()


@pytest.mark.asyncio
async def test_action_bar_renders_actions():
    app = ActionBarTestApp()
    async with app.run_test() as pilot:
        ab = app.query_one(ActionBar)
        ab.set_actions([
            Action(label="Vertical", key="V", action_id="vertical"),
            Action(label="Exportar", key="E", action_id="export"),
        ])
        await pilot.pause()
        assert ab.display is True
        assert len(ab._actions) == 2


@pytest.mark.asyncio
async def test_action_bar_empty():
    app = ActionBarTestApp()
    async with app.run_test() as pilot:
        ab = app.query_one(ActionBar)
        ab.set_actions([])
        await pilot.pause()
        assert ab.display is False


def test_action_bar_uses_primary_key_markup():
    bar = ActionBar()
    bar._actions = [Action("Executar", "r", "run")]
    bar._rebuild()
    rendered = str(bar._Static__content)
    assert "on white" not in rendered            # no more black-on-white chip
    assert "bold $primary" in rendered


# ---------------------------------------------------------------------------
# ResultTable tests
# ---------------------------------------------------------------------------
from dbqm.core.query_engine import QueryResult
from dbqm.ui.widgets.result_table import ResultTable


class ResultTableTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield ResultTable()


@pytest.mark.asyncio
async def test_result_table_loads_data():
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id", "name", "value"],
        rows=[[1, "Alice", 100], [2, "Bob", 200], [3, "Carol", 300]],
        row_count=3,
        elapsed=0.05,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_result_table_pagination():
    rows = [[i, f"name_{i}", i * 10] for i in range(250)]
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id", "name", "value"],
        rows=rows,
        row_count=250,
        elapsed=0.1,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.page_info == "Pagina 1/3 (250 registros)"
        table.next_page()
        assert "Pagina 2/3" in table.page_info
        table.prev_page()
        assert "Pagina 1/3" in table.page_info


@pytest.mark.asyncio
async def test_result_table_empty():
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id"],
        rows=[],
        row_count=0,
        elapsed=0.01,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_result_table_vertical_toggle():
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id", "name"],
        rows=[[1, "Alice"]],
        row_count=1,
        elapsed=0.01,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert not table.vertical_mode
        table.toggle_vertical()
        assert table.vertical_mode


@pytest.mark.asyncio
async def test_result_table_none_values():
    """None values should display as empty strings."""
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id", "name"],
        rows=[[1, None], [None, "Bob"]],
        row_count=2,
        elapsed=0.01,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_result_table_page_info_and_result_info():
    result = QueryResult(
        query_name="test",
        connection_name="ORACLE-PRD",
        columns=["id"],
        rows=[[i] for i in range(250)],
        row_count=250,
        elapsed=0.34,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        assert table.result_info == "250 registros | 0.34s | ORACLE-PRD"
        assert table.page_info == "Pagina 1/3 (250 registros)"


@pytest.mark.asyncio
async def test_result_table_pagination_boundary():
    """Cannot go before first or after last page."""
    rows = [[i] for i in range(250)]
    result = QueryResult(
        query_name="test",
        connection_name="conn",
        columns=["id"],
        rows=rows,
        row_count=250,
        elapsed=0.1,
    )
    app = ResultTableTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(ResultTable)
        table.load_result(result)
        table.prev_page()  # already at page 0
        assert "Pagina 1/3" in table.page_info
        table.next_page()
        table.next_page()
        table.next_page()  # should stop at page 3
        assert "Pagina 3/3" in table.page_info


def _result(columns, rows):
    return QueryResult(
        query_name="t", connection_name="c",
        columns=columns, rows=rows, row_count=len(rows), elapsed=0.01,
    )


@pytest.mark.asyncio
async def test_result_table_fixes_the_key_column_and_zebra_stripes():
    """The first column never goes out of sight when scrolling sideways.

    dbqm exists to compare: without knowing which record the row belongs
    to, the remaining columns mean nothing.
    """
    from textual.widgets import DataTable

    class App_(ThemedTestApp):
        def compose(self):
            yield ResultTable(id="rt")

    app = App_()
    async with app.run_test() as pilot:
        rt = app.query_one("#rt", ResultTable)
        rt.load_result(_result(
            ["NUM_APOLICE", "SITUACAO", "VLR_PREMIO"],
            [["8801194920", "ATIVA", "3.482,90"]],
        ))
        await pilot.pause()
        dt = rt.query_one(DataTable)
        assert dt.fixed_columns == 1
        assert dt.zebra_stripes is True


@pytest.mark.asyncio
async def test_result_table_does_not_fix_a_column_when_there_is_only_one():
    """Fixing the only column protects nothing and steals width.

    Asserts the TRANSITION (several columns -> a single one), not just the
    final value: Textual's default for fixed_columns is already 0, so a
    test that only loads one column would pass even if the line that zeroes
    fixed_columns were deleted. By loading a wide result first (fixes at 1)
    and then the single-column one in the SAME widget, a fixed_columns
    stuck at 1 from the previous load fails the test for the right reason.
    """
    from textual.widgets import DataTable

    class App_(ThemedTestApp):
        def compose(self):
            yield ResultTable(id="rt")

    app = App_()
    async with app.run_test() as pilot:
        rt = app.query_one("#rt", ResultTable)
        dt = app.query_one(DataTable)
        rt.load_result(_result(
            ["NUM_APOLICE", "SITUACAO", "VLR_PREMIO"],
            [["8801194920", "ATIVA", "3.482,90"]],
        ))
        await pilot.pause()
        assert dt.fixed_columns == 1

        rt.load_result(_result(["TOTAL"], [["42"]]))
        await pilot.pause()
        assert dt.fixed_columns == 0


@pytest.mark.asyncio
async def test_result_table_key_column_stays_rendered_while_scrolling():
    """The proof of rendering, not just of the reactive attribute.

    `fixed_columns == 1` can stay set and the column still stop painting on
    screen if a Textual upgrade or a CSS change breaks the rendering of the
    fixing. This test really scrolls (pilot.press) and reads the exported
    screenshot — the same text a user would see — instead of merely
    inspecting the attribute.
    """
    from textual.widgets import DataTable

    colunas = ["CHAVE_REGISTRO"] + [f"COLUNA_LARGA_NUMERO_{i:02d}" for i in range(1, 9)]
    linha = ["REG-0001"] + [f"valor-{i:02d}-xxxxxxxxxx" for i in range(1, 9)]

    class App_(ThemedTestApp):
        def compose(self):
            yield ResultTable(id="rt")

    app = App_()
    async with app.run_test(size=(40, 15)) as pilot:
        rt = app.query_one("#rt", ResultTable)
        rt.load_result(_result(colunas, [linha]))
        await pilot.pause()
        dt = rt.query_one(DataTable)

        # Before scrolling: the key is visible and the last wide column is
        # NOT — confirms the scenario really does require sideways
        # scrolling.
        antes = app.export_screenshot()
        assert "CHAVE_REGISTRO" in antes
        assert "COLUNA_LARGA_NUMERO_08" not in antes

        # Really scrolls, all the way to the end.
        for _ in range(40):
            await pilot.press("right")
        await pilot.pause()
        assert dt.scroll_x > 0  # the sideways scrolling really happened

        # After scrolling: the key column (header AND value) is still
        # painted on screen, and the column that was previously out of sight
        # has now shown up — proving that non-fixed columns scrolled
        # underneath it.
        depois = app.export_screenshot()
        assert "CHAVE_REGISTRO" in depois
        assert "REG-0001" in depois
        assert "COLUNA_LARGA_NUMERO_08" in depois


# ---------------------------------------------------------------------------
# ProgressIndicator tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.progress import ProgressIndicator


class ProgressTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield ProgressIndicator()


@pytest.mark.asyncio
async def test_progress_starts_hidden():
    app = ProgressTestApp()
    async with app.run_test() as pilot:
        progress = app.query_one(ProgressIndicator)
        assert not progress.display  # hidden by default


@pytest.mark.asyncio
async def test_progress_start_shows():
    app = ProgressTestApp()
    async with app.run_test() as pilot:
        progress = app.query_one(ProgressIndicator)
        progress.start("Loading...")
        assert progress.display


@pytest.mark.asyncio
async def test_progress_stop_hides():
    app = ProgressTestApp()
    async with app.run_test() as pilot:
        progress = app.query_one(ProgressIndicator)
        progress.start("Loading...")
        progress.stop()
        assert not progress.display


@pytest.mark.asyncio
async def test_progress_update_message():
    app = ProgressTestApp()
    async with app.run_test() as pilot:
        progress = app.query_one(ProgressIndicator)
        progress.start("Step 1...")
        progress.update_message("Step 2...")
        from textual.widgets import Static
        msg = progress.query_one("#progress-message", Static)
        assert str(msg._Static__content) == "Step 2..."


# ---------------------------------------------------------------------------
# QueryListWidget tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.query_list import QueryListWidget, QuerySelected


class QueryListTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield QueryListWidget()


@pytest.mark.asyncio
async def test_query_list_loads_items():
    from textual.widgets import OptionList

    queries = [
        {"name": "q1", "connection": "conn1", "table": "t1", "description": "desc1", "is_favorite": False, "folder": ""},
        {"name": "q2", "connection": "conn2", "table": "t2", "description": "desc2", "is_favorite": True, "folder": ""},
    ]
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()
        option_list = ql.query_one("#ql-listview", OptionList)
        assert option_list.option_count == 2
        # Favorites should be first
        assert rendered_names(option_list) == ["q2", "q1"]


@pytest.mark.asyncio
async def test_query_list_empty():
    """An `Option` can't host a widget, so an empty/filtered-to-nothing
    list shows an EmptyState beside the OptionList (which hides), never a
    fake row inside it."""
    from textual.widgets import OptionList
    from dbqm.ui.widgets.empty_state import EmptyState

    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries([])
        await pilot.pause()
        option_list = ql.query_one("#ql-listview", OptionList)
        assert option_list.option_count == 0
        assert ql.query_one("#ql-filter-empty", EmptyState).display is True
        assert option_list.display is False


@pytest.mark.asyncio
async def test_query_list_filtered_empty_state_clears_search_and_notifies_host():
    """The EmptyState shown when a filter matches nothing must not be a
    dead end: it clears the widget's own inline search AND tells the host
    screen (which owns folder/connection filters up there) to clear its
    own."""
    from textual.widgets import Button, OptionList
    from dbqm.ui.widgets.empty_state import EmptyState
    from dbqm.ui.widgets.query_list import ClearFiltersRequested

    notified = []

    class _HostApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield QueryListWidget()

        def on_clear_filters_requested(self, message: ClearFiltersRequested) -> None:
            notified.append(True)

    queries = [
        {
            "name": "q1", "connection": "c1", "table": "", "description": "",
            "is_favorite": False, "folder": None,
        },
    ]

    app = _HostApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()

        ql._search_text = "no-such-query"
        ql._refresh_items()
        await pilot.pause()
        assert ql.query_one("#ql-filter-empty", EmptyState).display is True
        assert ql.query_one("#ql-listview", OptionList).display is False

        ql.query_one("#limpar-filtros-consultas", Button).press()
        await pilot.pause()

        assert ql._search_text == ""
        assert ql.query_one("#ql-filter-empty", EmptyState).display is False
        assert ql.query_one("#ql-listview", OptionList).display is True
        assert notified == [True]


@pytest.mark.asyncio
async def test_query_list_filter_folder():
    from textual.widgets import OptionList

    queries = [
        {"name": "q1", "connection": "c1", "table": "", "description": "", "is_favorite": False, "folder": "folderA"},
        {"name": "q2", "connection": "c2", "table": "", "description": "", "is_favorite": False, "folder": "folderB"},
        {"name": "q3", "connection": "c3", "table": "", "description": "", "is_favorite": False, "folder": "folderA"},
    ]
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        ql.filter_folder("folderA")
        await pilot.pause()
        option_list = ql.query_one("#ql-listview", OptionList)
        assert option_list.option_count == 2
        assert set(rendered_names(option_list)) == {"q1", "q3"}


@pytest.mark.asyncio
async def test_query_list_filter_folder_none_shows_all():
    from textual.widgets import OptionList

    queries = [
        {"name": "q1", "connection": "c1", "table": "", "description": "", "is_favorite": False, "folder": "folderA"},
        {"name": "q2", "connection": "c2", "table": "", "description": "", "is_favorite": False, "folder": "folderB"},
    ]
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        ql.filter_folder(None)
        await pilot.pause()
        option_list = ql.query_one("#ql-listview", OptionList)
        assert option_list.option_count == 2


@pytest.mark.asyncio
async def test_query_list_posts_query_selected():
    """Clicking a row posts QuerySelected with that row's name.

    The click is the point: the old list was tested with `pilot.click`, and
    the conversion to OptionList swapped that for focus + `enter`. They are
    different input paths (mouse and keyboard), and the swap left the mouse
    one uncovered; the keyboard one is covered in
    `test_query_list_selects_by_name_even_with_repeated_names`."""
    from textual.widgets import OptionList

    queries = [
        {"name": "my_query", "connection": "c1", "table": "t1", "description": "d", "is_favorite": False, "folder": ""},
    ]
    messages = []

    class CapturingApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield QueryListWidget()

        def on_query_selected(self, event: QuerySelected) -> None:
            messages.append(event.query_name)

    app = CapturingApp()
    async with app.run_test(size=(80, 24)) as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()
        option_list = ql.query_one("#ql-listview", OptionList)
        # The click offset counts from the corner of the WIDGET, and the
        # first line of the first option starts at the corner of the CONTENT
        # area (the OptionList brings a border of its own by default).
        # Deriving the shift from the geometry instead of guessing it avoids
        # a click that lands on the border and selects nothing — and the
        # centre of the widget would fall into the empty space below the
        # single option.
        dx = option_list.content_region.x - option_list.region.x
        dy = option_list.content_region.y - option_list.region.y
        await pilot.click(option_list, offset=(dx + 1, dy))
        await pilot.pause()
        assert messages == ["my_query"]


@pytest.mark.asyncio
async def test_query_list_paints_two_queries_with_the_same_name():
    """Two queries with the same name must not bring the screen down.

    The name is dbqm's lookup key, and while it travelled as
    `Option(conteudo, id=nome)` a `queries.json` with two `dup` queries made
    `OptionList.add_option` raise `DuplicateID` — the whole screen stopped
    mounting. The UI's creation flows block a repeated name, but the file is
    editable by hand and there is legacy history.

    Ambiguous data stays ambiguous: there is no way to know which of the two
    the person meant, and the list does not try to guess. What it must do is
    not break — paint BOTH rows, each with its own disambiguation, the way
    the old list did. Measured in the state in which the defect happened:
    the mount with the duplicated data already loaded."""
    from textual.widgets import OptionList

    queries = [
        {"name": "dup", "connection": "c1", "table": "t1", "description": "",
         "is_favorite": False, "folder": ""},
        {"name": "dup", "connection": "c2", "table": "t2", "description": "",
         "is_favorite": False, "folder": ""},
    ]
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()
        option_list = ql.query_one("#ql-listview", OptionList)
        assert option_list.option_count == 2
        assert rendered_names(option_list) == ["dup", "dup"]
        # The two rows are still distinguishable by what disambiguates them.
        pintado = [
            option_list.get_option_at_index(i).prompt.plain for i in range(2)
        ]
        assert "c1 - t1" in pintado[0]
        assert "c2 - t2" in pintado[1]


@pytest.mark.asyncio
async def test_query_list_selects_by_name_even_with_repeated_names():
    """Selection resolves by name, exactly as it did before the ids.

    Normal case (unique names): the chosen row posts its own name. Ambiguous
    case: choosing either of the two same-named rows posts the same name —
    the ambiguity shows up later, at lookup time, and not as a dead row or
    a screen that does not mount."""
    from textual.widgets import OptionList

    messages = []

    class CapturingApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield QueryListWidget()

        def on_query_selected(self, event: QuerySelected) -> None:
            messages.append(event.query_name)

    queries = [
        {"name": "alpha", "connection": "c1", "table": "t1", "description": "",
         "is_favorite": False, "folder": ""},
        {"name": "dup", "connection": "c2", "table": "t2", "description": "",
         "is_favorite": False, "folder": ""},
        {"name": "dup", "connection": "c3", "table": "t3", "description": "",
         "is_favorite": False, "folder": ""},
    ]
    app = CapturingApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()
        option_list = ql.query_one("#ql-listview", OptionList)
        option_list.focus()
        option_list.highlighted = 0
        await pilot.press("enter")
        option_list.highlighted = 2
        await pilot.press("enter")
        await pilot.pause()
        assert messages == ["alpha", "dup"]


@pytest.mark.asyncio
async def test_query_list_unnamed_query_still_responds():
    """A query with an empty name posts QuerySelected("") instead of nothing.

    An empty name is not creatable through the UI, but with the name
    travelling as `id` the `or None` turned the row into a visible row that
    did NOTHING when chosen. Posting the empty name makes the screen answer
    "Consulta '' nao encontrada" — information, which is what the ListView
    version delivered."""
    from textual.widgets import OptionList

    messages = []

    class CapturingApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield QueryListWidget()

        def on_query_selected(self, event: QuerySelected) -> None:
            messages.append(event.query_name)

    app = CapturingApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries([
            {"name": "", "connection": "c1", "table": "t1", "description": "",
             "is_favorite": False, "folder": ""},
        ])
        await pilot.pause()
        option_list = ql.query_one("#ql-listview", OptionList)
        assert option_list.option_count == 1
        option_list.focus()
        option_list.highlighted = 0
        await pilot.press("enter")
        await pilot.pause()
        assert messages == [""]


@pytest.mark.asyncio
async def test_query_list_accepts_objects():
    """Widget should work with objects that have attributes (not just dicts)."""
    from textual.widgets import OptionList
    from dbqm.models.query import Query
    q = Query(name="obj_q", connection="conn", sql="SELECT 1", description="from object", is_favorite=True)
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries([q])
        await pilot.pause()
        option_list = ql.query_one("#ql-listview", OptionList)
        assert option_list.option_count == 1
        assert rendered_names(option_list) == ["obj_q"]


@pytest.mark.asyncio
async def test_query_list_mounted_item_has_visible_hierarchy():
    """The entry as really mounted inside the screen (not just the Content
    that `hierarchical_item` returns in isolation) takes up more than one
    line, and the identity comes out visually distinct from the
    disambiguation — colour resolved by the real `Style.parse` of the active
    theme, the same mechanism Textual uses to resolve style before painting.

    Proves the WIRING all the way to the option really mounted inside the
    `OptionList` (not the `Content` that `hierarchical_item` returns in
    isolation), not the pixel painting itself — no screenshot is taken here.
    Same pattern as
    `test_mounted_connection_list_distinguishes_identity_from_disambiguation`
    in test_screens.py."""
    from textual.style import Style
    from textual.widgets import OptionList

    def cor_no_offset(conteudo, offset):
        estilo = Style()
        for start, end, span_style in conteudo.spans:
            if start <= offset < end:
                estilo = estilo + Style.parse(span_style)
        return estilo.foreground

    queries = [
        {
            "name": "consulta_longa", "connection": "MGORA7ORA9", "table": "PEDIDO",
            "description": "Verifica pedidos pendentes de faturamento no fechamento",
            "is_favorite": False, "folder": "",
        },
    ]
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()

        option_list = ql.query_one("#ql-listview", OptionList)
        conteudo = option_list.get_option_at_index(0).prompt
        texto = conteudo.plain

        assert chr(10) in texto, "item pintado deve ocupar mais de uma linha"
        assert " | " not in texto

        cor_forte = Style.parse("$ds-text-strong").foreground
        cor_apoio = Style.parse("$ds-text-muted").foreground
        cor_desabilitado = Style.parse("$ds-text-disabled").foreground
        assert len({cor_forte, cor_apoio, cor_desabilitado}) == 3

        pos_identidade = texto.index("consulta_longa")
        pos_desambiguacao = texto.index("MGORA7ORA9")
        pos_contexto = texto.index("Verifica")

        assert cor_no_offset(conteudo, pos_identidade) == cor_forte
        assert cor_no_offset(conteudo, pos_desambiguacao) == cor_apoio
        assert cor_no_offset(conteudo, pos_contexto) == cor_desabilitado


# ---------------------------------------------------------------------------
# GroupResultWidget tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.group_result import GroupResultWidget
from dbqm.core.group_engine import GroupResult, ComparisonResult, ComparisonRow


class GroupResultTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield GroupResultWidget()


@pytest.mark.asyncio
async def test_group_result_loads(sample_group_result):
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        # Should render without error
        assert w.group_result is not None
        assert w.group_result.group_name == "test_group"


@pytest.mark.asyncio
async def test_group_result_default_mode_is_flat(sample_group_result):
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        assert w.mode == "flat"
        w.load_result(sample_group_result)
        assert w.mode == "flat"


@pytest.mark.asyncio
async def test_group_result_toggle_mode(sample_group_result):
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        assert w.mode == "flat"
        w.toggle_mode()
        assert w.mode == "pivoted"
        w.toggle_mode()
        assert w.mode == "flat"


@pytest.mark.asyncio
async def test_group_result_flat_renders_tables(sample_group_result):
    """Flat mode should render one DataTable per comparison column."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        await pilot.pause()
        from textual.widgets import DataTable
        tables = w.query(DataTable)
        # sample_group_result has 1 comparison column -> 1 table
        assert len(tables) == 1


@pytest.mark.asyncio
async def test_group_result_pivoted_renders_tables(sample_group_result):
    """Pivoted mode should render one DataTable per join key."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        w.toggle_mode()
        await pilot.pause()
        from textual.widgets import DataTable
        tables = w.query(DataTable)
        # sample_group_result has 2 keys -> 2 tables
        assert len(tables) == 2


@pytest.mark.asyncio
async def test_group_result_filter_status(sample_group_result):
    """Filtering by status should only show matching rows."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        w.filter_status({"DIFF"})
        await pilot.pause()
        from textual.widgets import DataTable
        tables = w.query(DataTable)
        assert len(tables) == 1
        # Only DIFF rows: key=2
        assert tables[0].row_count == 1


@pytest.mark.asyncio
async def test_group_result_filter_status_clear(sample_group_result):
    """Clearing filter should show all rows again."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        w.filter_status({"DIFF"})
        await pilot.pause()
        w.filter_status(set())
        await pilot.pause()
        from textual.widgets import DataTable
        tables = w.query(DataTable)
        assert tables[0].row_count == 2


@pytest.mark.asyncio
async def test_group_result_key_stays_rendered_while_scrolling():
    """The "Chave" column of the comparison table does not go out of sight
    when scrolling.

    The same rule as `ResultTable` (section 6 of the grammar) applied where
    it matters most: the group comparison table has ONE column per query in
    the group, so the width grows with the group. Without the fixed key,
    scrolling to the right erases the value that says which record the
    remaining cells belong to — and comparing is the only thing this screen
    does.

    Asserts the RENDERED output, not `fixed_columns`: the attribute can stay
    at 1 and the fixing stop painting (Textual upgrade, new CSS). The
    scenario is mounted wide on purpose and the scrolling is verified
    (`scroll_x > 0`) before the final assertion is worth anything.
    """
    from textual.widgets import DataTable

    nomes = [f"CONSULTA_LONGA_{i:02d}" for i in range(1, 6)] + ["FIM_DA_TABELA"]
    resultados = {
        nome: QueryResult(
            query_name=nome, connection_name="conn",
            columns=["id", "status"], rows=[[1, "ativa"]],
            row_count=1, elapsed=0.1,
        )
        for nome in nomes
    }
    comparacao = ComparisonResult(
        column="status",
        rows=[
            ComparisonRow(
                key_value="REG-0001",
                values={
                    nome: (
                        "valor-fim"
                        if nome == "FIM_DA_TABELA"
                        else "valor-comprido-%s" % nome[-2:]
                    )
                    for nome in nomes
                },
                status="OK",
            )
        ],
        total_keys=1, equal_count=1, diff_count=0, absent_count=0,
        normalized_count=0,
    )
    largo = GroupResult(
        group_name="grupo_largo",
        query_results=resultados,
        comparisons=[comparacao],
        all_match=True,
        summary_lines=["Coluna: status"],
    )

    app = GroupResultTestApp()
    async with app.run_test(size=(40, 15)) as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(largo)
        await pilot.pause()
        tabela = w.query_one(DataTable)
        tabela.focus()
        await pilot.pause()

        # The scenario only proves something if it really does not fit.
        antes = app.export_screenshot()
        assert "Chave" in antes
        assert "FIM_DA_TABELA" not in antes

        for _ in range(60):
            await pilot.press("right")
        await pilot.pause()
        assert tabela.scroll_x > 0

        depois = app.export_screenshot()
        assert "Chave" in depois
        assert "REG-0001" in depois
        # The last column's name is short on purpose: scrolling all the way
        # to the end, a column with a long header would show up clipped
        # ("ULTA_...") and the assertion would fail because of width, not
        # because of the fixing.
        assert "FIM_DA_TABELA" in depois


@pytest.mark.asyncio
async def test_group_result_summary_shows(sample_group_result):
    """Summary section should contain comparison stats."""
    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(sample_group_result)
        await pilot.pause()
        from textual.widgets import Static
        summary = w.query_one("#gr-summary", Static)
        rendered = str(summary._Static__content)
        assert "DIVERGENTE" in rendered
        assert "status" in rendered


@pytest.mark.asyncio
async def test_group_result_status_column_resolves_verdict_colors():
    """The visible gain of the task: the Status column of the comparison
    table has to come out coloured, one colour per verdict.

    Tests the RESOLVED colour of each cell (not the markup string): a string
    test would not catch the cell staying grey/colourless because `add_row`
    received a raw `str(row.status)` instead of `Content.from_markup(...)`.
    """
    from textual.style import Style
    from textual.widgets import DataTable

    from dbqm.core.group_engine import ComparisonResult, ComparisonRow, GroupResult
    from dbqm.design.tokens import THEMES

    gr = GroupResult(
        group_name="todos_status",
        query_results={},
        comparisons=[
            ComparisonResult(
                column="status",
                rows=[
                    ComparisonRow(key_value=1, values={}, status="OK"),
                    ComparisonRow(key_value=2, values={}, status="OK*"),
                    ComparisonRow(key_value=3, values={}, status="DIFF"),
                    ComparisonRow(key_value=4, values={}, status="ABSENT"),
                ],
                total_keys=4,
                equal_count=1,
                diff_count=1,
                absent_count=1,
                normalized_count=1,
            )
        ],
        all_match=False,
        summary_lines=[],
    )

    esperado = {
        "1": THEMES["plano-escuro"]["ds-verdict-match"],
        "2": THEMES["plano-escuro"]["ds-verdict-match"],
        "3": THEMES["plano-escuro"]["ds-verdict-diff"],
        "4": THEMES["plano-escuro"]["ds-verdict-absent"],
    }

    app = GroupResultTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        await pilot.pause()
        table = w.query(DataTable).first()

        for chave, hex_esperado in esperado.items():
            conteudo = table.get_cell(chave, "status")
            pecas = list(
                conteudo.render(Style.null(), end="", parse_style=Style.parse)
            )
            cor = next(estilo.foreground for texto, estilo in pecas if texto.strip())
            assert cor.hex.lower() == hex_esperado.lower(), (
                f"celula da chave {chave}: esperava {hex_esperado}, "
                f"resolveu {cor.hex}"
            )


# ---------------------------------------------------------------------------
# Panel tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.panel import Panel
from textual.widgets import Static


class _PanelApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        with Panel("⚙️  PARAMETROS", accent=True, id="p1"):
            yield Static("body", id="inner")


@pytest.mark.asyncio
async def test_panel_renders_title_and_body():
    app = _PanelApp()
    async with app.run_test() as pilot:
        panel = app.query_one("#p1", Panel)
        title_content = str(panel.query_one("#panel-title")._Static__content)
        assert title_content.startswith("⚙️  PARAMETROS")
        assert panel.has_class("accent-focus")
        assert app.query_one("#inner", Static) in panel.query_one("#panel-body").children
        # Regression guard: the title must actually PAINT, not just exist in the
        # DOM. A `height: 1` title with a `border-bottom` leaves zero rows for
        # text, so it renders blank — assert the text reaches the screen.
        assert "PARAMETROS" in app.export_screenshot()


@pytest.mark.asyncio
async def test_dense_panel_gives_back_the_two_padding_lines():
    """Density is a decision of the COMPONENT, with a name, and not per-screen
    CSS.

    The body's vertical padding costs two lines per panel. That is cheap
    with one panel on screen and expensive with six — the Configuracoes
    screen spent 12 of 24 lines on air. Two screens had already rewritten
    `#panel-body { padding: 0 1 }` on their own, which is the "every screen
    decides for itself" that section 4 of the grammar exists to remove.

    The measure is the painted HEIGHT, and not the style rule: a CSS rule
    can read correctly and be worth nothing (that is how
    `Panel { height: auto }` stayed broken for a whole phase).
    """
    class _App(ThemedTestApp):
        # `auto` so that the panel height is the content's: it is the one
        # that changes when the body padding goes away.
        CSS = "Panel { height: auto; }"

        def compose(self) -> ComposeResult:
            with Panel("FOLGADO", id="folgado"):
                yield Static("uma linha")
            with Panel("DENSO", id="denso", dense=True):
                yield Static("uma linha")

    app = _App()
    async with app.run_test(size=(40, 24)) as pilot:
        await pilot.pause()
        folgado = app.query_one("#folgado", Panel)
        denso = app.query_one("#denso", Panel)
        assert denso.has_class("-dense")
        assert folgado.region.height - denso.region.height == 2, (
            "o modificador nao devolveu as duas linhas: folgado=%r denso=%r"
            % (folgado.region, denso.region)
        )
        moldura = crop(app, denso)
        assert moldura[0].startswith("╭") and moldura[-1].startswith("╰"), (
            "a moldura do painel denso deixou de ser desenhada: %r" % moldura
        )
        assert any("uma linha" in linha for linha in moldura), (
            "o conteudo do painel denso nao e pintado: %r" % moldura
        )


# ---------------------------------------------------------------------------
# Dialog tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.dialog import Dialog


def test_dialog_rejects_an_unknown_variant():
    """Closed variants: no back door for arbitrary styling."""
    with pytest.raises(ValueError, match="tom"):
        Dialog("Titulo", tone="roxo")
    with pytest.raises(ValueError, match="largura"):
        Dialog("Titulo", width="xxl")


@pytest.mark.asyncio
async def test_dialog_renders_the_title():
    class _DialogApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            with Dialog("Confirmar exclusao", id="d"):
                yield Static("corpo")

    app = _DialogApp()
    async with app.run_test():
        titulo = app.query_one("#d-title", Static)
        assert "Confirmar exclusao" in titulo.render().plain


def test_dialog_screen_variant_fills_the_viewport():
    """The fourth variant is the system's answer to the cases that used to
    bypass the enum by writing `.styles.width`/`.styles.height` after
    construction. It exists, and it uses percentages (not cells) because it
    is content to be displayed, not a compact form."""
    d = Dialog("Titulo", width="screen")
    # Textual stores a percentage as a "w"/"h" scalar (viewport
    # width/height); compare against the representation it actually
    # resolved, not against the input string.
    assert str(d.styles.width) == "90w"
    assert str(d.styles.height) == "85h"


def test_dialog_has_no_style_override_outside_the_component():
    """Closes the CLASS, not just the instance: `largura`/`tom` are validated
    in __init__, but nothing in Python stops anyone from writing
    `dialog.styles.width =` afterwards — the inline assignment beats
    anything __init__ may have decided, and no test and no validation can
    see that late write. A guard in the same format as
    `test_every_css_variable_is_a_token_or_a_documented_builtin`: silent
    until someone reintroduces the shortcut, and then it fails loudly.
    Needing more room is a sign of a new variant in `WIDTHS` (see "screen"),
    never of a local exception.

    Two doors, not one: the Python assignment (`dialog.styles.width = ...`)
    and the CSS rule next to it (`AlgumaTela #meu-dialog { height: 85%; }`).
    The second one escaped the original guard because it only looked at
    `.styles.`; `template_manage.py` and `error.py` hand-rolled exactly the
    "screen" variant via CSS before this fix. Every Dialog id in this repo
    contains the substring "dialog" (id="dialog", "error-dialog",
    "qp-dialog", "pkg-choice-dialog", ...), so the CSS rule scans any
    `#*dialog*{ ... }` block for width/height/max-height/min-height."""
    import re
    from pathlib import Path

    raiz_ui = Path(__file__).resolve().parents[2] / "dbqm" / "ui"
    padrao_python = re.compile(r"\.styles\.(width|height)\s*=")
    padrao_css_id = re.compile(r"#[\w-]*dialog[\w-]*\s*\{([^}]*)\}", re.IGNORECASE)
    padrao_css_prop = re.compile(r"(?<![\w-])(max-height|min-height|width|height)\s*:")

    ofensores = []
    for arquivo in sorted(raiz_ui.rglob("*.py")):
        if arquivo.name == "dialog.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        for m in padrao_python.finditer(texto):
            linha = texto.count(chr(10), 0, m.start()) + 1
            ofensores.append(f"{arquivo.relative_to(raiz_ui)}:{linha}")
        for bloco in padrao_css_id.finditer(texto):
            if padrao_css_prop.search(bloco.group(1)):
                linha = texto.count(chr(10), 0, bloco.start()) + 1
                ofensores.append(f"{arquivo.relative_to(raiz_ui)}:{linha}")

    assert not ofensores, (
        "width/height/max-height/min-height de Dialog so pode ser definido "
        f"dentro de dialog.py; achei override(s) fora do componente: {ofensores}"
    )


# ---------------------------------------------------------------------------
# TemplatesSidebar tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.templates_sidebar import TemplatesSidebar


class _TemplatesSidebarApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield TemplatesSidebar(id="tpl")


@pytest.mark.asyncio
async def test_templates_sidebar_starts_collapsed_and_toggles():
    app = _TemplatesSidebarApp()
    async with app.run_test() as pilot:
        sb = app.query_one("#tpl", TemplatesSidebar)
        # Starts collapsed so the app opens clean; Ctrl+B reveals it.
        assert sb.has_class("-collapsed")
        sb.toggle()
        assert not sb.has_class("-collapsed")
        sb.toggle()
        assert sb.has_class("-collapsed")


@pytest.mark.asyncio
async def test_templates_sidebar_shows_hint_when_empty():
    from textual.widgets import OptionList
    from dbqm.ui.widgets.empty_state import EmptyState
    app = _TemplatesSidebarApp()
    async with app.run_test() as pilot:
        sb = app.query_one("#tpl", TemplatesSidebar)
        sb._reload()  # no templates in the test config
        await pilot.pause()
        # With zero templates the hint shows and the list is hidden.
        assert sb.query_one("#tpl-empty", EmptyState).display is True
        assert sb.query_one("#tpl-list", OptionList).display is False
        # And the sidebar title itself paints (same border-bottom/height guard).
        sb.remove_class("-collapsed")
        await pilot.pause()
        assert "TEMPLATES" in app.export_screenshot()


@pytest.mark.asyncio
async def test_templates_sidebar_empty_state_action_switches_to_tools():
    """The EmptyState's "Abrir Ferramentas" button must not be a dead end."""
    from textual.widgets import Button

    switched = []

    class _SidebarWithSwitch(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield TemplatesSidebar(id="tpl")

        def action_switch_tab(self, tab_id: str) -> None:
            switched.append(tab_id)

    app = _SidebarWithSwitch()
    async with app.run_test() as pilot:
        sb = app.query_one("#tpl", TemplatesSidebar)
        sb._reload()  # no templates in the test config
        await pilot.pause()
        sb.query_one("#abrir-ferramentas", Button).press()
        await pilot.pause()
        assert switched == ["tab-ferramentas"]


@pytest.mark.asyncio
async def test_templates_sidebar_option_selected_posts_message():
    from textual.widgets import OptionList
    from textual.widgets.option_list import Option

    messages = []

    class CapturingApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield TemplatesSidebar(id="tpl")

        def on_templates_sidebar_template_chosen(self, event: TemplatesSidebar.TemplateChosen) -> None:
            messages.append(event.sql)

    app = CapturingApp()
    async with app.run_test() as pilot:
        sb = app.query_one("#tpl", TemplatesSidebar)
        ol = sb.query_one("#tpl-list", OptionList)
        ol.clear_options()
        sb._sqls = {"demo": "SELECT 1 FROM DUAL"}
        ol.add_option(Option("demo", id="demo"))
        await pilot.pause()
        ol.highlighted = 0
        await pilot.press("enter")
        await pilot.pause()
        assert messages == ["SELECT 1 FROM DUAL"]


# ---------------------------------------------------------------------------
# EmptyState tests
# ---------------------------------------------------------------------------

def test_empty_state_requires_an_action():
    """An empty view that only reports being empty is a defect, not a state."""
    from dbqm.ui.widgets.empty_state import EmptyState

    with pytest.raises(TypeError):
        EmptyState("Consultas", "Voce ainda nao salvou nenhuma")  # no action


@pytest.mark.asyncio
async def test_empty_state_offers_the_first_action():
    from textual.widgets import Button
    from dbqm.ui.widgets.empty_state import EmptyState

    class _EmptyStateApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield EmptyState(
                what="Consultas",
                why="Voce ainda nao salvou nenhuma consulta",
                action_label="Criar consulta",
                action_id="criar-consulta",
            )

    app = _EmptyStateApp()
    async with app.run_test():
        botao = app.query_one("#criar-consulta", Button)
        assert botao.label.plain == "Criar consulta"


# ---------------------------------------------------------------------------
# Skeleton tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skeleton_has_the_shape_of_the_content_to_come():
    """Shaped like the content to come, not a centred spinner: it avoids the
    layout jump when the real result arrives."""
    from dbqm.ui.widgets.skeleton import Skeleton

    class _EsqueletoApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield Skeleton(rows=6, columns=3, id="e")

    app = _EsqueletoApp()
    async with app.run_test():
        esqueleto = app.query_one("#e", Skeleton)
        assert len(esqueleto.query(".skeleton-row")) == 6


@pytest.mark.asyncio
async def test_read_only_is_visually_distinct_from_disabled():
    """Read-only looks like content; disabled looks like an inert control —
    confusing the two is the defect this task exists to prevent."""
    from textual.widgets import Input

    class _EstadosApp(ThemedTestApp):
        CSS = "Input { width: 20; }"

        def compose(self) -> ComposeResult:
            yield Input(value="a", id="ro", classes="-read-only")
            yield Input(value="b", id="off", disabled=True)

    app = _EstadosApp()
    async with app.run_test():
        ro = app.query_one("#ro", Input)
        off = app.query_one("#off", Input)
        assert ro.styles.color != off.styles.color


# ---------------------------------------------------------------------------
# hierarchical_item tests
# ---------------------------------------------------------------------------

def test_hierarchical_item_puts_identity_alone_on_the_first_line():
    from dbqm.ui.widgets.hierarchical_list import hierarchical_item

    c = hierarchical_item("MGORA7ORA9", "Oracle/TNS - MGORA7ORA9", "Producao prod-day")
    linhas = str(c).split("\n")
    assert linhas[0].strip() == "MGORA7ORA9"
    assert "Oracle/TNS" in linhas[1]
    assert "Producao" in linhas[2]


def test_hierarchical_item_omits_empty_lines():
    from dbqm.ui.widgets.hierarchical_list import hierarchical_item

    assert len(str(hierarchical_item("SO_NOME")).split("\n")) == 1


def test_hierarchical_item_omits_only_the_middle_line_when_only_it_is_missing():
    """A disambiguation present and an empty context have to give two lines,
    with no hole in the middle — not a skipped third blank line."""
    from dbqm.ui.widgets.hierarchical_list import hierarchical_item

    c = hierarchical_item("MGORA7ORA9", "Oracle/TNS - MGORA7ORA9")
    linhas = str(c).split("\n")
    assert len(linhas) == 2
    assert linhas[0].strip() == "MGORA7ORA9"
    assert "Oracle/TNS" in linhas[1]


def test_hierarchical_item_indents_every_line_of_a_multi_line_field():
    """A field (disambiguation or context) that already arrives with an
    embedded line break (e.g. connections.py pre-wrapping a long description
    into two logical lines) has to carry the indent on EVERY line, not just
    on the first. The indent is the cue for "this belongs to the entry
    above"; losing it on a continuation aligns that line with the IDENTITY
    column (the next entry), the same defect that motivated this whole
    phase - not being able to tell where one entry ends and the next
    begins."""
    from dbqm.ui.widgets.hierarchical_list import _INDENT, hierarchical_item

    contexto = "\n".join([
        "Portal ASDADM em ATSSUS ambiente",
        "da sustentacao Mapfre com",
        "replicacao",
    ])
    c = hierarchical_item("ASDADM (ASD)", "Oracle/TNS - ATSSUS", contexto)
    linhas = str(c).split("\n")
    assert len(linhas) == 5
    assert linhas[0] == "ASDADM (ASD)"
    # The four disambiguation+context lines ALL have the same indent -
    # none of them starts in column 0, the identity column.
    for linha in linhas[1:]:
        assert linha.startswith(_INDENT), f"linha sem recuo: {linha!r}"
    assert linhas[1] == _INDENT + "Oracle/TNS - ATSSUS"
    assert linhas[2] == _INDENT + "Portal ASDADM em ATSSUS ambiente"
    assert linhas[3] == _INDENT + "da sustentacao Mapfre com"
    assert linhas[4] == _INDENT + "replicacao"


def test_hierarchical_item_does_not_read_content_brackets_as_markup():
    """A connection name or description comes from user data, and free text
    with a bracket (an environment tag, a ticket reference) is a plausible
    pattern in this domain — e.g. `Proposta [PROD]`.

    Going through `Content.from_markup` would treat `[PROD]` as an attempted
    tag and, because of the known asymmetry of Textual's parser between
    `\\[` and `\\]` (see `result_table.py`), a naive escape would return the
    text altered (a leftover backslash). The proof here is a round trip:
    what goes in has to come out identical in `.plain`, bracket by bracket —
    not just "it did not blow up".
    """
    from dbqm.ui.widgets.hierarchical_list import hierarchical_item

    entrada = "Proposta [PROD] com [/] e ] solto"
    c = hierarchical_item(entrada, entrada, entrada)
    for linha in str(c).split("\n"):
        assert entrada in linha


@pytest.mark.asyncio
async def test_hierarchical_item_uses_the_grammar_color_hierarchy():
    """Identity, disambiguation and context have to come out with three
    different colours actually resolved in the active theme — not merely the
    token name showing up in the markup string (lesson from Task 1)."""
    from textual.style import Style

    from dbqm.ui.widgets.hierarchical_list import hierarchical_item

    def cor_no_offset(conteudo, offset):
        estilo = Style()
        for start, end, span_style in conteudo.spans:
            if start <= offset < end:
                estilo = estilo + Style.parse(span_style)
        return estilo.foreground

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield from ()

    app = _App()
    async with app.run_test():
        conteudo = hierarchical_item(
            "MGORA7ORA9", "Oracle/TNS - MGORA7ORA9", "Producao prod-day"
        )
        texto = conteudo.plain

        cor_forte = Style.parse("$ds-text-strong").foreground
        cor_apoio = Style.parse("$ds-text-muted").foreground
        cor_desabilitado = Style.parse("$ds-text-disabled").foreground
        assert len({cor_forte, cor_apoio, cor_desabilitado}) == 3

        pos_identidade = texto.index("MGORA7ORA9")
        pos_desambiguacao = texto.index("Oracle/TNS")
        pos_contexto = texto.index("Producao")

        assert cor_no_offset(conteudo, pos_identidade) == cor_forte
        assert cor_no_offset(conteudo, pos_desambiguacao) == cor_apoio
        assert cor_no_offset(conteudo, pos_contexto) == cor_desabilitado
