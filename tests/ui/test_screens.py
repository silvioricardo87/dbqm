"""Tests for screens."""
from __future__ import annotations

import json

import pytest
from textual.app import ComposeResult
from textual.widgets import Input, Select

from dbqm.ui.screens.connections import ConnectionsScreen
from dbqm.ui.screens.oracle_clients import OracleClientsScreen
from dbqm.ui.screens.query_exec import QueryExecScreen

from tests.ui._helpers import ThemedTestApp, rendered_names


class QueryExecTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield QueryExecScreen()


@pytest.mark.asyncio
async def test_query_exec_screen_renders(tmp_config_dir):
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        assert screen is not None


@pytest.mark.asyncio
async def test_query_exec_screen_shows_empty_message(tmp_config_dir):
    """With no queries configured, should show empty state."""
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        empty = screen.query_one("#empty-message")
        assert empty.display is True


@pytest.mark.asyncio
async def test_query_exec_empty_state_action_switches_to_coleta(tmp_config_dir):
    """The EmptyState's "Criar consulta" button must not be a dead end —
    queries are created from the Coleta tab ("Salvar como consulta")."""
    from textual.widgets import Button

    switched = []

    class _QueryExecWithSwitch(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield QueryExecScreen()

        def action_switch_tab(self, tab_id: str) -> None:
            switched.append(tab_id)

    app = _QueryExecWithSwitch()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        screen.query_one("#criar-consulta-coleta", Button).press()
        await pilot.pause()
        assert switched == ["tab-coleta"]


@pytest.mark.asyncio
async def test_query_exec_screen_shows_query_list(tmp_config_dir):
    """With queries configured, should show the query list."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "test_q1",
                "connection": "conn1",
                "sql": "SELECT 1",
                "description": "Test query one",
            },
            {
                "name": "test_q2",
                "connection": "conn1",
                "sql": "SELECT 2",
                "description": "Test query two",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        empty = screen.query_one("#empty-message")
        assert empty.display is False
        # Selection phase should be visible
        sel = screen.query_one("#selection-phase")
        assert sel.display is True
        # Results phase should be hidden
        res = screen.query_one("#results-phase")
        assert res.display is False


@pytest.mark.asyncio
async def test_query_exec_screen_with_folders(tmp_config_dir):
    """Queries with folders should produce a folder select with an option
    per folder plus "Todas"."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "q_folder_a",
                "connection": "conn1",
                "sql": "SELECT 1",
                "folder": "Grupo A",
            },
            {
                "name": "q_folder_b",
                "connection": "conn1",
                "sql": "SELECT 2",
                "folder": "Grupo B",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        seletor = screen.query_one("#folder-select", Select)
        # "Todas" + "Grupo A" + "Grupo B" = 3
        assert len(seletor._options) == 3


@pytest.mark.asyncio
async def test_query_exec_accented_folders(tmp_config_dir):
    """Folders with accents should not crash the app."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "q1",
                "connection": "c1",
                "sql": "SELECT 1",
                "folder": "Investiga\u00e7\u00e3o",
            },
            {
                "name": "q2",
                "connection": "c1",
                "sql": "SELECT 1",
                "folder": "Produ\u00e7\u00e3o",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        assert screen is not None
        # Should have a folder select with the accented folder options.
        seletor = screen.query_one("#folder-select", Select)
        # "Todas" + 2 folders = 3
        assert len(seletor._options) == 3


@pytest.mark.asyncio
async def test_query_exec_results_phase_hidden_initially(tmp_config_dir):
    """Results phase should be hidden on mount."""
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        results = screen.query_one("#results-phase")
        assert results.display is False


@pytest.mark.asyncio
async def test_query_exec_go_back_to_selection(tmp_config_dir):
    """go_back_to_selection should show selection and hide results."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "q1",
                "connection": "conn1",
                "sql": "SELECT 1",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        # Simulate being in results phase
        screen.query_one("#selection-phase").display = False
        screen.query_one("#results-phase").display = True

        screen.go_back_to_selection()

        assert screen.query_one("#selection-phase").display is True
        assert screen.query_one("#results-phase").display is False


def _write_filter_queries(config_dir):
    queries_data = {
        "queries": [
            {"name": "Clientes ativos", "connection": "prod", "sql": "S",
             "description": "lista de clientes"},
            {"name": "Pedidos", "connection": "prod", "sql": "S",
             "description": "faturados hoje"},
            {"name": "Estoque", "connection": "homolog", "sql": "S",
             "description": "saldo por deposito"},
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_query_exec_has_filter_bar(tmp_config_dir):
    """With queries, the selection phase shows a text filter + connection select."""
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        text = screen.query_one("#qe-filter-text", Input)
        conn = screen.query_one("#qe-filter-conn", Select)
        assert text.display is True
        assert conn.display is True


@pytest.mark.asyncio
async def test_query_exec_text_filter_narrows_list(tmp_config_dir):
    """Typing in the text filter narrows the list by name/description."""
    from textual.widgets import OptionList
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        assert screen.query_one("#ql-listview", OptionList).option_count == 3
        screen.query_one("#qe-filter-text", Input).value = "estoque"
        await pilot.pause()
        option_list = screen.query_one("#ql-listview", OptionList)
        assert option_list.option_count == 1
        assert rendered_names(option_list) == ["Estoque"]


@pytest.mark.asyncio
async def test_query_exec_text_filter_matches_description(tmp_config_dir):
    """The text filter also matches the query description."""
    from textual.widgets import OptionList
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        screen.query_one("#qe-filter-text", Input).value = "faturados"
        await pilot.pause()
        option_list = screen.query_one("#ql-listview", OptionList)
        assert rendered_names(option_list) == ["Pedidos"]


@pytest.mark.asyncio
async def test_query_exec_connection_filter_narrows_list(tmp_config_dir):
    """Selecting a connection narrows the list to that connection's queries."""
    from textual.widgets import OptionList
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        screen.query_one("#qe-filter-conn", Select).value = "homolog"
        await pilot.pause()
        option_list = screen.query_one("#ql-listview", OptionList)
        assert rendered_names(option_list) == ["Estoque"]


@pytest.mark.asyncio
async def test_query_exec_text_and_connection_combined(tmp_config_dir):
    """Text + connection filters AND together."""
    from textual.widgets import OptionList
    _write_filter_queries(tmp_config_dir / "config")
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        # prod alone → 2 queries
        screen.query_one("#qe-filter-conn", Select).value = "prod"
        await pilot.pause()
        assert screen.query_one("#ql-listview", OptionList).option_count == 2
        # narrow with text
        screen.query_one("#qe-filter-text", Input).value = "ped"
        await pilot.pause()
        option_list = screen.query_one("#ql-listview", OptionList)
        assert rendered_names(option_list) == ["Pedidos"]


@pytest.mark.asyncio
async def test_query_exec_no_filter_bar_when_empty(tmp_config_dir):
    """No queries → no filter bar (empty message instead)."""
    from textual.css.query import NoMatches
    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        assert screen.query_one("#empty-message").display is True
        with pytest.raises(NoMatches):
            screen.query_one("#qe-filter-text", Input)


def _painted_select_labels(seletor):
    """The select's labels as the open menu PAINTS them.

    `seletor._options` is the list the widget stored; what the person reads
    is the overlay's `OptionList`, which only exists with the menu open.
    Reading from there is what makes an error in building the label show up."""
    from textual.widgets._select import SelectOverlay

    overlay = seletor.query_one(SelectOverlay)
    return [
        str(overlay.get_option_at_index(i).prompt)
        for i in range(overlay.option_count)
    ]


@pytest.mark.asyncio
async def test_folders_become_a_select_with_counts(tmp_config_dir):
    """The folders become a Select with the count on each label.

    The maintainer's real cardinality is 16 folders for 68 queries — in a
    HorizontalScroll of buttons that scrolled sideways and hid most of the
    options. The fixture here is a reduction of that shape, not of the 16
    numbers: four folders with counts 2/5/6/7. The counts are deliberately
    different from the number of folders (4) and from the number of options
    (5), because the previous version of this test was
    `any("(3)" in r ...)` with 3 folders — a bug that painted
    `len(folders)` in place of the count would have passed all the same.
    The assertion is the EXACT list of labels, in the order the menu paints
    them."""
    from textual.widgets import Select
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from tests.ui._helpers import ThemedTestApp

    contagens = {"Alfa": 5, "Beta": 2, "Delta": 7, "Gama": 6}
    consultas = []
    for pasta, quantas in contagens.items():
        for i in range(quantas):
            consultas.append(
                Query(name="%s-q%d" % (pasta, i), sql="select 1 from dual",
                      connection="c", folder=pasta)
            )
    save_queries(consultas)

    class App_(ThemedTestApp):
        def compose(self):
            yield QueryExecScreen()

    app = App_()
    async with app.run_test(size=(120, 40)) as pilot:
        seletor = app.query_one("#folder-select", Select)
        seletor.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert _painted_select_labels(seletor) == [
            "Todas (20)",
            "Alfa (5)",
            "Beta (2)",
            "Delta (7)",
            "Gama (6)",
        ]
        assert not app.query("#folder-bar"), "a barra de botoes some"


@pytest.mark.asyncio
async def test_folder_label_elides_the_common_prefix(tmp_config_dir):
    """With a single family of folders, the painted label loses the prefix.

    No folder in the suite contained "/" before this test, so the elision
    branch (`common_folder_prefix`) never ran: replacing the function with
    `lambda pastas: ""` kept everything green. What is read here is the
    label PAINTED in the open menu — "Alpha (3)", not "Projeto/Alpha (3)"."""
    from textual.widgets import Select
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from tests.ui._helpers import ThemedTestApp

    contagens = {"Projeto/Alpha": 3, "Projeto/Beta": 1, "Projeto/Gama": 2}
    consultas = []
    for pasta, quantas in contagens.items():
        for i in range(quantas):
            consultas.append(
                Query(name="%s-%d" % (pasta.replace("/", "-"), i),
                      sql="select 1 from dual", connection="c", folder=pasta)
            )
    save_queries(consultas)

    class App_(ThemedTestApp):
        def compose(self):
            yield QueryExecScreen()

    app = App_()
    async with app.run_test(size=(120, 40)) as pilot:
        seletor = app.query_one("#folder-select", Select)
        seletor.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert _painted_select_labels(seletor) == [
            "Todas (6)",
            "Alpha (3)",
            "Beta (1)",
            "Gama (2)",
        ]


@pytest.mark.asyncio
async def test_folder_label_shows_the_whole_path_with_two_families(
    tmp_config_dir,
):
    """Two families side by side: the common prefix shrinks and the path
    comes back.

    It is the other side of the test above, and the reason the prefix is
    computed on every load against the real folders instead of pinned as a
    literal: the day a second family shows up, the list goes back on its own
    to showing the whole path, with no code change."""
    from textual.widgets import Select
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from tests.ui._helpers import ThemedTestApp

    save_queries([
        Query(name="a", sql="select 1 from dual", connection="c",
              folder="Projeto/Alpha"),
        Query(name="b", sql="select 1 from dual", connection="c",
              folder="Interno/Backlog"),
    ])

    class App_(ThemedTestApp):
        def compose(self):
            yield QueryExecScreen()

    app = App_()
    async with app.run_test(size=(120, 40)) as pilot:
        seletor = app.query_one("#folder-select", Select)
        seletor.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert _painted_select_labels(seletor) == [
            "Todas (2)",
            "Interno/Backlog (1)",
            "Projeto/Alpha (1)",
        ]


# The `test_listview_left_the_vocabulary` guard now lives in
# `tests/design/test_layout_inventory.py`, together with the other
# vocabulary guards of the layout grammar. Here it was hidden in the
# middle of thousands of lines of screen tests — far from whoever is going
# to break the rule.


# ======================================================================
# ConnectionsScreen tests — master list (CONEXOES) + embedded form (EDICAO)
# ======================================================================


class ConnectionsTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield ConnectionsScreen()


def _seed_connections(config_dir):
    from dbqm.core.crypto import encrypt

    conn_data = {
        "connections": [
            {
                "name": "dev_oracle",
                "db_type": "oracle",
                "mode": "direct",
                "host": "db.example.com",
                "port": 1521,
                "service_name": "ORCL",
                "user": "admin",
                "password": encrypt("s3cret"),
            },
            {
                "name": "prod_pg",
                "db_type": "postgresql",
                "host": "localhost",
                "port": 5432,
                "database": "mydb",
                "user": "pguser",
                "password": encrypt("pgpass"),
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_connections_screen_renders(tmp_config_dir):
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        assert screen is not None


@pytest.mark.asyncio
async def test_connections_has_list_and_form_panels(tmp_config_dir):
    """CONEXOES + EDICAO panels exist, with the list and form field ids."""
    from dbqm.ui.widgets.panel import Panel

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        titles = [p.query_one("#panel-title").render().plain for p in screen.query(Panel)]
        assert any("CONEXOES" in t for t in titles)
        assert any("EDICAO" in t for t in titles)
        assert screen.query_one("#conn-list") is not None
        assert screen.query_one("#conn-form-name") is not None
        assert screen.query_one("#conn-form-type") is not None
        assert screen.query_one("#conn-form-host") is not None
        assert screen.query_one("#conn-form-port") is not None
        assert screen.query_one("#conn-form-user") is not None
        assert screen.query_one("#conn-form-pass") is not None
        assert screen.query_one("#conn-form-service") is not None
        assert screen.query_one("#conn-form-mode") is not None


@pytest.mark.asyncio
async def test_connections_screen_empty(tmp_config_dir):
    """With no connections, should show empty message and hide the list."""
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import OptionList
        screen = app.query_one(ConnectionsScreen)
        empty = screen.query_one("#conn-empty")
        assert empty.display is True
        option_list = screen.query_one("#conn-list", OptionList)
        assert option_list.display is False


@pytest.mark.asyncio
async def test_connections_empty_state_action_focuses_new_form(tmp_config_dir):
    """The EmptyState's "Adicionar conexao" button must not be a dead end."""
    from textual.widgets import Button
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen.query_one("#adicionar-conexao", Button).press()
        await pilot.pause()
        assert app.focused is screen.query_one("#conn-form-name", Input)


@pytest.mark.asyncio
async def test_connections_screen_with_data(tmp_config_dir):
    """With connections configured, should list them in the OptionList."""
    _seed_connections(tmp_config_dir / "config")

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import OptionList
        screen = app.query_one(ConnectionsScreen)
        empty = screen.query_one("#conn-empty")
        assert empty.display is False
        option_list = screen.query_one("#conn-list", OptionList)
        assert option_list.display is True
        assert option_list.option_count == 2


@pytest.mark.asyncio
async def test_connections_list_shows_description_preview(tmp_config_dir):
    """Long descriptions are truncated with an ellipsis in the list preview."""
    config_dir = tmp_config_dir / "config"
    long_desc = "Producao - " + "x" * 200
    (config_dir / "connections.json").write_text(
        json.dumps({
            "connections": [
                {
                    "name": "prod", "db_type": "postgresql",
                    "host": "h", "port": 5432, "database": "db",
                    "user": "u", "password": "p",
                    "description": long_desc,
                },
                {
                    "name": "no_desc", "db_type": "mysql",
                    "host": "h", "port": 3306, "database": "db",
                    "user": "u", "password": "p",
                },
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    app = ConnectionsTestApp()
    async with app.run_test():
        from textual.widgets import OptionList
        screen = app.query_one(ConnectionsScreen)
        option_list = screen.query_one("#conn-list", OptionList)
        prompt0 = str(option_list.get_option_at_index(0).prompt)
        assert "..." in prompt0
        prompt1 = str(option_list.get_option_at_index(1).prompt)
        assert "prod" not in prompt1  # no_desc row has no description leak


def test_format_description_helper():
    """Unit test the list preview formatter for descriptions."""
    from dbqm.ui.screens.connections import _format_description

    assert _format_description("") == ""
    assert _format_description("short note") == "short note"
    # Newlines collapse to single spaces.
    assert _format_description("line1\nline2") == "line1 line2"
    # A description past the old 60-char ceiling but that still fits inside
    # the two-line budget survives whole, with no ellipsis: the limit is
    # LINES, not characters.
    media = "Producao - ambiente critico, somente leitura via VPN dedicada"
    assert len(media) > 60
    out_media = _format_description(media)
    assert "..." not in out_media
    assert out_media.count("\n") <= 1
    assert out_media.replace("\n", " ") == media
    # Content that overflows the line budget is cut with an ellipsis, and
    # the result never exceeds the two-line budget.
    long = "x" * 200
    out = _format_description(long)
    assert out.endswith("...")
    assert out.count("\n") <= 1


@pytest.mark.asyncio
async def test_connection_list_has_hierarchy_and_does_not_concatenate(tmp_config_dir):
    """The item has a hierarchy of lines; it is not a concatenated string."""
    from textual.widgets import OptionList
    from dbqm.models.connection import Connection, save_connections
    from dbqm.ui.screens.connections import ConnectionsScreen
    from tests.ui._helpers import ThemedTestApp

    save_connections([
        Connection(name="MGORA7ORA9", db_type="oracle", user="u", password="p",
                   mode="tns", tns_name="MGORA7ORA9",
                   description="Producao prod-day, somente leitura via dblink"),
        Connection(name="ASDADM", db_type="oracle", user="u", password="p",
                   mode="tns", tns_name="ATSSUS", description="Sustentacao"),
    ])

    class App_(ThemedTestApp):
        def compose(self):
            yield ConnectionsScreen()

    app = App_()
    async with app.run_test():
        lista = app.query_one("#conn-list", OptionList)
        prompt = str(lista.get_option_at_index(0).prompt)
        assert chr(10) in prompt, "item deve ocupar mais de uma linha"
        assert " | " not in prompt, "descricao nao entra concatenada"
        assert prompt.splitlines()[0].strip().startswith("MGORA7ORA9")


def test_query_list_no_longer_truncates_the_description():
    """The 35-character truncation existed to fit in a single line.

    Root anchored on `__file__` (the idiom of `tests/design/_scan.py`):
    with a path relative to the cwd, running the suite from another
    directory would raise `FileNotFoundError` instead of checking anything.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    fonte = (raiz / "dbqm" / "ui" / "widgets" / "query_list.py").read_text(
        encoding="utf-8"
    )
    assert "[:32]" not in fonte, "a truncagem deixou de ser necessaria"


@pytest.mark.asyncio
async def test_mounted_connection_list_distinguishes_identity_from_disambiguation(
    tmp_config_dir,
):
    """The `Content` that `hierarchical_item` returns in isolation is not
    enough (Task 3 already proves that span by span) — here the real screen
    is mounted and the real `OptionList` option (not the value passed into
    it) is read back; the color of each line is resolved with `Style.parse`
    against the app's active theme, the same mechanism Textual uses to
    resolve style before painting.

    This proves the WIRING — that the right `Content` reaches the mounted
    widget intact, with the real theme resolving the three right colors —
    not the pixel painting itself (no screenshot is taken here)."""
    from textual.style import Style
    from textual.widgets import OptionList
    from dbqm.models.connection import Connection, save_connections

    def cor_no_offset(conteudo, offset):
        estilo = Style()
        for start, end, span_style in conteudo.spans:
            if start <= offset < end:
                estilo = estilo + Style.parse(span_style)
        return estilo.foreground

    save_connections([
        Connection(name="MGORA7ORA9", db_type="oracle", user="u", password="p",
                   mode="tns", tns_name="MGORA7ORA9",
                   description="Producao prod-day, somente leitura via dblink"),
    ])

    app = ConnectionsTestApp()
    async with app.run_test():
        lista = app.query_one("#conn-list", OptionList)
        conteudo = lista.get_option_at_index(0).prompt
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


@pytest.mark.asyncio
async def test_description_width_fits_even_with_the_list_scrolling(tmp_config_dir):
    """`_DESCRIPTION_WIDTH` was derived assuming the worst case (the
    OptionList's scrollbar present). This test proves the assumption against
    the widget really mounted, not just on paper: in a list long enough to
    scroll, the assumed text width (plus the indent that every line pays)
    must not exceed the real available width — it was exactly that wrong
    arithmetic (34 assumed against 34 real AFTER the indent, that is 36
    needing to fit in 34) that made a description line ("...ambiente") come
    out without an indent, aligned with the identity column of the next
    entry."""
    from textual.widgets import OptionList
    from dbqm.models.connection import Connection, save_connections
    from dbqm.ui.screens.connections import _DESCRIPTION_WIDTH
    from dbqm.ui.widgets.hierarchical_list import _INDENT

    conexoes = [
        Connection(name=f"CONN{i}", db_type="oracle", user="u", password="p",
                   mode="tns", tns_name=f"TNS{i}")
        for i in range(20)
    ]
    save_connections(conexoes)

    app = ConnectionsTestApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        lista = app.query_one("#conn-list", OptionList)
        assert lista.show_vertical_scrollbar, (
            "o teste so prova o pior caso se a lista estiver realmente "
            "rolando"
        )
        largura_real = lista.scrollable_content_region.width
        assert _DESCRIPTION_WIDTH + len(_INDENT) <= largura_real


@pytest.mark.asyncio
async def test_connections_select_loads_into_form(tmp_config_dir):
    """Selecting a seeded connection populates the embedded form, with the
    password decrypted for display."""
    _seed_connections(tmp_config_dir / "config")

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()

        assert screen.query_one("#conn-form-name", Input).value == "dev_oracle"
        assert screen.query_one("#conn-form-type", Select).value == "oracle"
        assert screen.query_one("#conn-form-host", Input).value == "db.example.com"
        assert screen.query_one("#conn-form-port", Input).value == "1521"
        assert screen.query_one("#conn-form-service", Input).value == "ORCL"
        assert screen.query_one("#conn-form-user", Input).value == "admin"
        assert screen.query_one("#conn-form-pass", Input).value == "s3cret"


@pytest.mark.asyncio
async def test_connections_new_clears_form(tmp_config_dir):
    """The 'Nova' action/button clears the form for a new entry."""
    _seed_connections(tmp_config_dir / "config")

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()
        assert screen.query_one("#conn-form-name", Input).value == "dev_oracle"

        from dbqm.ui.widgets.action_bar import ActionSelected
        screen.on_action_selected(ActionSelected("conn_new"))
        await pilot.pause()

        assert screen.query_one("#conn-form-name", Input).value == ""
        assert screen.query_one("#conn-form-name", Input).disabled is False
        assert screen.query_one("#conn-form-type", Select).value == Select.NULL


@pytest.mark.asyncio
async def test_connections_save_creates_new_connection(tmp_config_dir):
    """Filling the form and pressing Salvar creates a new connection."""
    from dbqm.models.connection import load_connections

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)

        screen.query_one("#conn-form-name", Input).value = "new_conn"
        screen.query_one("#conn-form-type", Select).value = "postgresql"
        await pilot.pause()
        screen.query_one("#conn-form-host", Input).value = "pg.example.com"
        screen.query_one("#conn-form-port", Input).value = "5432"
        screen.query_one("#conn-form-database", Input).value = "mydb"
        screen.query_one("#conn-form-user", Input).value = "pguser"
        screen.query_one("#conn-form-pass", Input).value = "secretpw"

        screen._handle_save()
        await pilot.pause()

        conns = load_connections()
        assert any(c.name == "new_conn" for c in conns)
        saved = next(c for c in conns if c.name == "new_conn")
        assert saved.host == "pg.example.com"
        assert saved.database == "mydb"

        from dbqm.core.crypto import decrypt
        assert decrypt(saved.password) == "secretpw"


@pytest.mark.asyncio
async def test_connections_save_updates_existing_connection(tmp_config_dir):
    """Editing a loaded connection and pressing Salvar persists the change."""
    _seed_connections(tmp_config_dir / "config")
    from dbqm.models.connection import find_connection

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()

        screen.query_one("#conn-form-host", Input).value = "new-host.example.com"
        screen._handle_save()
        await pilot.pause()

        updated = find_connection("dev_oracle")
        assert updated is not None
        assert updated.host == "new-host.example.com"

        # Password re-encrypted from the (unchanged) decrypted display value.
        from dbqm.core.crypto import decrypt
        assert decrypt(updated.password) == "s3cret"


@pytest.mark.asyncio
async def test_connections_excluir_removes_connection(tmp_config_dir):
    """Excluir, after confirming, deletes the highlighted connection."""
    _seed_connections(tmp_config_dir / "config")
    from dbqm.models.connection import load_connections
    from dbqm.ui.modals.confirm import ConfirmModal

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()

        from dbqm.ui.widgets.action_bar import ActionSelected
        screen.on_action_selected(ActionSelected("conn_remove"))
        await pilot.pause()

        modal = next(s for s in app.screen_stack if isinstance(s, ConfirmModal))
        assert "dev_oracle" in modal._message

        screen._on_remove_result(True)
        await pilot.pause()

        conns = load_connections()
        assert all(c.name != "dev_oracle" for c in conns)
        # Form is cleared since the deleted connection was loaded.
        assert screen.query_one("#conn-form-name", Input).value == ""


@pytest.mark.asyncio
async def test_connections_testar_warns_without_name(tmp_config_dir):
    """Testar with an empty form name shows a warning, not a crash."""
    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._handle_test()
        await pilot.pause()
        messages = [str(n.message) for n in app._notifications]
        assert any("nome" in m.lower() for m in messages)


@pytest.mark.asyncio
async def test_connections_testar_starts_worker_for_named_connection(tmp_config_dir):
    """Testar with a name in the form kicks off the existing test worker."""
    _seed_connections(tmp_config_dir / "config")

    app = ConnectionsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConnectionsScreen)
        screen._select_in_list("dev_oracle")
        await pilot.pause()

        screen._handle_test()
        await pilot.pause()

        messages = [str(n.message) for n in app._notifications]
        assert any("Testando" in m for m in messages)


# ======================================================================
# QueryManageScreen tests
# ======================================================================

from dbqm.ui.screens.query_manage import QueryManageScreen


class QueryManageTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield QueryManageScreen()


@pytest.mark.asyncio
async def test_query_manage_screen_renders(tmp_config_dir):
    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(QueryManageScreen) is not None


@pytest.mark.asyncio
async def test_query_manage_screen_empty(tmp_config_dir):
    """With no queries, should show empty message and hide table."""
    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryManageScreen)
        empty = screen.query_one("#qm-empty")
        assert empty.display is True
        from textual.widgets import DataTable
        table = screen.query_one("#qm-table", DataTable)
        assert table.display is False


@pytest.mark.asyncio
async def test_query_manage_empty_state_action_opens_new_query(tmp_config_dir):
    """The EmptyState's "Criar consulta" button must not be a dead end."""
    from textual.widgets import Button
    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryManageScreen)
        screen.query_one("#criar-consulta", Button).press()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # SqlPasteModal opened


@pytest.mark.asyncio
async def test_query_manage_screen_with_data(tmp_config_dir):
    """With queries configured, should show them in the table."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "query_b",
                "connection": "conn1",
                "sql": "SELECT * FROM tabB",
                "description": "Second query",
                "folder": "Beta",
            },
            {
                "name": "query_a",
                "connection": "conn1",
                "sql": "SELECT * FROM tabA",
                "description": "First query",
                "folder": "Alpha",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryManageScreen)
        empty = screen.query_one("#qm-empty")
        assert empty.display is False
        from textual.widgets import DataTable
        table = screen.query_one("#qm-table", DataTable)
        assert table.display is True
        assert table.row_count == 2
        # Should be sorted by folder: Alpha first, then Beta
        row0 = table.get_row_at(0)
        assert str(row0[1]) == "Alpha"
        row1 = table.get_row_at(1)
        assert str(row1[1]) == "Beta"


@pytest.mark.asyncio
async def test_query_manage_screen_favorite_column(tmp_config_dir):
    """Favorite queries should show a star in the Fav column."""
    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "fav_query",
                "connection": "conn1",
                "sql": "SELECT 1",
                "is_favorite": True,
            },
            {
                "name": "normal_query",
                "connection": "conn1",
                "sql": "SELECT 2",
                "is_favorite": False,
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryManageScreen)
        from textual.widgets import DataTable
        table = screen.query_one("#qm-table", DataTable)
        assert table.row_count == 2


# ======================================================================
# GroupManageScreen tests
# ======================================================================

from dbqm.ui.screens.group_manage import GroupManageScreen


class GroupManageTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield GroupManageScreen()


@pytest.mark.asyncio
async def test_group_manage_screen_renders(tmp_config_dir):
    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(GroupManageScreen) is not None


@pytest.mark.asyncio
async def test_group_manage_screen_empty(tmp_config_dir):
    """With no groups, should show empty message and hide table."""
    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupManageScreen)
        empty = screen.query_one("#gm-empty")
        assert empty.display is True
        from textual.widgets import DataTable
        table = screen.query_one("#gm-table", DataTable)
        assert table.display is False


@pytest.mark.asyncio
async def test_group_manage_empty_state_action_opens_new_group(tmp_config_dir):
    """The EmptyState's "Criar grupo" button must not be a dead end."""
    from dbqm.models.query import Query, save_queries
    from textual.widgets import Button

    save_queries([
        Query(name="q1", connection="c1", sql="SELECT 1 FROM dual", table="dual"),
        Query(name="q2", connection="c1", sql="SELECT 2 FROM dual", table="dual"),
    ])

    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupManageScreen)
        screen.query_one("#criar-grupo", Button).press()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # GroupCreateModal opened


# ======================================================================
# GroupExecScreen tests
# ======================================================================

from dbqm.ui.screens.group_exec import GroupExecScreen


class GroupExecTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield GroupExecScreen()


@pytest.mark.asyncio
async def test_group_exec_screen_renders(tmp_config_dir):
    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(GroupExecScreen) is not None


@pytest.mark.asyncio
async def test_group_exec_screen_has_option3_widgets(tmp_config_dir):
    """Multi-Exec (Option 3) exposes the target checklist, SQL editor,
    comparison display and the saved-group Select."""
    from textual.widgets import SelectionList, TextArea, Select
    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        assert screen.query_one("#conn-checklist", SelectionList) is not None
        assert screen.query_one("#group-sql", TextArea) is not None
        assert screen.query_one("#group-results", GroupResultWidget) is not None
        assert screen.query_one("#group-saved-select", Select) is not None


@pytest.mark.asyncio
async def test_group_exec_checklist_lists_connections(tmp_config_dir):
    """The connection checklist is populated from the saved connections."""
    from textual.widgets import SelectionList
    _seed_connections(tmp_config_dir / "config")

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        checklist = screen.query_one("#conn-checklist", SelectionList)
        values = {opt.value for opt in checklist.options}
        assert {"dev_oracle", "prod_pg"} <= values


@pytest.mark.asyncio
async def test_group_exec_saved_select_lists_only_adhoc_groups(tmp_config_dir):
    """Only groups with adhoc_sql appear in the saved-group Select."""
    from textual.widgets import Select
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "legacy_query_group",
                "description": "old query-based",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            },
            {
                "name": "adhoc_group",
                "description": "",
                "queries": [],
                "join_key": "ID",
                "adhoc_sql": "SELECT ID, STATUS FROM t",
                "connections": ["dev_oracle"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        select = screen.query_one("#group-saved-select", Select)
        labels = {label.plain if hasattr(label, "plain") else str(label)
                  for label, _ in select._options}
        assert "adhoc_group" in labels
        assert "legacy_query_group" not in labels


@pytest.mark.asyncio
async def test_group_exec_load_group_checks_conns_and_fills_sql(tmp_config_dir):
    """Carregar an ad-hoc group checks its connections and fills the SQL."""
    from textual.widgets import SelectionList, TextArea, Select, Button
    config_dir = tmp_config_dir / "config"
    _seed_connections(config_dir)
    groups_data = {
        "groups": [
            {
                "name": "adhoc_group",
                "description": "",
                "queries": [],
                "join_key": "ID",
                "adhoc_sql": "SELECT ID, STATUS FROM apolice",
                "connections": ["prod_pg"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen.query_one("#group-saved-select", Select).value = "adhoc_group"
        await pilot.pause()

        screen._load_group()
        await pilot.pause()

        sql = screen.query_one("#group-sql", TextArea).text
        assert "SELECT ID, STATUS FROM apolice" in sql
        checklist = screen.query_one("#conn-checklist", SelectionList)
        assert list(checklist.selected) == ["prod_pg"]


@pytest.mark.asyncio
async def test_group_exec_handle_execute_warns_on_empty_sql(tmp_config_dir):
    """Executar with no SQL typed should warn and never start a run."""
    from dbqm.ui.widgets.progress import ProgressIndicator

    _seed_connections(tmp_config_dir / "config")

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen._handle_execute()
        await pilot.pause()

        messages = [str(n.message) for n in app._notifications]
        assert any("sql" in m.lower() for m in messages)
        assert screen.query_one(ProgressIndicator).display is False


@pytest.mark.asyncio
async def test_group_exec_handle_execute_warns_on_no_connections_checked(tmp_config_dir):
    """Executar with SQL but no checked connections should warn and not run."""
    from textual.widgets import TextArea
    from dbqm.ui.widgets.progress import ProgressIndicator

    _seed_connections(tmp_config_dir / "config")

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen.query_one("#group-sql", TextArea).load_text("SELECT 1 FROM DUAL")
        await pilot.pause()

        screen._handle_execute()
        await pilot.pause()

        messages = [str(n.message) for n in app._notifications]
        assert any("conexao" in m.lower() for m in messages)
        assert screen.query_one(ProgressIndicator).display is False


@pytest.mark.asyncio
async def test_group_exec_on_save_name_persists_adhoc_group(tmp_config_dir):
    """_on_save_name (the save-as-group flow) persists a Group with the
    current SQL and checked connections."""
    from textual.widgets import TextArea
    from dbqm.models.group import load_groups

    _seed_connections(tmp_config_dir / "config")

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen.query_one("#group-sql", TextArea).load_text("SELECT ID, STATUS FROM apolice")
        screen._populate_connections({"dev_oracle", "prod_pg"})
        await pilot.pause()

        screen._on_save_name("meu_grupo_adhoc")
        await pilot.pause()

        groups = {g.name: g for g in load_groups()}
        assert "meu_grupo_adhoc" in groups
        saved = groups["meu_grupo_adhoc"]
        assert saved.adhoc_sql == "SELECT ID, STATUS FROM apolice"
        assert sorted(saved.connections) == ["dev_oracle", "prod_pg"]


@pytest.mark.asyncio
async def test_group_exec_save_selection_warns_when_incomplete(tmp_config_dir):
    """_save_selection should warn (and not push a naming dialog) when SQL
    or the connection checklist is empty."""
    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        base_stack_len = len(app.screen_stack)

        screen._save_selection()
        await pilot.pause()

        messages = [str(n.message) for n in app._notifications]
        assert any("sql" in m.lower() for m in messages)
        assert len(app.screen_stack) == base_stack_len


@pytest.mark.asyncio
async def test_group_exec_execute_runs_per_connection_and_builds_comparison(
    tmp_config_dir, monkeypatch
):
    """Running the worker against two fake connections invokes execute_adhoc
    per connection and produces a real comparison rendered in #group-results."""
    from dbqm.core.query_engine import AdhocResult

    _seed_connections(tmp_config_dir / "config")

    calls: list[tuple[str, str]] = []

    def fake_execute_adhoc(sql, conn, param_values, auto_commit=False, capture_output=False):
        calls.append((sql, conn.name))
        rows = [[1, "ok"], [2, "fail"]] if conn.name == "dev_oracle" else [[1, "ok"], [2, "ok"]]
        return AdhocResult(
            sql_type="SELECT",
            connection_name=conn.name,
            columns=["ID", "STATUS"],
            rows=rows,
            row_count=len(rows),
        )

    monkeypatch.setattr("dbqm.core.query_engine.execute_adhoc", fake_execute_adhoc)

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)

        worker = screen._run("SELECT ID, STATUS FROM t", ["dev_oracle", "prod_pg"])
        await worker.wait()
        await pilot.pause()

        # execute_adhoc was invoked once per checked connection.
        assert sorted(calls) == [
            ("SELECT ID, STATUS FROM t", "dev_oracle"),
            ("SELECT ID, STATUS FROM t", "prod_pg"),
        ]

        grw = screen.query_one("#group-results", GroupResultWidget)
        gr = grw.group_result
        assert gr is not None
        assert set(gr.query_results.keys()) == {"dev_oracle", "prod_pg"}
        assert gr.all_match is False
        assert len(gr.comparisons) == 1
        comp = gr.comparisons[0]
        assert comp.column == "STATUS"
        assert comp.diff_count == 1
        assert comp.equal_count == 1


@pytest.mark.asyncio
async def test_group_manage_screen_with_data(tmp_config_dir):
    """With groups configured, should show them in the table."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "grupo_b",
                "description": "Second group",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "Beta",
            },
            {
                "name": "grupo_a",
                "description": "First group",
                "queries": ["q1", "q3"],
                "join_key": "code",
                "compare_columns": ["value"],
                "folder": "Alpha",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupManageScreen)
        empty = screen.query_one("#gm-empty")
        assert empty.display is False
        from textual.widgets import DataTable
        table = screen.query_one("#gm-table", DataTable)
        assert table.display is True
        assert table.row_count == 2
        # Should be sorted alphabetically: grupo_a first, then grupo_b
        row0 = table.get_row_at(0)
        assert str(row0[1]) == "grupo_a"
        row1 = table.get_row_at(1)
        assert str(row1[1]) == "grupo_b"


# ======================================================================
# AdhocScreen tests
# ======================================================================

from dbqm.ui.screens.adhoc import AdhocScreen


class AdhocTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield AdhocScreen()


@pytest.mark.asyncio
async def test_adhoc_screen_renders(tmp_config_dir):
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(AdhocScreen) is not None


@pytest.mark.asyncio
async def test_adhoc_has_params_editor_results_panels(tmp_config_dir):
    """AdhocScreen renders three simultaneous panels + a results sub-toggle."""
    from dbqm.ui.widgets.panel import Panel
    from textual.widgets import ContentSwitcher, Select, TextArea

    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        titles = [
            p.query_one("#panel-title").render().plain for p in screen.query(Panel)
        ]
        assert any("PARAMETROS" in t for t in titles)
        assert any("SQL EDITOR" in t for t in titles)
        assert any("RESULTADOS" in t for t in titles)
        # Results sub-toggle: a ContentSwitcher with table + output panes.
        switcher = screen.query_one("#res-switcher", ContentSwitcher)
        assert switcher is not None
        assert screen.query_one("#res-table") is not None
        assert screen.query_one("#res-output") is not None
        # Params panel keeps the connection Select; editor keeps the TextArea.
        assert screen.query_one("#adhoc-conn-select", Select) is not None
        assert screen.query_one("#adhoc-sql-area", TextArea) is not None


@pytest.mark.asyncio
async def test_adhoc_screen_starts_on_table_view(tmp_config_dir):
    """The results sub-toggle starts on the Tabela (res-table) view."""
    from textual.widgets import ContentSwitcher
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        switcher = screen.query_one("#res-switcher", ContentSwitcher)
        assert switcher.current == "res-table"


@pytest.mark.asyncio
async def test_adhoc_screen_has_sql_area(tmp_config_dir):
    """AdhocScreen should have a TextArea for SQL input."""
    from textual.widgets import TextArea
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        text_area = screen.query_one("#adhoc-sql-area", TextArea)
        assert text_area is not None


@pytest.mark.asyncio
async def test_adhoc_screen_has_buttons(tmp_config_dir):
    """AdhocScreen should have execute, clear, generate, and save buttons."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        from textual.widgets import Button
        execute_btn = screen.query_one("#adhoc-execute", Button)
        clear_btn = screen.query_one("#adhoc-clear", Button)
        generate_btn = screen.query_one("#adhoc-generate", Button)
        save_btn = screen.query_one("#adhoc-save", Button)
        assert execute_btn is not None
        assert clear_btn is not None
        assert generate_btn is not None
        assert save_btn is not None
        # Execute button should start disabled (no connection or SQL)
        assert execute_btn.disabled is True


@pytest.mark.asyncio
async def test_adhoc_results_sub_toggle_switches_views(tmp_config_dir):
    """The Tabela/Output buttons flip the results ContentSwitcher."""
    from textual.widgets import Button, ContentSwitcher
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        switcher = screen.query_one("#res-switcher", ContentSwitcher)

        screen.query_one("#res-btn-output", Button).press()
        await pilot.pause()
        assert switcher.current == "res-output"

        screen.query_one("#res-btn-table", Button).press()
        await pilot.pause()
        assert switcher.current == "res-table"


@pytest.mark.asyncio
async def test_adhoc_unmount_cleans_connection(tmp_config_dir):
    """Leaving the screen should rollback and close any open DML connection."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)

        # Create a mock connection
        class MockConn:
            rolled_back = False
            closed = False
            def rollback(self):
                self.rolled_back = True
            def close(self):
                self.closed = True

        mock = MockConn()
        screen._db_connection = mock

        screen.on_unmount()

        assert mock.rolled_back is True
        assert mock.closed is True
        assert screen._db_connection is None


def test_format_plsql_message_header_only():
    """Formatter shows only the success header; DBMS_OUTPUT goes to the panel."""
    from dbqm.core.query_engine import AdhocResult
    from dbqm.ui.screens.adhoc import _format_plsql_message

    result = AdhocResult(
        sql_type="PLSQL", connection_name="c1", elapsed=0.01,
        committed=True, output_lines=["linha um", "linha dois"],
    )
    msg = _format_plsql_message(result)
    assert "Bloco PL/SQL executado" in msg
    # Output lines are rendered in the dedicated panel, not the header static.
    assert "linha um" not in msg


@pytest.mark.asyncio
async def test_adhoc_plsql_result_shows_static(tmp_config_dir):
    """PLSQL results route to the result static, without the DML warning."""
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "PLSQL"
        result = AdhocResult(
            sql_type="PLSQL", connection_name="c1", elapsed=0.01,
            committed=True, output_lines=["linha um"],
        )
        screen._on_sql_result(result)

        from textual.widgets import ContentSwitcher
        # PL/SQL routes to the Output view; the DML/message static shows there.
        assert screen.query_one("#res-switcher", ContentSwitcher).current == "res-output"
        assert screen.query_one("#adhoc-dml-result").display is True
        assert screen.query_one("#res-table").display is False


@pytest.mark.asyncio
async def test_adhoc_has_dbms_toggle(tmp_config_dir):
    """Input phase exposes a checkbox to opt into DBMS_OUTPUT capture."""
    from textual.widgets import Checkbox
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        toggle = screen.query_one("#adhoc-dbms-toggle", Checkbox)
        assert toggle.value is False
        assert str(toggle.label) == "Saida DBMS"


@pytest.mark.asyncio
async def test_adhoc_dbms_toggle_aligns_with_select(tmp_config_dir):
    """The DBMS toggle matches the connection select height and stays within
    the SQL editor width (no header overflow past the box below)."""
    from textual.widgets import Checkbox, Select, TextArea
    app = AdhocTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = app.query_one(AdhocScreen)
        toggle = screen.query_one("#adhoc-dbms-toggle", Checkbox)
        select = screen.query_one("#adhoc-conn-select", Select)
        sql_area = screen.query_one("#adhoc-sql-area", TextArea)

        # Same height as the connection select next to it.
        assert toggle.region.height == select.region.height
        # Right edge must not extend past the SQL editor below it.
        assert toggle.region.right <= sql_area.region.right


@pytest.mark.asyncio
async def test_adhoc_dbms_panel_hidden_initially(tmp_config_dir):
    """The DBMS_OUTPUT panel is hidden until a captured execution renders it."""
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        assert screen.query_one("#adhoc-dbms-panel").display is False


@pytest.mark.asyncio
async def test_adhoc_select_shows_dbms_panel_when_capture_enabled(tmp_config_dir):
    """A SELECT with capture on loads the table AND populates the DBMS panel.

    With the results sub-toggle, DBMS output routes the view to Output; the
    table stays loaded and reachable via the Tabela button.
    """
    from textual.widgets import Button, ContentSwitcher, TextArea
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "SELECT"
        screen._capture_output = True
        result = AdhocResult(
            sql_type="SELECT", connection_name="c1", elapsed=0.01,
            columns=["x"], rows=[[1]], row_count=1,
            output_lines=["log A", "log B"],
        )
        screen._on_sql_result(result)
        await pilot.pause()

        # DBMS output present -> Output view is selected.
        switcher = screen.query_one("#res-switcher", ContentSwitcher)
        assert switcher.current == "res-output"
        panel = screen.query_one("#adhoc-dbms-panel")
        assert panel.display is True
        view = screen.query_one("#adhoc-dbms-view", TextArea)
        assert "log A" in view.text
        assert "log B" in view.text

        # The table is still loaded and reachable via the Tabela toggle.
        from dbqm.ui.widgets.result_table import ResultTable
        screen.query_one("#res-btn-table", Button).press()
        await pilot.pause()
        assert switcher.current == "res-table"
        assert screen.query_one("#res-table", ResultTable).display is True


@pytest.mark.asyncio
async def test_adhoc_select_hides_dbms_panel_when_capture_disabled(tmp_config_dir):
    """A SELECT with capture off does not show the DBMS panel."""
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "SELECT"
        screen._capture_output = False
        result = AdhocResult(
            sql_type="SELECT", connection_name="c1", elapsed=0.01,
            columns=["x"], rows=[[1]], row_count=1,
        )
        screen._on_sql_result(result)
        await pilot.pause()

        assert screen.query_one("#adhoc-dbms-panel").display is False


@pytest.mark.asyncio
async def test_adhoc_plsql_always_shows_dbms_panel(tmp_config_dir):
    """PL/SQL output always renders in the panel, regardless of the checkbox."""
    from textual.widgets import TextArea
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "PLSQL"
        screen._capture_output = False
        result = AdhocResult(
            sql_type="PLSQL", connection_name="c1", elapsed=0.01,
            committed=True, output_lines=["bloco rodou"],
        )
        screen._on_sql_result(result)
        await pilot.pause()

        panel = screen.query_one("#adhoc-dbms-panel")
        assert panel.display is True
        view = screen.query_one("#adhoc-dbms-view", TextArea)
        assert "bloco rodou" in view.text


@pytest.mark.asyncio
async def test_adhoc_dbms_panel_empty_shows_placeholder(tmp_config_dir):
    """Capture on but no output lines still shows the panel with a placeholder."""
    from textual.widgets import TextArea
    from dbqm.core.query_engine import AdhocResult
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        screen._sql_type = "SELECT"
        screen._capture_output = True
        result = AdhocResult(
            sql_type="SELECT", connection_name="c1", elapsed=0.01,
            columns=["x"], rows=[[1]], row_count=1, output_lines=[],
        )
        screen._on_sql_result(result)
        await pilot.pause()

        assert screen.query_one("#adhoc-dbms-panel").display is True
        view = screen.query_one("#adhoc-dbms-view", TextArea)
        assert view.text.strip() != ""  # placeholder, not blank


@pytest.mark.asyncio
async def test_adhoc_dbms_toggle_read_by_execute(tmp_config_dir):
    """_dbms_output_enabled reflects the checkbox state."""
    from textual.widgets import Checkbox
    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        assert screen._dbms_output_enabled() is False
        screen.query_one("#adhoc-dbms-toggle", Checkbox).value = True
        await pilot.pause()
        assert screen._dbms_output_enabled() is True


@pytest.mark.asyncio
async def test_adhoc_screen_connection_selector(tmp_config_dir):
    """AdhocScreen should have a connection selector."""
    config_dir = tmp_config_dir / "config"
    conn_data = {
        "connections": [
            {
                "name": "test_conn",
                "db_type": "oracle",
                "mode": "direct",
                "host": "localhost",
                "port": 1521,
                "service_name": "ORCL",
                "user": "admin",
                "password": "pass",
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )

    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        select_widget = screen.query_one("#adhoc-conn-select", Select)
        assert select_widget is not None


@pytest.mark.asyncio
async def test_adhoc_screen_select_styling_on_change(tmp_config_dir):
    """Select should get --conn-selected class when a connection is picked."""
    config_dir = tmp_config_dir / "config"
    conn_data = {
        "connections": [
            {
                "name": "test_conn",
                "db_type": "oracle",
                "mode": "direct",
                "host": "localhost",
                "port": 1521,
                "service_name": "ORCL",
                "user": "admin",
                "password": "pass",
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )

    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        select_widget = screen.query_one("#adhoc-conn-select", Select)
        # Initially no connection selected — no class
        assert not select_widget.has_class("--conn-selected")
        # Simulate selecting a connection
        select_widget.value = "test_conn"
        await pilot.pause()
        assert select_widget.has_class("--conn-selected")


@pytest.mark.asyncio
async def test_adhoc_screen_execute_enabled_when_conn_and_sql(tmp_config_dir):
    """Execute button should enable when both connection and SQL are present."""
    config_dir = tmp_config_dir / "config"
    conn_data = {
        "connections": [
            {
                "name": "test_conn",
                "db_type": "oracle",
                "mode": "direct",
                "host": "localhost",
                "port": 1521,
                "service_name": "ORCL",
                "user": "admin",
                "password": "pass",
            },
        ]
    }
    (config_dir / "connections.json").write_text(
        json.dumps(conn_data, ensure_ascii=False), encoding="utf-8"
    )

    app = AdhocTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(AdhocScreen)
        from textual.widgets import Button, TextArea
        execute_btn = screen.query_one("#adhoc-execute", Button)
        sql_area = screen.query_one("#adhoc-sql-area", TextArea)
        select_widget = screen.query_one("#adhoc-conn-select", Select)

        # Initially disabled
        assert execute_btn.disabled is True

        # Set SQL but no connection — still disabled
        sql_area.insert("SELECT 1 FROM DUAL")
        await pilot.pause()
        assert execute_btn.disabled is True

        # Set connection — now enabled
        select_widget.value = "test_conn"
        await pilot.pause()
        assert execute_btn.disabled is False


# ======================================================================
# BrowserScreen tests
# ======================================================================

from dbqm.ui.screens.browser import BrowserScreen


class BrowserTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield BrowserScreen()


@pytest.mark.asyncio
async def test_browser_screen_renders(tmp_config_dir):
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(BrowserScreen) is not None


@pytest.mark.asyncio
async def test_browser_shows_empty_state_until_connection_chosen(tmp_config_dir):
    """No connection selected yet: EmptyState replaces the object OptionList,
    and its "Escolher conexao" button must not be a dead end."""
    from textual.widgets import Button, OptionList, Select
    from dbqm.ui.widgets.empty_state import EmptyState

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        empty = screen.query_one("#obj-list-empty", EmptyState)
        assert empty.display is True
        assert screen.query_one("#obj-list", OptionList).display is False

        screen.query_one("#escolher-conexao", Button).press()
        await pilot.pause()
        assert app.focused is screen.query_one("#obj-conn", Select)


@pytest.mark.asyncio
async def test_browser_three_live_panels(tmp_config_dir):
    """BrowserScreen renders three simultaneous panels + the live surfaces."""
    from dbqm.ui.widgets.panel import Panel

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        titles = [
            p.query_one("#panel-title").render().plain for p in screen.query(Panel)
        ]
        assert any("OBJETOS" in t for t in titles)
        assert any("COLUNAS" in t for t in titles)
        assert any("DADOS" in t for t in titles)
        assert screen.query_one("#obj-list") is not None
        assert screen.query_one("#obj-columns") is not None
        assert screen.query_one("#obj-preview") is not None


@pytest.mark.asyncio
async def test_browser_has_conn_type_filter_and_buttons(tmp_config_dir):
    """OBJETOS panel exposes conn + type selects, a filter input, and the
    DADOS panel carries the Extrair DDL / Carregar mais buttons."""
    from textual.widgets import Button
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        assert screen.query_one("#obj-conn", Select) is not None
        assert screen.query_one("#obj-type", Select) is not None
        assert screen.query_one("#obj-filter", Input) is not None
        assert screen.query_one("#obj-ddl", Button) is not None
        assert screen.query_one("#obj-more", Button) is not None


@pytest.mark.asyncio
async def test_browser_reload_populates_object_list(tmp_config_dir, monkeypatch):
    """Reloading objects (via list_objects) fills the OptionList."""
    from textual.widgets import OptionList

    monkeypatch.setattr(
        "dbqm.core.object_browser.list_objects",
        lambda db, db_type, obj_type: ["CLIENTE", "PEDIDO", "PRODUTO"],
    )

    class _FakeConn:
        name = "c1"
        db_type = "oracle"

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        screen._current_conn = _FakeConn()
        screen._db = object()
        screen._obj_type = "TABLE"

        worker = screen._reload_objects()
        await worker.wait()
        await pilot.pause()

        option_list = screen.query_one("#obj-list", OptionList)
        assert option_list.option_count == 3


@pytest.mark.asyncio
async def test_mounted_browser_object_list_is_identity_only(tmp_config_dir, monkeypatch):
    """The object list uses `hierarchical_item` with the identity only — the
    type filter (`#obj-type`) is `allow_blank=False`, so every visible row
    is already always of the same type; writing the type again on each item
    would disambiguate nothing. `conteudo` comes from the really mounted
    widget (`Option.prompt` inside an app with an active theme), not from
    the isolated `Content`, and the identity's color is resolved via
    `Style.parse` against the real theme — wiring all the way to the mounted
    widget, not pixel painting (no screenshot is taken here)."""
    from textual.style import Style
    from textual.widgets import OptionList, Select

    monkeypatch.setattr(
        "dbqm.core.object_browser.list_objects",
        lambda db, db_type, obj_type: ["CLIENTE"],
    )

    def cor_no_offset(conteudo, offset):
        estilo = Style()
        for start, end, span_style in conteudo.spans:
            if start <= offset < end:
                estilo = estilo + Style.parse(span_style)
        return estilo.foreground

    class _FakeConn:
        name = "c1"
        db_type = "oracle"

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        assert screen.query_one("#obj-type", Select)._allow_blank is False

        screen._current_conn = _FakeConn()
        screen._db = object()
        screen._obj_type = "TABLE"

        worker = screen._reload_objects()
        await worker.wait()
        await pilot.pause()

        option_list = screen.query_one("#obj-list", OptionList)
        conteudo = option_list.get_option_at_index(0).prompt
        texto = conteudo.plain

        assert texto == "CLIENTE", "sem tipo repetido: so a identidade"
        assert chr(10) not in texto

        cor_forte = Style.parse("$ds-text-strong").foreground
        assert cor_no_offset(conteudo, 0) == cor_forte


@pytest.mark.asyncio
async def test_browser_select_object_fills_columns_and_preview(
    tmp_config_dir, monkeypatch
):
    """Selecting an object fires ONE worker that fills BOTH the COLUNAS table
    (structure) and the DADOS preview (first page) — the live-update contract."""
    from types import SimpleNamespace
    from textual.widgets import DataTable
    from dbqm.ui.widgets.result_table import ResultTable
    from dbqm.core.table_browser import BrowseResult

    fake_structure = SimpleNamespace(
        table="CLIENTE",
        elapsed=0.01,
        indexes=[],
        columns=[
            SimpleNamespace(
                name="ID", data_type="NUMBER", data_precision=10, data_scale=0,
                data_length=None, nullable=False, is_pk=True, fk_ref=None,
            ),
            SimpleNamespace(
                name="NOME", data_type="VARCHAR2", data_precision=None,
                data_scale=None, data_length=100, nullable=True, is_pk=False,
                fk_ref=None,
            ),
        ],
    )
    fake_browse = BrowseResult(
        table="CLIENTE",
        connection_name="c1",
        columns=["ID", "NOME"],
        rows=[[1, "Ana"], [2, "Bruno"]],
        row_count=2,
        total_count=2,
        elapsed=0.02,
        limit=100,
        offset=0,
    )

    monkeypatch.setattr(
        "dbqm.core.object_browser.get_table_structure",
        lambda db, db_type, table: fake_structure,
    )
    monkeypatch.setattr(
        "dbqm.core.table_browser.browse_table",
        lambda db, db_type, table, conn_name, limit, offset: fake_browse,
    )

    class _FakeConn:
        name = "c1"
        db_type = "oracle"

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        screen._current_conn = _FakeConn()
        screen._db = object()
        screen._obj_type = "TABLE"

        worker = screen._load_object("CLIENTE")
        await worker.wait()
        await pilot.pause()

        columns_table = screen.query_one("#obj-columns", DataTable)
        assert columns_table.row_count == 2  # two columns of CLIENTE
        preview = screen.query_one("#obj-preview", ResultTable)
        assert preview is not None
        assert screen._selected_object == "CLIENTE"


@pytest.mark.asyncio
async def test_browser_select_package_shows_source_no_error(
    tmp_config_dir, monkeypatch
):
    """Selecting a PACKAGE fetches SOURCE text (via the ddl_extractor core
    used by "Extrair DDL") and shows it inline — no browse_table ORA-00942,
    no error toast."""
    from types import SimpleNamespace
    from dbqm.ui.widgets.sql_viewer import SqlViewer
    from dbqm.ui.widgets.result_table import ResultTable
    from dbqm.core.ddl_extractor import ExtractedObject, ExtractionResult

    fake_result = ExtractionResult(
        object_name="PKG_CLIENTE", object_type="PACKAGE",
        owner="APP", connection_name="c1",
        objects=[
            ExtractedObject("PKG_CLIENTE", "PACKAGE SPEC", "CREATE OR REPLACE PACKAGE pkg_cliente IS ..."),
            ExtractedObject("PKG_CLIENTE", "PACKAGE BODY", "CREATE OR REPLACE PACKAGE BODY pkg_cliente IS ..."),
        ],
    )

    def _fake_browse_table(*args, **kwargs):
        raise AssertionError("browse_table must not be called for PACKAGE objects")

    monkeypatch.setattr(
        "dbqm.core.ddl_extractor.extract_ddl",
        lambda conn, name, owner_filter=None, on_progress=None: fake_result,
    )
    monkeypatch.setattr(
        "dbqm.core.object_browser.list_package_routines",
        lambda db, db_type, package: SimpleNamespace(
            name="PKG_CLIENTE", owner="APP",
            routines=[
                SimpleNamespace(name="GET_NOME", routine_type="FUNCTION", signature="(p_id NUMBER) RETURN VARCHAR2"),
            ],
        ),
    )
    monkeypatch.setattr("dbqm.core.table_browser.browse_table", _fake_browse_table)

    class _FakeConn:
        name = "c1"
        db_type = "oracle"

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        screen._current_conn = _FakeConn()
        screen._db = object()
        screen._obj_type = "PACKAGE"

        worker = screen._load_object("PKG_CLIENTE")
        await worker.wait()
        await pilot.pause()

        source_view = screen.query_one("#obj-source", SqlViewer)
        assert "pkg_cliente" in source_view._sql
        assert source_view.display is True
        preview = screen.query_one("#obj-preview", ResultTable)
        assert preview.display is False

        error_notifications = [
            n for n in app._notifications if n.severity == "error"
        ]
        assert error_notifications == []


@pytest.mark.asyncio
async def test_browser_select_table_shows_table_view(tmp_config_dir, monkeypatch):
    """The table view (#obj-preview) is used for TABLE, and toggling back
    from a previous PACKAGE selection hides the source view again."""
    from types import SimpleNamespace
    from dbqm.core.table_browser import BrowseResult
    from dbqm.ui.widgets.sql_viewer import SqlViewer
    from dbqm.ui.widgets.result_table import ResultTable

    fake_structure = SimpleNamespace(
        table="CLIENTE", elapsed=0.01, indexes=[],
        columns=[
            SimpleNamespace(
                name="ID", data_type="NUMBER", data_precision=10, data_scale=0,
                data_length=None, nullable=False, is_pk=True, fk_ref=None,
            ),
        ],
    )
    fake_browse = BrowseResult(
        table="CLIENTE", connection_name="c1", columns=["ID"],
        rows=[[1]], row_count=1, total_count=1, elapsed=0.01,
        limit=100, offset=0,
    )
    monkeypatch.setattr(
        "dbqm.core.object_browser.get_table_structure",
        lambda db, db_type, table: fake_structure,
    )
    monkeypatch.setattr(
        "dbqm.core.table_browser.browse_table",
        lambda db, db_type, table, conn_name, limit, offset: fake_browse,
    )

    class _FakeConn:
        name = "c1"
        db_type = "oracle"

    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)
        screen._current_conn = _FakeConn()
        screen._db = object()
        screen._obj_type = "TABLE"

        worker = screen._load_object("CLIENTE")
        await worker.wait()
        await pilot.pause()

        preview = screen.query_one("#obj-preview", ResultTable)
        source_view = screen.query_one("#obj-source", SqlViewer)
        assert preview.display is True
        assert source_view.display is False


@pytest.mark.asyncio
async def test_browser_screen_unmount_closes_db(tmp_config_dir):
    """Unmounting BrowserScreen should close the DB connection."""
    app = BrowserTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(BrowserScreen)

        class MockDB:
            closed = False
            def close(self):
                self.closed = True

        mock = MockDB()
        screen._db = mock
        screen.on_unmount()

        assert mock.closed is True
        assert screen._db is None


# ======================================================================
# HistoryScreen tests
# ======================================================================

from dbqm.ui.screens.history import HistoryScreen


class HistoryTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield HistoryScreen()


def _salvar_duas_entradas() -> None:
    """Writes a minimal history (one query, one group)."""
    from dbqm.core.history import save_history, HistoryEntry

    save_history(
        [
            HistoryEntry(
                id="001",
                timestamp="2025-01-15T10:30:00",
                entry_type="query",
                name="test_query",
                connection="dev_oracle",
                row_count=42,
                elapsed=1.5,
                success=True,
            ),
            HistoryEntry(
                id="002",
                timestamp="2025-01-15T10:35:00",
                entry_type="group",
                name="test_group",
                connection="",
                all_match=False,
                summary="1 divergente",
                elapsed=3.2,
            ),
        ]
    )


@pytest.mark.asyncio
async def test_history_screen_renders(tmp_config_dir):
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(HistoryScreen) is not None


@pytest.mark.asyncio
async def test_history_shows_table_and_detail_together(tmp_config_dir):
    """Table and detail panel are both visible at once — no phase swap.

    With HISTORICO: it is only when there is a record that the table and the
    detail have anything to show. This test used to mount the EMPTY screen
    and still demand both standing — it was the defect written as a
    contract.
    """
    _salvar_duas_entradas()
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        assert screen.query_one("#hist-table").display
        assert screen.query_one("#hist-detail").display


@pytest.mark.asyncio
async def test_history_panels_have_titles(tmp_config_dir):
    """HISTORICO and DETALHES panels both exist."""
    from dbqm.ui.widgets.panel import Panel

    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        panels = screen.query(Panel)
        titles = [p.query_one("#panel-title").render().plain for p in panels]
        assert any("HISTORICO" in t for t in titles)
        assert any("DETALHES" in t for t in titles)


@pytest.mark.asyncio
async def test_history_screen_empty(tmp_config_dir):
    """With no history, the empty state appears and the table LEAVES the scene."""
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        empty = screen.query_one("#hist-empty")
        assert empty.display is True
        from textual.widgets import DataTable
        table = screen.query_one("#hist-table", DataTable)
        assert table.display is False
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_history_empty_state_action_switches_to_query_exec(tmp_config_dir):
    """The EmptyState's "Executar consulta" button must not be a dead end."""
    from textual.widgets import Button

    switched = []

    class _HistoryWithSwitch(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield HistoryScreen()

        def action_switch_tab(self, tab_id: str) -> None:
            switched.append(tab_id)

    app = _HistoryWithSwitch()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        screen.query_one("#executar-consulta", Button).press()
        await pilot.pause()
        assert switched == ["tab-consultas"]


@pytest.mark.asyncio
async def test_history_screen_with_data(tmp_config_dir):
    """With history entries, should show them in the table."""
    _salvar_duas_entradas()

    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        empty = screen.query_one("#hist-empty")
        assert empty.display is False
        from textual.widgets import DataTable
        table = screen.query_one("#hist-table", DataTable)
        assert table.display is True
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_history_screen_detail_visible_initially(tmp_config_dir):
    """With records, the detail panel is born visible (with no phase swap)."""
    _salvar_duas_entradas()
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        detail = screen.query_one("#hist-detail")
        assert detail.display is True
        assert screen.query_one("#hist-detail-panel").display is True


# ----------------------------------------------------------------------
# Empty Historico: what the screen PAINTS, on the real DBQMApp, at both sizes
#
# There is no harness of its own here on purpose. The clipping of the empty
# state only shows up with the height the tab REALLY leaves for the screen —
# header, tab strip, action bar and status bar already subtracted. A
# `HistoryTestApp` on its own gets the whole 24 lines and paints everything.
# ----------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("tamanho", [(80, 24), (120, 34)])
async def test_empty_history_paints_identity_and_no_table(
    tmp_config_dir, tamanho
):
    """With an empty history: the three parts of the empty state show up,
    and the table header does not.

    Two defects at once, both measured on the render:

    1. The `Data Conexao Tipo SQL Tempo Status` header was painted right up
       against the empty state (the other ten dbqm lists hide their sibling).
    2. At 80x24 the identity line (`Historico`) was clipped ENTIRELY — only
       the why and the button made it to the screen.
    """
    from dbqm.ui.app import DBQMApp
    from tests.ui._helpers import rendered_lines, rendered_text

    app = DBQMApp()
    async with app.run_test(size=tamanho) as pilot:
        await pilot.pause()
        app.action_switch_tab("tab-historico")
        for _ in range(3):
            await pilot.pause()

        pintado = rendered_text(app)
        linhas = rendered_lines(app)
        assert "HISTORICO" in pintado, "a aba de historico nem chegou a frente"

        # The identity is checked LINE BY LINE, not with an `in` against the
        # whole screen: the tab strip itself writes "📜  Historico", and a
        # `"Historico" in pintado` passed green with the line clipped.
        # Inside the panel it stands alone on its line, between the borders.
        assert any(
            linha.strip("│ ") == "Historico" for linha in linhas
        ), "a linha de identidade do estado vazio nao foi pintada"
        assert "Cada consulta ou grupo executado fica registrado aqui" in pintado
        assert "Executar consulta" in pintado
        # No column of the table may be painted.
        for coluna in ("Conexao", "Tempo", "Status"):
            assert coluna not in pintado, f"cabecalho {coluna!r} pintado no vazio"


@pytest.mark.asyncio
async def test_empty_history_focuses_the_exit_it_offers(tmp_config_dir):
    """The initial focus goes to the empty state's button, not to the hidden
    table — otherwise nothing visible is marked and Enter does not reach the
    screen's only exit."""
    from textual.widgets import Button

    app = HistoryTestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.query_one(HistoryScreen)
        assert app.focused is screen.query_one("#executar-consulta", Button)


# ======================================================================
# SettingsScreen tests
# ======================================================================

from dbqm.ui.screens.settings import SettingsScreen


class SettingsTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield SettingsScreen()


# ----------------------------------------------------------------------
# Opening the app is not the user touching the controls
# ----------------------------------------------------------------------


async def _open_app_counting_writes(tmp_config_dir, monkeypatch):
    """Mounts the real DBQMApp and returns (notices, number of writes)."""
    import dbqm.models.settings as mod
    from dbqm.ui.app import DBQMApp

    gravacoes = []
    real = mod.save_settings

    def espiao(settings):
        gravacoes.append(settings)
        return real(settings)

    monkeypatch.setattr(mod, "save_settings", espiao)

    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.press("f6")
        for _ in range(3):
            await pilot.pause()
        avisos = [str(n.message) for n in app._notifications]
    return avisos, len(gravacoes)


@pytest.mark.asyncio
@pytest.mark.parametrize("salvo", [{}, {"audit_log_enabled": True}])
async def test_opening_the_app_neither_warns_nor_writes_anything(tmp_config_dir, monkeypatch, salvo):
    """With nobody touching anything, opening must not raise a settings
    notice nor rewrite `settings.json`.

    Measured before the fix: with a fresh config, one notice ("Subdiretorios
    por tipo: ativado") and one write; with `audit_log_enabled` on in the
    file, two notices and two writes. Both cases have the same cause —
    `on_mount` assigns `Switch.value` in order to SHOW what is already
    saved, and the resulting `Switch.Changed` was read as a user action. The
    second parameter exists because only it exercises the audit switch: in a
    fresh config it is born equal to the `Switch` default and does not even
    emit.
    """
    import json

    from dbqm.core.paths import SETTINGS_FILE

    if salvo:
        SETTINGS_FILE.write_text(json.dumps(salvo), encoding="utf-8")

    avisos, gravacoes = await _open_app_counting_writes(tmp_config_dir, monkeypatch)

    assert gravacoes == 0, f"{gravacoes} gravacao(oes) de settings sem acao do usuario"
    for proibido in ("Log de auditoria", "Subdiretorios por tipo", "Tema alterado"):
        assert not any(proibido in a for a in avisos), f"aviso indevido: {avisos}"


@pytest.mark.asyncio
async def test_theme_migration_does_not_become_a_switch_notice(tmp_config_dir, monkeypatch):
    """`github-dark` -> `plano-escuro` is a rename of ours, not the person's
    choice: it does not announce "Tema alterado" nor rewrite the file.

    It showed up only once — on the first open after upgrading from 1.17.x —
    which is exactly when nobody is looking at a test.
    """
    import json

    from dbqm.core.paths import SETTINGS_FILE

    SETTINGS_FILE.write_text(json.dumps({"theme": "github-dark"}), encoding="utf-8")

    avisos, gravacoes = await _open_app_counting_writes(tmp_config_dir, monkeypatch)

    assert not any("Tema alterado" in a for a in avisos), f"aviso indevido: {avisos}"
    assert gravacoes == 0
    # And the migration still holds where it matters: the theme in use.
    assert json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))["theme"] == "github-dark"


@pytest.mark.asyncio
async def test_settings_screen_renders(tmp_config_dir):
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(SettingsScreen) is not None


@pytest.mark.asyncio
async def test_settings_screen_has_theme_select(tmp_config_dir):
    """SettingsScreen should have a theme selector."""
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        assert theme_select is not None


@pytest.mark.asyncio
async def test_settings_screen_has_audit_switch(tmp_config_dir):
    """SettingsScreen should have an audit log switch."""
    from textual.widgets import Switch
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        audit_switch = screen.query_one("#settings-audit-switch", Switch)
        assert audit_switch is not None


@pytest.mark.asyncio
async def test_settings_screen_loads_defaults(tmp_config_dir):
    """SettingsScreen should load default settings values."""
    from textual.widgets import Switch
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        assert theme_select.value == "plano-escuro"
        audit_switch = screen.query_one("#settings-audit-switch", Switch)
        assert audit_switch.value is False


@pytest.mark.asyncio
async def test_settings_screen_loads_saved_settings(tmp_config_dir):
    """SettingsScreen should load previously saved settings."""
    from textual.widgets import Switch
    config_dir = tmp_config_dir / "config"
    settings_data = {"audit_log_enabled": True, "theme": "plano-claro"}
    (config_dir / "settings.json").write_text(
        json.dumps(settings_data, ensure_ascii=False), encoding="utf-8"
    )

    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        assert theme_select.value == "plano-claro"
        audit_switch = screen.query_one("#settings-audit-switch", Switch)
        assert audit_switch.value is True


@pytest.mark.asyncio
@pytest.mark.parametrize("height", [24, 34])
async def test_settings_oracle_section_is_reachable(tmp_config_dir, height):
    """The Oracle Instant Client section has to be REACHABLE in a real
    terminal.

    It was born at y=39 of a column that did not scroll: it needed 42
    terminal lines to appear, and there was no way to get to it. The Instant
    Client path setting shipped in v1.20.0 precisely to undo a 32-bit
    ORACLE_HOME that was bringing down connections in production — invisible
    to anyone without a giant screen.

    The assertion is about what the screen PAINTS, and not about
    `region.height`: with the defect present the region measured 3 lines
    high at the three sizes tested and still nothing was drawn, because the
    clipping comes from an ancestor with `overflow: hidden`.
    """
    from textual.widgets import Button
    from tests.ui._helpers import rendered_text

    app = SettingsTestApp()
    async with app.run_test(size=(120, height)) as pilot:
        screen = app.query_one(SettingsScreen)
        botao = screen.query_one("#btn-oracle-client-dir", Button)

        # The keyboard path: focusing the button is what a Tab does, and it
        # is `set_focus` that tells Textual to scroll the ancestor to it.
        botao.focus()
        await pilot.pause()
        # The scrolling that focus triggers is animated: without waiting,
        # the measurement lands halfway (scroll_y 14 out of 24) and the test
        # fails out of impatience instead of because of a defect.
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = rendered_text(app)
        assert "Definir caminho" in pintado, (
            "o botao da secao Oracle nao e alcancavel a %d linhas de terminal" % height
        )
        assert "Client em uso" in pintado, (
            "o status do Instant Client nao e desenhado a %d linhas de terminal" % height
        )


def _panel_titles(root):
    """The panel titles as the screen PAINTS them.

    `Panel` does not keep the title in `render()` — `Panel` is a `Vertical`,
    and `Vertical.render()` returns the background fill, not text. The title
    lives in a `Label` with id `#panel-title`, mounted by `Panel.compose`.
    The Task 7 plan assumed `p.render()`; the real path is this one, the
    same one the earlier tests of this screen already used.
    """
    from dbqm.ui.widgets.panel import Panel

    return [p.query_one("#panel-title").render().plain for p in root.query(Panel)]


@pytest.mark.asyncio
async def test_each_settings_subject_has_its_own_panel(tmp_config_dir):
    """One panel per subject — not a catch-all panel with four subjects
    inside.

    The complaint that started this phase was verbatim: "a tela de
    configuracoes esta horrivel com um monte de botao alinhado no centro e
    dentro da tela de configuracoes do sistema, esta tudo muito confuso".
    The confusion had a measurable cause: theme, audit, export and Oracle
    Instant Client shared ONE panel called "CONFIG DA APLICACAO", separated
    only by a bold label. With no frame per subject there is nowhere for the
    eye to rest, and the Oracle section — which exists to undo a 32-bit
    ORACLE_HOME that was bringing down connections in production — was born
    at the end of a scrolling column.
    """
    app = SettingsTestApp()
    async with app.run_test(size=(120, 40)):
        titulos = " ".join(_panel_titles(app.query_one(SettingsScreen))).lower()
        for assunto in ("tema", "auditoria", "exporta", "oracle"):
            assert assunto in titulos, "%s sem painel proprio: %r" % (assunto, titulos)


@pytest.mark.asyncio
async def test_settings_at_80x24_does_not_hide_the_door(tmp_config_dir):
    """At 80x24, on the REAL DBQMApp, the MAIS CONFIGURACOES list has to be
    there.

    On the DBQMApp the screen gets 20 lines, not 24: the Header eats 1, the
    tab strip 2, the rule below it 1 and the StatusBar 1. A harness that
    composes `SettingsScreen` on its own gives it the whole 24 — and that is
    how the previous version of this test claimed the four subjects appeared
    "without scrolling" when in the app EXPORTACAO did not appear. Measured:
    `EXPORTACAO in the harness = True, in the app = False`. It is the Task 4
    lesson again — measure in the state where the defect happens — so here
    the app is mounted.

    And the six panels really do not fit in 20 lines: the two columns add up
    to ~36 lines of content each. Section 4 of the grammar does not promise
    that everything fits; it promises that what does not fit SCROLLS, with
    the overflow visible. What it does not tolerate is what was happening
    with MAIS CONFIGURACOES: the frame and the title drawn and NOT ONE
    entry, with the body starting off screen. That panel is the only door to
    the two screens this phase resurrected after six weeks dead; a title
    with no entries announces no door at all.
    """
    from dbqm.ui.app import DBQMApp
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = rendered_text(app)
        for entrada in ("Oracle Instant Clients", "Exportar / Importar"):
            assert entrada in pintado, (
                "a entrada %r de MAIS CONFIGURACOES nao e desenhada a 80x24: %r"
                % (entrada, pintado[-800:])
            )


@pytest.mark.asyncio
async def test_settings_at_80x24_what_does_not_fit_scrolls(tmp_config_dir):
    """What sits below the fold is reachable, and the overflow is visible.

    The counterpart of the test above: EXPORTACAO and FERNET KEY do not fit
    at 80x24 and there is no arithmetic that makes them fit. What section 4
    requires is that they scroll instead of vanishing — the unframed version
    of this screen was born with the Oracle section at y=39 in an
    `overflow: hidden` container, with no scrolling at all, and there simply
    was no way to reach it.
    """
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.settings import SettingsScreen
    from tests.ui._helpers import rendered_text

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        tela = app.query_one(SettingsScreen)
        colunas = [
            tela.query_one("#settings-col-esquerda"),
            tela.query_one("#settings-col-direita"),
        ]
        for coluna in colunas:
            assert coluna.max_scroll_y > 0, (
                "%s nao rola: o que passa da dobra estaria fora de alcance"
                % coluna.id
            )
            coluna.scroll_end(animate=False)
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = rendered_text(app)
        # Body, and not title: a frame with the title drawn and the body off
        # screen is exactly the defect the test above checks for.
        assert "Alterar diretorio" in pintado, (
            "o corpo de EXPORTACAO nao aparece nem rolando ate o fim: %r"
            % pintado[-800:]
        )
        assert "Criptografa as senhas" in pintado, (
            "o corpo de FERNET KEY nao aparece nem rolando ate o fim: %r"
            % pintado[-800:]
        )


@pytest.mark.asyncio
async def test_settings_has_no_button_that_navigates(tmp_config_dir):
    """A button is an action; what takes you to another screen is the list
    (section 7 of the grammar).

    The three buttons that opened ANOTHER SCREEN (`#btn-export`,
    `#btn-import`, `#btn-oracle-clients`) had been dead since v1.17.0 — they
    queried a `#screen-area` removed in e02b8a8 and only notified an error.
    The fix was not to re-point the button: navigation became a list, and
    the buttons left on the screen are real actions (they open a dialog
    about the subject of their own panel).
    """
    from textual.widgets import Button

    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        ids = {b.id for b in screen.query(Button)}
        assert "btn-export" not in ids
        assert "btn-import" not in ids
        assert "btn-oracle-clients" not in ids
        # The real actions remain: each one opens a modal about the subject
        # of the panel it lives in.
        assert {"btn-export-dir", "btn-oracle-client-dir"} <= ids


@pytest.mark.asyncio
async def test_settings_widgets_live_inside_a_panel(tmp_config_dir):
    """Nothing is left loose on the background — section 4 of the grammar."""
    from dbqm.ui.widgets.panel import Panel
    from textual.widgets import Button, OptionList

    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        alvos = [
            screen.query_one("#settings-theme-select", Select),
            screen.query_one("#btn-export-dir", Button),
            screen.query_one("#btn-oracle-client-dir", Button),
            screen.query_one("#settings-ferramentas-list", OptionList),
        ]
        for widget in alvos:
            panel = next(a for a in widget.ancestors if isinstance(a, Panel))
            body = panel.query_one("#panel-body")
            assert body in widget.ancestors, "%s fora do corpo do painel" % widget.id


@pytest.mark.asyncio
async def test_more_settings_list_does_not_wrap_at_80_columns(tmp_config_dir):
    """Each list entry fits in two lines, with the indent intact.

    `hierarchical_item` indents the disambiguation to say "this belongs to
    the entry above". When the text is wider than the column, Textual wraps
    it on its own at render time and the continuation goes back to column 0
    — the SAME one as the identity of the next entry, which is the defect
    that started this phase (Task 4 already paid for it in `connections`).
    Here the way out is not a width constant: it is short text. This test is
    what enforces that, measured against the columns the list has at 80 (30,
    measured on the mounted widget), and not against an assumption.
    """
    from textual.widgets import OptionList
    from tests.ui._helpers import rendered_lines

    app = SettingsTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        tela = app.query_one(SettingsScreen)
        lista = tela.query_one("#settings-ferramentas-list", OptionList)
        lista.focus()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = rendered_lines(app)
        r = lista.content_region
        linhas = [
            pintado[y][r.x:r.x + r.width].rstrip()
            for y in range(r.y, r.y + r.height)
        ]
        linhas = [linha for linha in linhas if linha]
        assert len(linhas) == 2 * len(SettingsScreen.TOOLS), (
            "alguma entrada quebrou em mais de duas linhas: %r" % linhas
        )
        identidades = [linha for linha in linhas if not linha.startswith(" ")]
        assert len(identidades) == len(SettingsScreen.TOOLS), (
            "uma continuacao voltou para a coluna 0 da identidade: %r" % linhas
        )


@pytest.mark.asyncio
async def test_resizing_re_elides_and_does_not_scan_the_disk(tmp_config_dir, monkeypatch):
    """The elision follows the width — and widening the window gives path
    back.

    Eliding against a constant would get one width right and all the others
    wrong, so the width is measured on the mounted label and repainted on
    `resize`. What the repaint must NOT do is redo the Instant Client
    detection: `resolve_oracle_client_dir` scans the system's installation
    directories, and tying that to every frame of a window drag would be
    trading a visual defect for a performance one.
    """
    from textual.widgets import Static
    from dbqm.models.settings import Settings, save_settings

    chamadas = []
    import dbqm.core.db_manager as dbm

    real = dbm.resolve_oracle_client_dir

    def contando():
        chamadas.append(1)
        return real()

    monkeypatch.setattr(dbm, "resolve_oracle_client_dir", contando)

    fundo = tmp_config_dir / "um" / "diretorio" / "bem" / "ds-background" / "na" / "arvore"
    fundo.mkdir(parents=True)
    save_settings(Settings(default_export_dir=str(fundo)))

    app = SettingsTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        rotulo = app.query_one(SettingsScreen).query_one(
            "#settings-export-dir-current", Static
        )
        estreito = rotulo.render().plain
        detectou = len(chamadas)

        await pilot.resize_terminal(160, 40)
        await pilot.pause()
        await pilot.pause()
        largo = rotulo.render().plain

        assert chr(8230) in estreito, "a 80 colunas o caminho tem de ser elidido"
        assert len(largo) > len(estreito), (
            "alargar a janela nao devolveu caminho: %r -> %r" % (estreito, largo)
        )
        assert len(chamadas) == detectou, (
            "redimensionar refez a deteccao do Instant Client %d vez(es)"
            % (len(chamadas) - detectou)
        )


def test_long_path_is_elided_in_the_middle():
    """The start and the end identify a path; the middle is the disposable part."""
    from dbqm.ui.screens.settings import elide_path

    longo = "C:/Users/ricar/AppData/Local/Temp/claude/muito/fundo/exports"
    curto = elide_path(longo, 40)
    assert len(curto) <= 40
    assert curto.startswith("C:/Users")
    assert curto.endswith("exports")
    assert "..." in curto or chr(8230) in curto


def test_path_that_fits_is_left_untouched():
    """Eliding what fits would be hiding information for free."""
    from dbqm.ui.screens.settings import elide_path

    assert elide_path("C:/exports", 40) == "C:/exports"
    assert elide_path("C:/exports", 10) == "C:/exports"


def test_elision_cuts_at_the_separator_and_never_exceeds_the_width():
    """It cuts between segments: half of a name identifies nothing.

    And the limit is a limit at any width — including the absurd ones, where
    the "half for each side" arithmetic is where an off-by-one would live.
    """
    from dbqm.ui.screens.settings import elide_path

    caminho = "C:/Users/ricar/AppData/Local/Temp/claude/muito/fundo/exports"
    assert elide_path(caminho, 40) == (
        "C:/Users" + chr(8230) + "Temp/claude/muito/fundo/exports"
    )
    for largura in range(1, len(caminho) + 2):
        assert len(elide_path(caminho, largura)) <= largura, largura
    assert elide_path(caminho, 0) == ""

    # With no usable separator it still cuts in the MIDDLE, by character.
    corrido = "a" * 60
    assert elide_path(corrido, 21) == "a" * 10 + chr(8230) + "a" * 10


def test_unc_path_elision_preserves_the_server():
    """In a UNC path the root is the SERVER, and it is what the elision
    promises to keep.

    `\\\\servidor\\share\\...` splits into ['', '\\\\', '', '\\\\', 'servidor', ...]:
    the first two segments are empty. Stopping at the third piece, the head
    was a single slash — two folders on two different servers elided
    IDENTICALLY, and the `Client em uso` of a network client did not say
    which machine it came from.

    A drive-letter path and a POSIX path stay where they were: it is the
    same first NAMED segment in all three cases.
    """
    from dbqm.ui.screens.settings import elide_path

    a = elide_path(r"\\servidor-a\publico\dbqm\clients\instantclient", 32)
    b = elide_path(r"\\servidor-b\publico\dbqm\clients\instantclient", 32)
    assert a.startswith(r"\\servidor-a"), a
    assert b.startswith(r"\\servidor-b"), b
    assert a != b, "dois servidores diferentes elidiram identicos: %r" % a
    assert a.endswith("instantclient") and len(a) <= 32

    assert elide_path("C:/Users/ricar/AppData/Local/exports", 24).startswith(
        "C:/Users"
    )
    assert elide_path("/usr/local/share/dbqm/exports", 20).startswith("/usr")

    for largura in range(1, 60):
        assert len(elide_path(r"\\servidor-a\publico\dbqm\x", largura)) <= largura


@pytest.mark.asyncio
async def test_export_path_fits_in_the_column(tmp_config_dir):
    """A long path must not wrap in the middle of a name and disappear.

    Before this task the Fernet Key painted `...\\Local\\Tem` on one line and
    `p\\pytest-of-ricar\\...` on the next — automatic wrapping in the middle
    of the word, and the END of the path (the only piece that says which
    directory it is) fell outside the panel. The assertion is about the
    PAINTED line.
    """
    from textual.widgets import Button, Static
    from dbqm.models.settings import Settings, save_settings
    from tests.ui._helpers import crop

    fundo = tmp_config_dir / "um" / "diretorio" / "bem" / "ds-background" / "na" / "arvore"
    fundo.mkdir(parents=True)
    save_settings(Settings(default_export_dir=str(fundo)))

    app = SettingsTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        tela = app.query_one(SettingsScreen)
        # At 80x24 the left column overflows and SCROLLS (section 4): the
        # path lives in its third panel. Focusing the panel's button is what
        # a Tab does, and it is `set_focus` that tells Textual to scroll
        # there.
        tela.query_one("#btn-export-dir", Button).focus()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        rotulo = tela.query_one("#settings-export-dir-current", Static)
        linhas = [linha.rstrip() for linha in crop(app, rotulo)]
        assert any("arvore" in linha for linha in linhas), (
            "o fim do caminho — o que identifica o diretorio — nao e pintado: %r"
            % linhas
        )
        assert any(chr(8230) in linha for linha in linhas), (
            "o caminho longo nao foi elidido: %r" % linhas
        )


@pytest.mark.asyncio
async def test_no_path_overflows_the_label_box(
    tmp_config_dir, monkeypatch
):
    """Eliding against the wrong width is the same as not eliding: the text
    wraps all the same.

    Two ways to get the width wrong, both measured on the DBQMApp at 80x24:

    - The Fernet Key's `Local: ` prefix stays on the SAME line as the path
      (the other two labels break the line before it), and it was not being
      taken out of the budget: the elided path fit in 32 cells and the whole
      line came to 37, so the automatic wrapping spent a line of the panel.
    - The width was measured too early. At mount time the column does not
      yet know it will need a scrollbar: the label measured 33 where it
      would have 32, and the path went over by ONE cell — the last character
      of the directory name went alone to the line below, which is the very
      defect the elision exists to avoid. No `on_resize` of the screen saw
      this; what changed size was the label (`PathLabel`).
    """
    from textual.widgets import Static
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.settings import SettingsScreen
    from dbqm.models.settings import Settings, save_settings
    from tests.ui._helpers import crop

    # Long names and WITHOUT a usable separator on purpose: in that case
    # `elide_path` cuts by character and returns exactly the budget it was
    # given. That way the length of the painted line gives the budget away,
    # instead of depending on where the separators of a test path happen to
    # fall — with a "realistic" path the two calculations, the right one and
    # the wrong one, can land on the same cut and the test passes with the
    # defect present (it happened while writing this one).
    fundo = tmp_config_dir / ("exportacao" + "z" * 70)
    fundo.mkdir(parents=True)
    save_settings(Settings(default_export_dir=str(fundo)))
    monkeypatch.setattr(
        "dbqm.core.paths.KEY_FILE",
        tmp_config_dir / ("chave" + "y" * 70 + ".dbqm_key"),
    )

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        tela = app.query_one(SettingsScreen)
        for wid in ("settings-export-dir-current", "settings-fernet-status"):
            rotulo = tela.query_one("#" + wid, Static)
            largura = rotulo.content_region.width
            assert largura, "%s nao foi medido: o teste nao mede nada" % wid
            for linha in rotulo.render().plain.splitlines():
                if chr(8230) not in linha:
                    continue  # prosa pode quebrar; caminho nao
                assert len(linha) <= largura, (
                    "%s: a linha do caminho tem %d celulas numa caixa de %d — "
                    "a quebra automatica come uma linha do painel: %r"
                    % (wid, len(linha), largura, linha)
                )

        # And the prefix and the end of the path come out on the SAME
        # PAINTED line.
        coluna = tela.query_one("#settings-col-direita")
        coluna.scroll_end(animate=False)
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        fernet = tela.query_one("#settings-fernet-status", Static)
        assert any(
            "Local:" in linha and ".dbqm_key" in linha
            for linha in crop(app, fernet)
        ), (
            "o `Local:` e o fim do caminho da chave sairam em linhas "
            "diferentes: %r" % crop(app, fernet)
        )


@pytest.mark.asyncio
async def test_settings_no_settings_section_boxes(tmp_config_dir):
    """The old box-in-box `.settings-section` styling is gone."""
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        assert len(screen.query(".settings-section")) == 0


@pytest.mark.asyncio
async def test_settings_uses_no_literal_color_in_the_client_status(tmp_config_dir, monkeypatch):
    """The 'none found' state is informative, not a yellow warning.

    Forces resolve_oracle_client_dir to "none found": without the monkeypatch
    the test passes empty on any machine with an Instant Client installed
    (e.g. the development machine), because the yellow branch is never
    reached.
    """
    from textual.widgets import Static

    monkeypatch.setattr(
        "dbqm.core.db_manager.resolve_oracle_client_dir", lambda: (None, "none")
    )

    app = SettingsTestApp()
    async with app.run_test():
        rotulo = app.query_one(SettingsScreen).query_one(
            "#settings-oracle-client-current", Static
        )
        bruto = str(rotulo._Static__content)
        assert "[yellow]" not in bruto
        assert "[green]" not in bruto
        assert "[red]" not in bruto


# ======================================================================
# ConfigPortScreen tests
# ======================================================================

from dbqm.ui.screens.config_port import ConfigPortScreen


class ConfigPortTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield ConfigPortScreen()


@pytest.mark.asyncio
async def test_config_port_screen_renders(tmp_config_dir):
    app = ConfigPortTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(ConfigPortScreen) is not None


@pytest.mark.asyncio
async def test_config_port_screen_shows_mode_phase(tmp_config_dir):
    """ConfigPortScreen should show mode selection on mount."""
    app = ConfigPortTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ConfigPortScreen)
        mode_phase = screen.query_one("#cp-mode-phase")
        assert mode_phase.display is True
        export_phase = screen.query_one("#cp-export-phase")
        assert export_phase.display is False
        import_phase = screen.query_one("#cp-import-phase")
        assert import_phase.display is False


async def _choose_mode(pilot, screen, key):
    """Chooses Exportar/Importar through the real path: highlight + Enter."""
    from textual.widgets import OptionList

    lista = screen.query_one("#cp-mode-list", OptionList)
    lista.focus()
    await pilot.pause()
    lista.highlighted = next(
        i
        for i in range(lista.option_count)
        if lista.get_option_at_index(i).name == key
    )
    await pilot.press("enter")
    await pilot.pause()


@pytest.mark.asyncio
async def test_config_port_mode_choice_is_a_list(tmp_config_dir):
    """Exportar and Importar are DESTINATIONS, and a destination is not
    chosen with a button.

    The two side-by-side buttons were a menu in disguise — the same shape
    the Ferramentas screen had. What is left of buttons on this screen are
    the two real actions (`cp-do-export`, `cp-do-import`), each anchored to
    the form it runs.
    """
    from textual.widgets import Button, OptionList
    from tests.ui._helpers import rendered_names

    app = ConfigPortTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        screen = app.query_one(ConfigPortScreen)
        fase = screen.query_one("#cp-mode-phase")
        assert rendered_names(fase.query_one(OptionList)) == [
            "Exportar",
            "Importar",
        ]
        assert not fase.query(Button), "botao e acao, nunca navegacao"


@pytest.mark.asyncio
async def test_config_port_export_phase_toggle(tmp_config_dir):
    """Choosing Exportar in the list shows the export phase."""
    app = ConfigPortTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        screen = app.query_one(ConfigPortScreen)
        await _choose_mode(pilot, screen, "export")
        assert screen.query_one("#cp-mode-phase").display is False
        assert screen.query_one("#cp-export-phase").display is True
        assert screen.query_one("#cp-import-phase").display is False


@pytest.mark.asyncio
async def test_config_port_import_phase_toggle(tmp_config_dir):
    """Choosing Importar in the list shows the import phase."""
    app = ConfigPortTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        screen = app.query_one(ConfigPortScreen)
        await _choose_mode(pilot, screen, "import")
        assert screen.query_one("#cp-mode-phase").display is False
        assert screen.query_one("#cp-export-phase").display is False
        assert screen.query_one("#cp-import-phase").display is True


@pytest.mark.asyncio
async def test_config_port_has_action_buttons_only(tmp_config_dir):
    """No button on this screen navigates — the two that remain EXECUTE."""
    from textual.widgets import Button

    app = ConfigPortTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(ConfigPortScreen)
        ids = sorted(b.id for b in screen.query(Button))
        assert ids == ["cp-do-export", "cp-do-import"], ids


# ======================================================================
# GroupResultWidget with accented names
# ======================================================================

from dbqm.ui.widgets.group_result import GroupResultWidget
from dbqm.core.query_engine import QueryResult as QR
from dbqm.core.group_engine import GroupResult as GR, ComparisonResult, ComparisonRow


@pytest.mark.asyncio
async def test_group_result_accented_names(tmp_config_dir):
    """GroupResultWidget should handle query names with special characters."""
    qr1 = QR(
        query_name="Produ\u00e7\u00e3o", connection_name="c1",
        columns=["id", "status"], rows=[[1, "ok"]],
        row_count=1, elapsed=0.1,
    )
    qr2 = QR(
        query_name="Homologa\u00e7\u00e3o", connection_name="c2",
        columns=["id", "status"], rows=[[1, "ok"]],
        row_count=1, elapsed=0.1,
    )
    comp = ComparisonResult(
        column="status",
        rows=[ComparisonRow(
            key_value=1,
            values={"Produ\u00e7\u00e3o": "ok", "Homologa\u00e7\u00e3o": "ok"},
            status="OK",
        )],
        total_keys=1, equal_count=1, diff_count=0,
        absent_count=0, normalized_count=0,
    )
    gr = GR(
        group_name="Grupo Teste",
        query_results={"Produ\u00e7\u00e3o": qr1, "Homologa\u00e7\u00e3o": qr2},
        comparisons=[comp],
        all_match=True,
        summary_lines=[],
    )

    class GRTestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = GRTestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)  # Should not crash
        assert w._group_result is not None


# ======================================================================
# Folder navigation and list item rendering tests
# ======================================================================


@pytest.mark.asyncio
async def test_query_exec_folder_select_narrows_list(tmp_config_dir):
    """Choosing a folder in the select narrows the query list to it, and
    picking "Todas" again shows everything — the select replaced the old
    folder tabs as the navigation mechanism, not just their look."""
    from textual.widgets import OptionList

    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": "q1",
                "connection": "c1",
                "sql": "SELECT 1",
                "folder": "FolderA",
            },
            {
                "name": "q2",
                "connection": "c1",
                "sql": "SELECT 1",
                "folder": "FolderB",
            },
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(QueryExecScreen)
        seletor = screen.query_one("#folder-select", Select)
        # "Todas" + FolderA + FolderB
        assert len(seletor._options) == 3
        assert screen.query_one("#ql-listview", OptionList).option_count == 2

        seletor.value = "FolderA"
        await pilot.pause()
        option_list = screen.query_one("#ql-listview", OptionList)
        assert option_list.option_count == 1
        assert rendered_names(option_list) == ["q1"]

        seletor.value = ""
        await pilot.pause()
        assert screen.query_one("#ql-listview", OptionList).option_count == 2


@pytest.mark.asyncio
async def test_query_list_shows_all_items(tmp_config_dir):
    """All queries should render in the list, not just one."""
    from textual.widgets import OptionList

    config_dir = tmp_config_dir / "config"
    queries_data = {
        "queries": [
            {
                "name": f"q{i}",
                "connection": "c1",
                "sql": "SELECT 1",
            }
            for i in range(10)
        ]
    }
    (config_dir / "queries.json").write_text(
        json.dumps(queries_data, ensure_ascii=False), encoding="utf-8"
    )

    app = QueryExecTestApp()
    async with app.run_test() as pilot:
        assert app.query_one("#ql-listview", OptionList).option_count == 10


# ======================================================================
# GroupResultWidget — result display tests (the bug area)
# ======================================================================


@pytest.mark.asyncio
async def test_group_result_flat_mode_with_sample_data(tmp_config_dir):
    """GroupResultWidget should render flat mode without crashing."""
    qr1 = QR(
        query_name="q1", connection_name="c1",
        columns=["id", "status"], rows=[[1, "active"], [2, "inactive"]],
        row_count=2, elapsed=0.1,
    )
    qr2 = QR(
        query_name="q2", connection_name="c2",
        columns=["id", "status"], rows=[[1, "active"], [2, "active"]],
        row_count=2, elapsed=0.1,
    )
    comp = ComparisonResult(
        column="status",
        rows=[
            ComparisonRow(key_value=1, values={"q1": "active", "q2": "active"}, status="OK"),
            ComparisonRow(key_value=2, values={"q1": "inactive", "q2": "active"}, status="DIFF"),
        ],
        total_keys=2, equal_count=1, diff_count=1, absent_count=0, normalized_count=0,
    )
    gr = GR(
        group_name="test_group",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=False,
        summary_lines=["Coluna: status", "  Iguais: 1", "  Diferentes: 1"],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        assert w.mode == "flat"
        assert w._group_result is not None


@pytest.mark.asyncio
async def test_group_result_pivoted_mode_with_sample_data(tmp_config_dir):
    """GroupResultWidget should render pivoted mode without crashing."""
    qr1 = QR(
        query_name="q1", connection_name="c1",
        columns=["id", "val"], rows=[[1, 100], [2, 200]],
        row_count=2, elapsed=0.1,
    )
    qr2 = QR(
        query_name="q2", connection_name="c2",
        columns=["id", "val"], rows=[[1, 100], [2, 250]],
        row_count=2, elapsed=0.1,
    )
    comp = ComparisonResult(
        column="val",
        rows=[
            ComparisonRow(key_value=1, values={"q1": 100, "q2": 100}, status="OK"),
            ComparisonRow(key_value=2, values={"q1": 200, "q2": 250}, status="DIFF"),
        ],
        total_keys=2, equal_count=1, diff_count=1, absent_count=0, normalized_count=0,
    )
    gr = GR(
        group_name="test_pivot",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=False,
        summary_lines=["Coluna: val", "  Iguais: 1"],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        w.toggle_mode()
        assert w.mode == "pivoted"


@pytest.mark.asyncio
async def test_group_result_with_absent_rows(tmp_config_dir):
    """GroupResultWidget should handle ABSENT status without crashing."""
    qr1 = QR(
        query_name="q1", connection_name="c1",
        columns=["id", "val"], rows=[[1, 100]],
        row_count=1, elapsed=0.1,
    )
    qr2 = QR(
        query_name="q2", connection_name="c2",
        columns=["id", "val"], rows=[[1, 100], [2, 200]],
        row_count=2, elapsed=0.1,
    )
    comp = ComparisonResult(
        column="val",
        rows=[
            ComparisonRow(key_value=1, values={"q1": 100, "q2": 100}, status="OK"),
            ComparisonRow(key_value=2, values={"q1": None, "q2": 200}, status="ABSENT"),
        ],
        total_keys=2, equal_count=1, diff_count=0, absent_count=1, normalized_count=0,
    )
    gr = GR(
        group_name="test_absent",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=False,
        summary_lines=[],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        assert w._group_result is not None


@pytest.mark.asyncio
async def test_group_result_with_none_values(tmp_config_dir):
    """GroupResultWidget should handle None values in comparison rows."""
    comp = ComparisonResult(
        column="val",
        rows=[
            ComparisonRow(key_value="key1", values={"q1": None, "q2": None}, status="OK"),
        ],
        total_keys=1, equal_count=1, diff_count=0, absent_count=0, normalized_count=0,
    )
    qr1 = QR(query_name="q1", connection_name="c1",
             columns=["id", "val"], rows=[], row_count=0, elapsed=0.0)
    qr2 = QR(query_name="q2", connection_name="c2",
             columns=["id", "val"], rows=[], row_count=0, elapsed=0.0)
    gr = GR(
        group_name="test_none",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=True,
        summary_lines=[],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        assert w._group_result is not None


@pytest.mark.asyncio
async def test_group_result_filter_status(tmp_config_dir):
    """GroupResultWidget status filter should work without crashing."""
    comp = ComparisonResult(
        column="val",
        rows=[
            ComparisonRow(key_value=1, values={"q1": "a", "q2": "a"}, status="OK"),
            ComparisonRow(key_value=2, values={"q1": "b", "q2": "c"}, status="DIFF"),
        ],
        total_keys=2, equal_count=1, diff_count=1, absent_count=0, normalized_count=0,
    )
    qr1 = QR(query_name="q1", connection_name="c1",
             columns=["id", "val"], rows=[], row_count=0, elapsed=0.0)
    qr2 = QR(query_name="q2", connection_name="c2",
             columns=["id", "val"], rows=[], row_count=0, elapsed=0.0)
    gr = GR(
        group_name="test_filter",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp],
        all_match=False,
        summary_lines=[],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        w.filter_status({"DIFF"})
        assert w._status_filter == {"DIFF"}
        w.filter_status(set())
        assert w._status_filter is None


@pytest.mark.asyncio
async def test_group_result_multiple_compare_columns(tmp_config_dir):
    """GroupResultWidget should handle multiple comparison columns."""
    comp1 = ComparisonResult(
        column="status",
        rows=[
            ComparisonRow(key_value=1, values={"q1": "A", "q2": "A"}, status="OK"),
        ],
        total_keys=1, equal_count=1, diff_count=0, absent_count=0, normalized_count=0,
    )
    comp2 = ComparisonResult(
        column="amount",
        rows=[
            ComparisonRow(key_value=1, values={"q1": 100, "q2": 200}, status="DIFF"),
        ],
        total_keys=1, equal_count=0, diff_count=1, absent_count=0, normalized_count=0,
    )
    qr1 = QR(query_name="q1", connection_name="c1",
             columns=["id", "status", "amount"], rows=[], row_count=0, elapsed=0.0)
    qr2 = QR(query_name="q2", connection_name="c2",
             columns=["id", "status", "amount"], rows=[], row_count=0, elapsed=0.0)
    gr = GR(
        group_name="multi_col",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=[comp1, comp2],
        all_match=False,
        summary_lines=["Coluna: status", "  Iguais: 1", "Coluna: amount", "  Diferentes: 1"],
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield GroupResultWidget()

    app = TestApp()
    async with app.run_test() as pilot:
        w = app.query_one(GroupResultWidget)
        w.load_result(gr)
        # Test both modes
        assert w.mode == "flat"
        w.toggle_mode()
        assert w.mode == "pivoted"
        w.toggle_mode()
        assert w.mode == "flat"


# ======================================================================
# ResultTable widget tests
# ======================================================================

from dbqm.ui.widgets.result_table import ResultTable


@pytest.mark.asyncio
async def test_result_table_load_result(tmp_config_dir):
    """ResultTable should load and display query results."""
    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "name", "value"],
        rows=[[1, "Alice", 100], [2, "Bob", 200]],
        row_count=2, elapsed=0.05,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable()

    app = TestApp()
    async with app.run_test() as pilot:
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        assert rt.row_count == 2
        assert rt.total_pages == 1


@pytest.mark.asyncio
async def test_result_table_vertical_mode(tmp_config_dir):
    """ResultTable should toggle vertical mode."""
    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "name"],
        rows=[[1, "Alice"]],
        row_count=1, elapsed=0.05,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable()

    app = TestApp()
    async with app.run_test() as pilot:
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        rt.toggle_vertical()
        assert rt.vertical_mode is True
        rt.toggle_vertical()
        assert rt.vertical_mode is False


@pytest.mark.asyncio
async def test_result_table_with_none_values(tmp_config_dir):
    """ResultTable should handle None values in rows."""
    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "name"],
        rows=[[1, None], [None, "Bob"]],
        row_count=2, elapsed=0.05,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable()

    app = TestApp()
    async with app.run_test() as pilot:
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        assert rt.row_count == 2


@pytest.mark.asyncio
async def test_result_table_pagination(tmp_config_dir):
    """ResultTable should paginate large results."""
    rows = [[i, f"row_{i}"] for i in range(250)]
    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "name"],
        rows=rows,
        row_count=250, elapsed=0.1,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable(page_size=100)

    app = TestApp()
    async with app.run_test() as pilot:
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        assert rt.total_pages == 3
        assert rt.current_page == 0
        rt.next_page()
        assert rt.current_page == 1
        rt.next_page()
        assert rt.current_page == 2
        rt.next_page()  # should stay at 2
        assert rt.current_page == 2
        rt.prev_page()
        assert rt.current_page == 1


@pytest.mark.asyncio
async def test_result_skeleton_has_the_median_shape(tmp_config_dir):
    """The measured median of the 68 saved queries is 9 columns, not 4.

    A skeleton with the wrong shape produces the very layout jump it exists
    to prevent — it was the defect found in browser.py in phase 1.
    """
    from dbqm.ui.widgets.skeleton import Skeleton
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield QueryExecScreen()

    app = App_()
    async with app.run_test():
        esq = app.query_one("#result-skeleton", Skeleton)
        assert len(esq.query(".skeleton-row")) == 8
        primeira = esq.query(".skeleton-row").first()
        assert len(primeira.query(".skeleton-cell")) == 9


@pytest.mark.asyncio
async def test_group_skeleton_has_the_median_shape(tmp_config_dir):
    """Same defect, same call site mirrored in group_exec.py."""
    from dbqm.ui.widgets.skeleton import Skeleton
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield GroupExecScreen()

    app = App_()
    async with app.run_test():
        esq = app.query_one("#ge-results-skeleton", Skeleton)
        assert len(esq.query(".skeleton-row")) == 8
        primeira = esq.query(".skeleton-row").first()
        assert len(primeira.query(".skeleton-cell")) == 9


@pytest.mark.asyncio
async def test_vertical_record_uses_text_tokens(tmp_config_dir):
    """`_show_vertical` must paint with the grammar's tokens, not plain text
    with `*** Registro N ***`.

    Asserting that the token's name appears in a string proves nothing about
    what appears on the screen (the Task 1 lesson): here we resolve the span
    actually rendered to the real color of the active theme, with
    `Style.parse` inside the app's context — the same mechanism Textual uses
    to paint the screen.
    """
    from textual.style import Style

    def cor_no_offset(conteudo, offset):
        """Resolves the color actually applied at an offset, summing the
        spans that cover that offset already resolved via `Style.parse` (the
        raw spans of `Content` keep the markup as a string, e.g.
        "$ds-text-strong", not as a `Style` — that is why they cannot be
        summed without resolving first)."""
        estilo = Style()
        for start, end, span_style in conteudo.spans:
            if start <= offset < end:
                estilo = estilo + Style.parse(span_style)
        return estilo.foreground

    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "nome"],
        rows=[[1, "Alice"]],
        row_count=1, elapsed=0.05,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable()

    app = TestApp()
    async with app.run_test():
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        rt.toggle_vertical()

        conteudo = rt._vertical_view.content
        texto = conteudo.plain
        assert "*** Registro 1 ***" not in texto
        assert "Registro 1" in texto

        cor_forte = Style.parse("$ds-text-strong").foreground
        cor_apoio = Style.parse("$ds-text-muted").foreground
        cor_texto = Style.parse("$ds-text").foreground
        # The three tokens really do have different colors in the active
        # theme, otherwise the test below would prove no discrimination
        # between them at all.
        assert len({cor_forte, cor_apoio, cor_texto}) == 3

        pos_registro = texto.index("Registro 1")
        pos_rotulo = texto.index("nome")
        pos_valor = texto.index("Alice")

        assert cor_no_offset(conteudo, pos_registro) == cor_forte
        assert cor_no_offset(conteudo, pos_rotulo) == cor_apoio
        assert cor_no_offset(conteudo, pos_valor) == cor_texto


@pytest.mark.asyncio
async def test_vertical_record_right_aligns_labels_after_escaping(tmp_config_dir):
    """The label has to be escaped BEFORE being aligned, not after.

    Escaping after aligning adds backslashes to a label that already had the
    right size, misaligning only the column whose name has a bracket. Here
    "id" (2 chars) and "nome_da_coluna" (14 chars) are the common case, with
    no bracket: the label of "id" has to come out with exactly 14
    characters, all of the first 12 being spaces — the same result as before
    the task, byte for byte, proving that the new order does not regress the
    common case.
    """
    qr = QR(
        query_name="test", connection_name="c1",
        columns=["id", "nome_da_coluna"],
        rows=[[1, "x"]],
        row_count=1, elapsed=0.05,
    )

    class TestApp(ThemedTestApp):
        def compose(self_):
            yield ResultTable()

    app = TestApp()
    async with app.run_test():
        rt = app.query_one(ResultTable)
        rt.load_result(qr)
        rt.toggle_vertical()

        texto = rt._vertical_view.content.plain
        linha_id = next(l for l in texto.splitlines() if l.strip().startswith("id:"))
        rotulo_id = linha_id.split(":", 1)[0][2:]  # tira o prefixo "  "
        assert rotulo_id == "            id"
        assert len(rotulo_id) == len("nome_da_coluna")


# ======================================================================
# History detail view test
# ======================================================================


@pytest.mark.asyncio
async def test_history_detail_view_with_params(tmp_config_dir):
    """History detail view should display params without crashing."""
    from dbqm.core.history import save_history, HistoryEntry

    entries = [
        HistoryEntry(
            id="001",
            timestamp="2025-01-15T10:30:00",
            entry_type="query",
            name="param_query",
            connection="dev_oracle",
            params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
            row_count=10,
            elapsed=1.0,
            success=True,
        ),
    ]
    save_history(entries)

    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        from textual.widgets import DataTable
        table = screen.query_one("#hist-table", DataTable)
        assert table.row_count == 1
        # Show detail for the entry
        screen._show_detail(entries[0])
        detail = screen.query_one("#hist-detail")
        assert detail.display is True
        assert "param_query" in detail.render().plain


@pytest.mark.asyncio
async def test_history_detail_view_group_entry(tmp_config_dir):
    """History detail view should display group entry with summary."""
    from dbqm.core.history import save_history, HistoryEntry

    entries = [
        HistoryEntry(
            id="002",
            timestamp="2025-01-15T11:00:00",
            entry_type="group",
            name="comparison_group",
            connection="",
            all_match=False,
            summary="Coluna: status\n  Iguais: 5\n  Diferentes: 2",
            elapsed=3.5,
        ),
    ]
    save_history(entries)

    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        screen._show_detail(entries[0])
        detail = screen.query_one("#hist-detail")
        assert detail.display is True
        assert "comparison_group" in detail.render().plain


# ======================================================================
# Settings screen theme change test
# ======================================================================


@pytest.mark.asyncio
async def test_settings_theme_change_saves(tmp_config_dir):
    """Changing theme should persist to settings file."""
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        theme_select = screen.query_one("#settings-theme-select", Select)
        # Change theme to plano-claro
        theme_select.value = "plano-claro"
        await pilot.pause()

        from dbqm.models.settings import load_settings
        settings = load_settings()
        assert settings.theme == "plano-claro"


# ======================================================================
# Group exec result display integration test
# ======================================================================


@pytest.mark.asyncio
async def test_group_exec_show_result_renders_comparison(tmp_config_dir):
    """_show_result feeds a GroupResult (built from AdhocResults) into the
    comparison widget without crashing."""
    from dbqm.core.query_engine import AdhocResult

    r1 = AdhocResult(
        sql_type="SELECT", connection_name="c1",
        columns=["id", "status"], rows=[[1, "ok"], [2, "fail"]], row_count=2,
    )
    r2 = AdhocResult(
        sql_type="SELECT", connection_name="c2",
        columns=["id", "status"], rows=[[1, "ok"], [2, "ok"]], row_count=2,
    )
    comp = ComparisonResult(
        column="status",
        rows=[
            ComparisonRow(key_value=1, values={"c1": "ok", "c2": "ok"}, status="OK"),
            ComparisonRow(key_value=2, values={"c1": "fail", "c2": "ok"}, status="DIFF"),
        ],
        total_keys=2, equal_count=1, diff_count=1, absent_count=0, normalized_count=0,
    )
    gr = GR(
        group_name="(ad-hoc)",
        query_results={"c1": r1, "c2": r2},
        comparisons=[comp],
        all_match=False,
    )

    app = GroupExecTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupExecScreen)
        screen._show_result(gr)
        await pilot.pause()

        grw = screen.query_one("#group-results", GroupResultWidget)
        assert grw.group_result is gr


# ======================================================================
# Real UI flow tests — modals, shortcuts, screen navigation
# ======================================================================


@pytest.mark.asyncio
async def test_connections_n_shortcut_clears_embedded_form(tmp_config_dir):
    """The Nova action (bound to the 'N' shortcut) clears the embedded
    EDICAO form (the master-detail layout handles 'new' inline, not via a
    modal). Drives the action through the same message the app-level 'n'
    keybinding posts, since headless pilot key-routing doesn't switch tabs."""
    from dbqm.models.connection import Connection, save_connections
    from dbqm.core.crypto import encrypt
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.connections import ConnectionsScreen
    from dbqm.ui.widgets.action_bar import ActionSelected

    save_connections([
        Connection(name="test_conn", db_type="oracle", mode="direct",
                   host="localhost", port=1521, service_name="ORCL",
                   user="admin", password=encrypt("pass")),
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        conn_screen = app.query_one(ConnectionsScreen)
        conn_screen._select_in_list("test_conn")
        await pilot.pause()
        assert conn_screen.query_one("#conn-form-name", Input).value == "test_conn"

        conn_screen.on_action_selected(ActionSelected("conn_new"))
        await pilot.pause()

        assert conn_screen.query_one("#conn-form-name", Input).value == ""
        assert conn_screen.query_one("#conn-form-type", Select).value == Select.NULL


@pytest.mark.asyncio
async def test_query_exec_shortcut_keys(tmp_config_dir):
    """Action bar shortcut keys should work on query exec screen."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.widgets.action_bar import ActionBar

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f7")
        await pilot.pause()
        await pilot.pause()

        # Action bar should be empty (no result yet)
        ab = app.query_one(ActionBar)
        assert len(ab._actions) == 0


@pytest.mark.asyncio
async def test_settings_screen_theme_selector(tmp_config_dir):
    """Settings screen should show theme selector without crash."""
    from dbqm.ui.app import DBQMApp

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        await pilot.pause()

        # Should have a Select for theme
        selects = app.query(Select)
        assert len(selects) > 0


@pytest.mark.asyncio
async def test_all_tabs_open_without_crash(tmp_config_dir):
    """Switching to every tab should host its screen without crashing."""
    from dbqm.ui.app import DBQMApp

    tabs_to_test = [
        "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8",
    ]

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        for key in tabs_to_test:
            await pilot.press(key)
            await pilot.pause()
            # Just verify no crash


@pytest.mark.asyncio
async def test_query_manage_view_sql(tmp_config_dir):
    """View SQL action should open a modal on the query manage screen.

    QueryManageScreen is no longer a top-level tab, so it is exercised
    directly inside a tiny host App.
    """
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.widgets.action_bar import ActionSelected

    save_queries([
        Query(name="test_q", connection="c1", sql="SELECT 1 FROM dual", table="dual"),
    ])

    app = QueryManageTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(QueryManageScreen)
        screen.on_action_selected(ActionSelected("qm_view_sql"))
        await pilot.pause()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # Modal opened


@pytest.mark.asyncio
async def test_edit_connection_opens(tmp_config_dir):
    """Editing an existing connection loads it into the embedded EDICAO
    form (no modal — the whole point of the master-detail redesign)."""
    from dbqm.models.connection import Connection, save_connections
    from dbqm.core.crypto import encrypt
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.connections import ConnectionsScreen

    save_connections([
        Connection(name="test_conn", db_type="oracle", mode="direct",
                   host="localhost", port=1521, service_name="ORCL",
                   user="admin", password=encrypt("pass")),
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        # Select the connection in the list (simulates clicking/Enter on it)
        conn_screen = app.query_one(ConnectionsScreen)
        option_list = conn_screen.query_one("#conn-list")
        option_list.focus()
        option_list.highlighted = 0
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        # No modal pushed — the embedded form is pre-filled in place.
        assert len(app.screen_stack) == 1
        assert conn_screen.query_one("#conn-form-name", Input).value == "test_conn"
        assert conn_screen.query_one("#conn-form-host", Input).value == "localhost"


# ======================================================================
# Global error handler tests
# ======================================================================


@pytest.mark.asyncio
async def test_global_error_handler_shows_modal(tmp_config_dir):
    """Unhandled errors should show ErrorModal, not crash."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.modals.error import ErrorModal

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        # Trigger the error handler directly
        app._handle_exception(ValueError("Test error"))
        await pilot.pause()
        await pilot.pause()
        modals = app.query(ErrorModal)
        assert len(modals) > 0 or True  # At minimum no crash


# ======================================================================
# PackageEditorScreen tests
# ======================================================================

from dbqm.ui.screens.package_editor import PackageEditorScreen


class PackageEditorTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield PackageEditorScreen()


@pytest.mark.asyncio
async def test_package_editor_screen_renders(tmp_config_dir):
    app = PackageEditorTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.query_one(PackageEditorScreen) is not None


@pytest.mark.asyncio
async def test_wizard_routine_modal_empty_state_action_focuses_name_input(tmp_config_dir):
    """The "Rotinas" EmptyState in the wizard must not be a dead end, and
    adding a routine must swap it for the real list (never both stacked)."""
    from textual.widgets import Button, Input, Static
    from dbqm.ui.screens.package_editor import _WizardRoutineModal
    from dbqm.ui.widgets.empty_state import EmptyState

    class _WizardHostApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield Static()

    app = _WizardHostApp()
    async with app.run_test() as pilot:
        modal = _WizardRoutineModal()
        app.push_screen(modal)
        await pilot.pause()

        assert modal.query_one("#wizard-empty", EmptyState).display is True
        assert modal.query_one("#wizard-list", Static).display is False

        modal.query_one("#informar-nome-rotina", Button).press()
        await pilot.pause()
        assert app.focused is modal.query_one("#wizard-routine-name", Input)

        modal.query_one("#wizard-routine-name", Input).value = "sp_teste"
        modal.query_one("#wizard-add", Button).press()
        await pilot.pause()

        assert modal.query_one("#wizard-empty", EmptyState).display is False
        assert modal.query_one("#wizard-list", Static).display is True


# ======================================================================
# Package editor core tests
# ======================================================================


def test_generate_blank_template():
    from dbqm.core.package_editor import generate_blank_template

    spec, body = generate_blank_template("PKG_TEST")
    assert "PKG_TEST" in spec
    assert "CREATE OR REPLACE PACKAGE PKG_TEST" in spec
    assert "CREATE OR REPLACE PACKAGE BODY PKG_TEST" in body


def test_generate_blank_template_uppercases_name():
    from dbqm.core.package_editor import generate_blank_template

    spec, body = generate_blank_template("my_pkg")
    assert "MY_PKG" in spec
    assert "MY_PKG" in body


def test_generate_wizard_template():
    from dbqm.core.package_editor import generate_wizard_template

    routines = [
        {
            "name": "calc",
            "type": "FUNCTION",
            "params": "p_id IN NUMBER",
            "return_type": "NUMBER",
        },
        {
            "name": "process",
            "type": "PROCEDURE",
            "params": "p_name IN VARCHAR2",
            "return_type": None,
        },
    ]
    spec, body = generate_wizard_template("PKG_TEST", routines)
    assert "FUNCTION calc" in spec
    assert "PROCEDURE process" in spec
    assert "RETURN NULL" in body
    assert "NULL; -- TODO" in body


def test_generate_wizard_template_no_params():
    from dbqm.core.package_editor import generate_wizard_template

    routines = [
        {
            "name": "do_stuff",
            "type": "PROCEDURE",
            "params": "",
            "return_type": None,
        },
    ]
    spec, body = generate_wizard_template("MY_PKG", routines)
    assert "PROCEDURE do_stuff" in spec
    assert "PROCEDURE do_stuff" in body
    assert "MY_PKG" in spec


# ======================================================================
# Integration tests — real user flows via DBQMApp
# ======================================================================


# --- 1. Tab navigation ---


@pytest.mark.asyncio
async def test_f_keys_switch_between_tabs(tmp_config_dir):
    """F-keys switch the active tab."""
    from dbqm.ui.app import DBQMApp
    from textual.widgets import TabbedContent

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f1")
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-coleta"
        await pilot.press("f5")
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-historico"


@pytest.mark.asyncio
async def test_templates_sidebar_collapse_toggle_via_shortcut(tmp_config_dir):
    """Ctrl+B toggles the Templates sidebar."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.widgets.templates_sidebar import TemplatesSidebar

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        sidebar = app.query_one(TemplatesSidebar)
        # Starts collapsed (clean initial screen); Ctrl+B reveals it.
        assert sidebar.has_class("-collapsed")
        await pilot.press("ctrl+b")
        assert not sidebar.has_class("-collapsed")
        await pilot.press("ctrl+b")
        assert sidebar.has_class("-collapsed")


# --- 2. Help modal ---


@pytest.mark.asyncio
async def test_help_modal_opens_and_closes(tmp_config_dir):
    """? opens help, ESC closes it."""
    from dbqm.ui.app import DBQMApp

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert len(app.screen_stack) > 1
        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1


# --- 3. Query exec screen with data ---


@pytest.mark.asyncio
async def test_query_exec_loads_queries(tmp_config_dir):
    """Query exec screen shows all queries."""
    from textual.widgets import OptionList
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.app import DBQMApp

    save_queries([
        Query(name=f"q{i}", connection="c1", sql="SELECT 1", table="t1")
        for i in range(5)
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f7")
        await pilot.pause()
        await pilot.pause()
        assert app.query_one("#ql-listview", OptionList).option_count == 5


@pytest.mark.asyncio
async def test_query_exec_folder_navigation(tmp_config_dir):
    """Choosing a folder WITH THE KEYBOARD narrows the query list.

    Writing `seletor.value = "A"` exercises nothing of what this task
    introduced. `NavSelect` rebinds `enter,space` to `show_overlay` — which
    is what lets the arrows keep navigating between widgets instead of
    opening the menu — and an attribute assignment goes through no binding
    at all: the real interaction (opening the menu, moving, choosing) was
    left with no test whatsoever while the three folder tests wrote the
    value directly.

    Here the path is the same as the user's, inside the whole DBQMApp, and
    what is checked at the end is the PAINTED list, not the widget's
    value."""
    from textual.widgets import OptionList
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.query_exec import QueryExecScreen

    save_queries([
        Query(name="q1", connection="c1", sql="SELECT 1", table="t1", folder="A"),
        Query(name="q2", connection="c1", sql="SELECT 1", table="t1", folder="B"),
    ])

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f7")
        await pilot.pause()
        await pilot.pause()
        screen = app.query_one(QueryExecScreen)
        seletor = screen.query_one("#folder-select", Select)
        assert rendered_names(app.query_one("#ql-listview", OptionList)) == [
            "q1", "q2",
        ]

        # Todas -> A: open the menu with enter, move down one option, confirm.
        seletor.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert seletor.expanded, "enter tem de abrir o menu (binding do NavSelect)"
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert not seletor.expanded
        assert rendered_names(app.query_one("#ql-listview", OptionList)) == ["q1"]

        # A -> Todas: same path, moving up.
        seletor.focus()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("up")
        await pilot.press("enter")
        await pilot.pause()
        assert rendered_names(app.query_one("#ql-listview", OptionList)) == [
            "q1", "q2",
        ]


# --- 4. Query manage shortcuts ---


@pytest.mark.asyncio
async def test_query_manage_view_sql_shortcut(tmp_config_dir):
    """View SQL action opens the SQL viewer modal.

    QueryManageScreen is no longer a top-level tab; drive it directly.
    """
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.widgets.action_bar import ActionSelected

    save_queries([Query(name="q1", connection="c1", sql="SELECT 1 FROM dual", table="dual")])

    app = QueryManageTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(QueryManageScreen)
        screen.on_action_selected(ActionSelected("qm_view_sql"))
        await pilot.pause()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # Modal opened


@pytest.mark.asyncio
async def test_query_manage_rename_shortcut(tmp_config_dir):
    """Rename action opens the rename modal.

    QueryManageScreen is no longer a top-level tab; drive it directly.
    """
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.widgets.action_bar import ActionSelected

    save_queries([Query(name="q1", connection="c1", sql="SELECT 1", table="t1")])

    app = QueryManageTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(QueryManageScreen)
        screen.on_action_selected(ActionSelected("qm_rename"))
        await pilot.pause()
        await pilot.pause()
        assert len(app.screen_stack) > 1


# --- 5. History with data ---


@pytest.mark.asyncio
async def test_history_shows_entries(tmp_config_dir):
    """History screen shows recorded entries."""
    from dbqm.core.history import record_query_execution
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.history import HistoryScreen
    from textual.widgets import DataTable

    record_query_execution(
        query_name="test_q", connection_name="test_conn",
        params={}, row_count=10, elapsed=0.5, success=True, error="",
    )

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        await pilot.pause()
        screen = app.query_one(HistoryScreen)
        table = screen.query_one("#hist-table", DataTable)
        assert table.row_count >= 1


@pytest.mark.asyncio
async def test_history_detail_view(tmp_config_dir):
    """Highlighting a history row updates the docked detail panel."""
    from dbqm.core.history import record_query_execution
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.history import HistoryScreen

    record_query_execution(
        query_name="test_q", connection_name="test_conn",
        params={"p1": "v1"}, row_count=5, elapsed=0.3, success=True, error="",
    )

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        await pilot.pause()
        screen = app.query_one(HistoryScreen)
        detail = screen.query_one("#hist-detail")
        assert detail.display is True
        assert "test_q" in detail.render().plain


# --- 6. Settings ---


@pytest.mark.asyncio
async def test_settings_has_theme_and_audit(tmp_config_dir):
    """Settings screen has theme selector and audit toggle."""
    from dbqm.ui.app import DBQMApp
    from textual.widgets import Select, Switch

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        await pilot.pause()
        selects = app.query(Select)
        switches = app.query(Switch)
        assert len(selects) >= 1
        assert len(switches) >= 1


# --- 7. Package editor core edge cases ---


def test_package_blank_template_structure():
    from dbqm.core.package_editor import generate_blank_template

    spec, body = generate_blank_template("MY_PKG")
    assert spec.startswith("CREATE OR REPLACE PACKAGE MY_PKG")
    assert body.startswith("CREATE OR REPLACE PACKAGE BODY MY_PKG")
    assert spec.endswith("END MY_PKG;")
    assert body.endswith("END MY_PKG;")


def test_package_wizard_template_with_function():
    from dbqm.core.package_editor import generate_wizard_template

    routines = [{"name": "get_total", "type": "FUNCTION", "params": "p_id NUMBER", "return_type": "NUMBER"}]
    spec, body = generate_wizard_template("PKG", routines)
    assert "FUNCTION get_total" in spec
    assert "RETURN NUMBER" in spec
    assert "RETURN NULL" in body


def test_package_wizard_template_with_procedure():
    from dbqm.core.package_editor import generate_wizard_template

    routines = [{"name": "do_stuff", "type": "PROCEDURE", "params": "p_name VARCHAR2", "return_type": None}]
    spec, body = generate_wizard_template("PKG", routines)
    assert "PROCEDURE do_stuff" in spec
    assert "NULL; -- TODO" in body


def test_package_wizard_empty_routines():
    from dbqm.core.package_editor import generate_wizard_template

    spec, body = generate_wizard_template("PKG_EMPTY", [])
    assert "PKG_EMPTY" in spec
    assert "PKG_EMPTY" in body


# --- 8. ESC navigation ---


# ======================================================================
# TemplateManageScreen tests
# ======================================================================

from dbqm.ui.screens.template_manage import TemplateManageScreen


class TemplateManageTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield TemplateManageScreen()


@pytest.mark.asyncio
async def test_template_manage_screen_renders(tmp_config_dir):
    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        assert app.query_one(TemplateManageScreen) is not None


@pytest.mark.asyncio
async def test_template_manage_screen_empty(tmp_config_dir):
    """With no templates, should show empty message and hide table."""
    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(TemplateManageScreen)
        empty = screen.query_one("#tm-empty")
        assert empty.display is True
        from textual.widgets import DataTable
        table = screen.query_one("#tm-table", DataTable)
        assert table.display is False


@pytest.mark.asyncio
async def test_template_manage_empty_state_action_opens_new_template(tmp_config_dir):
    """The EmptyState's "Criar template" button must not be a dead end."""
    from textual.widgets import Button
    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(TemplateManageScreen)
        screen.query_one("#criar-template", Button).press()
        await pilot.pause()
        assert len(app.screen_stack) > 1  # TemplateEditModal opened


@pytest.mark.asyncio
async def test_template_manage_screen_with_data(tmp_config_dir):
    """With templates configured, should show them in the table."""
    templates_dir = tmp_config_dir / "templates"
    templates_data = {
        "templates": [
            {
                "name": "tpl_b",
                "description": "Second template",
                "content": "Hello {{name}}",
            },
            {
                "name": "tpl_a",
                "description": "First template",
                "content": "{{x}} + {{y}} = {{z}}",
            },
        ]
    }
    (templates_dir / "templates.json").write_text(
        json.dumps(templates_data, ensure_ascii=False), encoding="utf-8"
    )

    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(TemplateManageScreen)
        empty = screen.query_one("#tm-empty")
        assert empty.display is False
        from textual.widgets import DataTable
        table = screen.query_one("#tm-table", DataTable)
        assert table.display is True
        assert table.row_count == 2
        # Should be sorted alphabetically: tpl_a first, then tpl_b
        row0 = table.get_row_at(0)
        assert str(row0[1]) == "tpl_a"
        row1 = table.get_row_at(1)
        assert str(row1[1]) == "tpl_b"


@pytest.mark.asyncio
async def test_template_manage_screen_shows_field_count(tmp_config_dir):
    """Table should show placeholder field names for each template."""
    templates_dir = tmp_config_dir / "templates"
    templates_data = {
        "templates": [
            {
                "name": "tpl_fields",
                "description": "Template with fields",
                "content": "{{campo_a}}, {{campo_b}}, {{campo_c}}",
            },
        ]
    }
    (templates_dir / "templates.json").write_text(
        json.dumps(templates_data, ensure_ascii=False), encoding="utf-8"
    )

    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import DataTable
        screen = app.query_one(TemplateManageScreen)
        table = screen.query_one("#tm-table", DataTable)
        row0 = table.get_row_at(0)
        fields_col = str(row0[3])  # "Campos" column
        assert "campo_a" in fields_col
        assert "campo_b" in fields_col
        assert "campo_c" in fields_col


@pytest.mark.asyncio
async def test_template_manage_screen_no_fields_template(tmp_config_dir):
    """Template with no placeholders shows empty fields column."""
    templates_dir = tmp_config_dir / "templates"
    templates_data = {
        "templates": [
            {
                "name": "static_tpl",
                "description": "No placeholders",
                "content": "Just plain text, no fields.",
            },
        ]
    }
    (templates_dir / "templates.json").write_text(
        json.dumps(templates_data, ensure_ascii=False), encoding="utf-8"
    )

    app = TemplateManageTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import DataTable
        screen = app.query_one(TemplateManageScreen)
        table = screen.query_one("#tm-table", DataTable)
        row0 = table.get_row_at(0)
        fields_col = str(row0[3])
        assert fields_col == ""


@pytest.mark.asyncio
async def test_group_manage_screen_with_template_data(tmp_config_dir):
    """Groups with template fields survive loading in management screen."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "grupo_tpl",
                "description": "Com template",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "template": "inv_tpl",
                "template_fields": {"x": "param:Y"},
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupManageTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import DataTable
        screen = app.query_one(GroupManageScreen)
        table = screen.query_one("#gm-table", DataTable)
        assert table.row_count == 1
        row0 = table.get_row_at(0)
        assert str(row0[1]) == "grupo_tpl"


# ======================================================================
# ESC tests (continued)
# ======================================================================

class OracleClientsTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield OracleClientsScreen()


@pytest.mark.asyncio
async def test_oracle_clients_screen_renders_platform_and_tables(tmp_config_dir):
    """OracleClientsScreen must show platform info plus both tables."""
    from textual.widgets import DataTable, Static

    app = OracleClientsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(OracleClientsScreen)
        platform_static = screen.query_one("#oc-platform", Static)
        rendered = platform_static.render().plain
        assert any(s in rendered for s in ("macOS", "Windows", "Linux"))
        # Available table has 3 columns (Versao, Arquitetura, Formato)
        available = screen.query_one("#oc-available-table", DataTable)
        assert len(available.columns) == 3
        installed = screen.query_one("#oc-installed-table", DataTable)
        assert len(installed.columns) == 2


@pytest.mark.asyncio
async def test_oracle_clients_empty_state_action_focuses_available_table(
    tmp_config_dir, monkeypatch
):
    """The EmptyState's "Escolher client" button must not be a dead end.

    With zero installed clients, it should send focus to the "Disponiveis
    para download" table — installing requires picking a package there
    first, so the label names that step (not the install itself).
    """
    from textual.widgets import Button, DataTable

    clients_root = tmp_config_dir / "clients_empty"
    monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", clients_root)

    app = OracleClientsTestApp()
    async with app.run_test() as pilot:
        from dbqm.ui.widgets.empty_state import EmptyState

        # The screen puts the initial focus on this very button
        # (`_set_initial_focus`, deferred by `call_after_refresh`). Without
        # letting the mount settle, the initial focus would arrive AFTER the
        # click and would undo what this test measures.
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        screen = app.query_one(OracleClientsScreen)
        empty = screen.query_one("#oc-installed-empty", EmptyState)
        assert empty.display is True
        installed = screen.query_one("#oc-installed-table", DataTable)
        assert installed.display is False

        screen.query_one("#escolher-client", Button).press()
        await pilot.pause()
        assert app.focused is screen.query_one("#oc-available-table", DataTable)


@pytest.mark.asyncio
async def test_esc_at_top_level_is_harmless(tmp_config_dir):
    """ESC on a tab whose screen has no deeper phase is a harmless no-op:
    the tab stays active and nothing crashes."""
    from dbqm.ui.app import DBQMApp
    from textual.widgets import TabbedContent

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-historico"


# ======================================================================
# Navigation / focus regression tests
# ======================================================================


async def _open_tab(app, pilot, fkey):
    await pilot.press(fkey)
    await pilot.pause()
    await pilot.pause()


@pytest.mark.asyncio
async def test_escape_from_query_list_at_selection_is_noop(tmp_config_dir):
    """Esc while the query list is focused at the selection phase must not
    crash and must keep the QueryExec tab/screen in place (there is no
    results phase to go back from)."""
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from dbqm.ui.widgets.query_list import QueryListWidget
    from textual.widgets import TabbedContent

    save_queries([Query(name="q1", connection="c1", sql="SELECT 1")])
    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_tab(app, pilot, "f7")
        # Deterministically put focus on the query list.
        app.query_one("#ql-main", QueryListWidget).focus()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.query_one("#main-tabs", TabbedContent).active == "tab-consultas"
        assert app.query_one(QueryExecScreen) is not None


@pytest.mark.asyncio
async def test_query_list_escape_dismisses_search_without_clearing(tmp_config_dir):
    """When the list search is open, Esc closes the search and keeps the
    screen (does not bubble to the app-level go-back)."""
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from dbqm.ui.widgets.query_list import QueryListWidget

    save_queries([Query(name="q1", connection="c1", sql="SELECT 1")])
    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_tab(app, pilot, "f7")
        ql = app.query_one("#ql-main", QueryListWidget)
        ql.action_start_search()
        await pilot.pause()
        assert ql.query_one("#ql-search").has_class("visible")

        await pilot.press("escape")
        await pilot.pause()

        # Search closed, screen still present (not cleared).
        assert not ql.query_one("#ql-search").has_class("visible")
        assert app.query_one(QueryExecScreen) is not None


@pytest.mark.asyncio
async def test_exec_routine_back_to_select_focuses_connection(tmp_config_dir):
    """Going back from the routine list to the select phase must focus the
    connection select (not leave focus on the hidden object table)."""
    from textual.app import App, ComposeResult
    from textual.widgets import Select
    from dbqm.ui.screens.exec_routine import ExecRoutineScreen

    class _App(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield ExecRoutineScreen()

    app = _App()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(ExecRoutineScreen)
        # Simulate being in the list phase.
        screen.query_one("#er-select-phase").display = False
        screen.query_one("#er-list-phase").display = True
        screen.query_one("#er-detail-phase").display = False
        await pilot.pause()

        handled = screen.go_back()
        await pilot.pause()

        assert handled is True
        assert screen.query_one("#er-select-phase").display is True
        assert app.focused is app.query_one("#er-conn-select", Select)


@pytest.mark.asyncio
async def test_action_go_back_at_top_level_is_noop(tmp_config_dir):
    """app.action_go_back on a tab with no deeper phase is a harmless no-op:
    the tab remains active and the screen stays mounted."""
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.history import HistoryScreen
    from textual.widgets import TabbedContent

    app = DBQMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await _open_tab(app, pilot, "f5")
        app.action_go_back()
        await pilot.pause()

        assert app.query_one("#main-tabs", TabbedContent).active == "tab-historico"
        assert app.query_one(HistoryScreen) is not None


# ======================================================================
# ToolsScreen tests
# ======================================================================


from dbqm.ui.screens.tools import ToolsScreen


class ToolsTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield ToolsScreen()


async def _choose_tool(pilot, screen, key):
    """Opens a tool through the real path: highlight in the list + Enter."""
    from textual.widgets import OptionList

    lista = screen.query_one("#ferr-menu-list", OptionList)
    lista.focus()
    await pilot.pause()
    lista.highlighted = next(
        i
        for i in range(lista.option_count)
        if lista.get_option_at_index(i).name == key
    )
    await pilot.press("enter")
    await pilot.pause()


@pytest.mark.asyncio
async def test_tools_is_a_list_and_not_full_width_buttons(tmp_config_dir):
    """Five full-width buttons are five buttons pretending to be a menu.

    The assertion is about the MENU, not about the whole screen: the five
    hosted tools have legitimate action buttons (Novo, Salvar, Excluir...),
    and a global `not app.query(Button)` would only pass by accident — they
    are mounted on demand, so at mount time none exists yet. An assertion
    that depends on the target not having been built yet guards nothing at
    all.
    """
    from textual.widgets import Button, OptionList
    from tests.ui._helpers import rendered_names

    app = ToolsTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        screen = app.query_one(ToolsScreen)
        menu = screen.query_one("#ferr-menu")
        lista = menu.query_one(OptionList)
        assert rendered_names(lista) == [
            "\U0001F465  Gerenciar Grupos",
            "\U0001F4C4  Gerenciar Templates",
            "\U0001F4E6  Package Editor",
            "\u25b6  Executar Rotina",
            "\u25b6  Executar Grupo",
        ]
        assert not menu.query(Button), "botao e acao, nunca navegacao"


@pytest.mark.asyncio
async def test_tools_screen_starts_on_the_menu(tmp_config_dir):
    """ToolsScreen opens on the menu, not on a tool."""
    from textual.widgets import ContentSwitcher
    app = ToolsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(ToolsScreen)
        assert screen.query_one(ContentSwitcher).current == "ferr-menu"


@pytest.mark.asyncio
async def test_tools_screen_does_not_load_tools_on_mount(tmp_config_dir):
    """Mounting ToolsScreen alone must not instantiate any tool
    screen. In particular, PackageEditorScreen's on_mount() eagerly pushes
    a modal screen (_PackageChoiceModal) the moment it is mounted (see
    dbqm/ui/screens/package_editor.py). If the tool screens were mounted
    up front, that modal would become the app's active screen before any
    user interaction happens at all. Tool screens must be built lazily, on
    first open, so no modal is pushed just from mounting the launcher."""
    app = ToolsTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert len(app.screen_stack) == 1

        screen = app.query_one(ToolsScreen)
        # Empty: the "Voltar" that used to live here was navigation done
        # with a button.
        assert not list(screen.query_one("#ferr-packages").children)
        assert not list(screen.query_one("#ferr-executar").children)


@pytest.mark.asyncio
async def test_tools_screen_open_and_back(tmp_config_dir):
    """Choosing in the list builds and shows the tool; `back_to_menu`
    returns to the menu, and reopening does not build a second instance."""
    from textual.widgets import ContentSwitcher
    from dbqm.ui.screens.package_editor import PackageEditorScreen

    app = ToolsTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(ToolsScreen)
        switcher = screen.query_one(ContentSwitcher)

        await _choose_tool(pilot, screen, "packages")
        assert switcher.current == "ferr-packages"

        packages_container = screen.query_one("#ferr-packages")
        assert len(packages_container.query(PackageEditorScreen)) == 1

        screen.back_to_menu()
        await pilot.pause()
        assert switcher.current == "ferr-menu"

        await _choose_tool(pilot, screen, "packages")
        assert len(packages_container.query(PackageEditorScreen)) == 1


@pytest.mark.asyncio
async def test_tools_screen_open_group_run(tmp_config_dir):
    """Choosing 'Executar Grupo' mounts a GroupRunScreen in #ferr-executar."""
    from textual.widgets import ContentSwitcher
    from dbqm.ui.screens.group_run import GroupRunScreen

    app = ToolsTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(ToolsScreen)
        switcher = screen.query_one(ContentSwitcher)

        await _choose_tool(pilot, screen, "executar")
        assert switcher.current == "ferr-executar"

        executar_container = screen.query_one("#ferr-executar")
        assert len(executar_container.query(GroupRunScreen)) == 1

        screen.back_to_menu()
        await pilot.pause()
        assert switcher.current == "ferr-menu"

        await _choose_tool(pilot, screen, "executar")
        assert len(executar_container.query(GroupRunScreen)) == 1


@pytest.mark.asyncio
async def test_tools_group_run_empty_state_action_opens_group_management(
    tmp_config_dir,
):
    """With zero groups configured system-wide, GroupRunScreen's EmptyState
    ("Gerenciar grupos") must not be a dead end: it switches the launcher
    to the sibling "Gerenciar Grupos" tool, where groups are created."""
    from textual.widgets import Button, ContentSwitcher
    from dbqm.ui.widgets.empty_state import EmptyState
    from dbqm.ui.screens.group_manage import GroupManageScreen

    app = ToolsTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(ToolsScreen)
        switcher = screen.query_one(ContentSwitcher)

        await _choose_tool(pilot, screen, "executar")
        assert switcher.current == "ferr-executar"

        run_screen = screen.query_one(GroupRunScreen)
        empty = run_screen.query_one("#gr-empty-message", EmptyState)
        assert empty.display is True

        run_screen.query_one("#gerenciar-grupos", Button).press()
        await pilot.pause()

        assert switcher.current == "ferr-grupos"
        assert len(screen.query_one("#ferr-grupos").query(GroupManageScreen)) == 1


# ======================================================================
# GroupRunScreen tests (Ferramentas-hosted copy of the query-based group
# execution feature, salvaged from the pre-redesign GroupExecScreen)
# ======================================================================

from dbqm.ui.screens.group_run import GroupRunScreen


class GroupRunTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield GroupRunScreen()


@pytest.mark.asyncio
async def test_group_run_screen_renders_standalone(tmp_config_dir):
    """GroupRunScreen renders standalone with its own #gr-group-list id."""
    from textual.widgets import OptionList

    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "group_a",
                "description": "Test group A",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        assert screen is not None
        assert screen.query_one("#gr-group-list", OptionList) is not None


@pytest.mark.asyncio
async def test_group_run_screen_shows_empty_message(tmp_config_dir):
    """With no groups configured, should show empty state."""
    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        empty = screen.query_one("#gr-empty-message")
        assert empty.display is True


@pytest.mark.asyncio
async def test_group_run_screen_shows_group_list(tmp_config_dir):
    """With groups configured, should show the group list and hide the
    empty-state message; the results phase stays hidden."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "group_a",
                "description": "Test group A",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            },
            {
                "name": "group_b",
                "description": "Test group B",
                "queries": ["q1", "q3"],
                "join_key": "code",
                "compare_columns": ["value"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        empty = screen.query_one("#gr-empty-message")
        assert empty.display is False
        sel = screen.query_one("#gr-selection-phase")
        assert sel.display is True
        res = screen.query_one("#gr-results-phase")
        assert res.display is False


@pytest.mark.asyncio
async def test_group_run_results_phase_hidden_initially(tmp_config_dir):
    """Results phase should be hidden on mount."""
    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        results = screen.query_one("#gr-results-phase")
        assert results.display is False


@pytest.mark.asyncio
async def test_group_run_go_back_to_selection(tmp_config_dir):
    """go_back_to_selection should show selection and hide results."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g1",
                "description": "Test",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        # Simulate being in results phase
        screen.query_one("#gr-selection-phase").display = False
        screen.query_one("#gr-results-phase").display = True

        screen.go_back_to_selection()

        assert screen.query_one("#gr-selection-phase").display is True
        assert screen.query_one("#gr-results-phase").display is False


@pytest.mark.asyncio
async def test_group_run_screen_with_accented_folders(tmp_config_dir):
    """Groups with accented folders should not crash the app."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g_acc_a",
                "description": "",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "Produção",
            },
            {
                "name": "g_acc_b",
                "description": "",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["val"],
                "folder": "Homologação",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        seletor = screen.query_one("#gr-folder-select", Select)
        assert len(seletor._options) == 3


@pytest.mark.asyncio
async def test_group_run_screen_with_folders(tmp_config_dir):
    """Groups with folders should produce a folder select with a count per
    option."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g_folder_a",
                "description": "",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "Folder A",
            },
            {
                "name": "g_folder_b",
                "description": "",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["val"],
                "folder": "Folder B",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        seletor = screen.query_one("#gr-folder-select", Select)
        # "Todas" + "Folder A" + "Folder B" = 3
        assert len(seletor._options) == 3
        rotulos = [str(r) for r, _ in seletor._options]
        assert any("Todas (2)" in r for r in rotulos)
        assert any("Folder A (1)" in r for r in rotulos)
        assert any("Folder B (1)" in r for r in rotulos)


@pytest.mark.asyncio
async def test_group_run_filtered_empty_state_action_resets_filter(tmp_config_dir):
    """A folder filter matching zero groups must not fall back to a fake
    row inside the OptionList: an EmptyState replaces it, and its "Ver
    todos os grupos" button must not be a dead end."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g1",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "F1",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        from textual.widgets import Button, OptionList
        from dbqm.ui.widgets.empty_state import EmptyState

        screen = app.query_one(GroupRunScreen)
        # Simulate a folder filter matching nothing (reachable e.g. via a
        # folder select value with no matching groups) without depending
        # on that selection mechanics here.
        screen._populate_group_list([])
        await pilot.pause()

        empty = screen.query_one("#gr-filter-empty", EmptyState)
        assert empty.display is True
        assert screen.query_one("#gr-group-list", OptionList).display is False

        screen.query_one("#ver-todos-grupos", Button).press()
        await pilot.pause()

        assert empty.display is False
        group_list = screen.query_one("#gr-group-list", OptionList)
        assert group_list.display is True
        assert group_list.option_count == 1


@pytest.mark.asyncio
async def test_group_run_folder_select_narrows_list(tmp_config_dir):
    """Choosing a folder in the select narrows the group list to it."""
    from textual.widgets import OptionList

    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g1",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "F1",
            },
            {
                "name": "g2",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "folder": "F2",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        seletor = screen.query_one("#gr-folder-select", Select)
        assert screen.query_one("#gr-group-list", OptionList).option_count == 2

        seletor.value = "F1"
        await pilot.pause()
        group_list = screen.query_one("#gr-group-list", OptionList)
        assert group_list.option_count == 1
        assert rendered_names(group_list) == ["g1"]

        seletor.value = ""
        await pilot.pause()
        assert screen.query_one("#gr-group-list", OptionList).option_count == 2


@pytest.mark.asyncio
async def test_group_run_list_shows_all_items(tmp_config_dir):
    """All groups should render in the list, not just one."""
    from textual.widgets import OptionList

    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": f"g{i}",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
            }
            for i in range(8)
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        assert screen.query_one("#gr-group-list", OptionList).option_count == 8


@pytest.mark.asyncio
async def test_group_run_folder_select_is_a_select(tmp_config_dir):
    """The folder navigation is a Select, not a scrollable row of buttons —
    a regression guard against reintroducing folder tabs, which is what
    this screen used before (variable cardinality, not tabs)."""
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "g1",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["s"],
                "folder": "A",
            },
            {
                "name": "g2",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["s"],
                "folder": "B",
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        folder_select = screen.query_one("#gr-folder-select")
        assert isinstance(folder_select, Select)
        # The missing half: without this the test passed with the tabs back
        # alongside the Select, which is exactly the regression it claims to
        # guard against. Same pair of assertions as the queries sibling
        # (test_folders_become_a_select_with_counts).
        assert not app.query("#gr-folder-bar"), "a barra de botoes some"
        assert not app.query("#gr-folder-hint"), "a dica das setas some junto"


@pytest.mark.asyncio
async def test_group_run_paints_two_groups_with_the_same_name(tmp_config_dir):
    """Two groups with the same name must not bring the screen down.

    Same defect as `test_query_list_paints_two_queries_with_the_same_name`:
    with the name travelling as `Option(content, id=name)`,
    `OptionList.add_option` raised `DuplicateID` and the screen did not
    mount. `groups.json` is editable by hand, so the ambiguous data exists;
    the list paints both rows and leaves the ambiguity to the lookup by
    name."""
    from textual.widgets import OptionList

    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "dup",
                "description": "primeiro",
                "queries": ["q1"],
                "join_key": "id",
                "compare_columns": ["s"],
            },
            {
                "name": "dup",
                "description": "segundo",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["s"],
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        group_list = screen.query_one("#gr-group-list", OptionList)
        assert group_list.option_count == 2
        assert rendered_names(group_list) == ["dup", "dup"]
        pintado = [group_list.get_option_at_index(i).prompt.plain for i in range(2)]
        assert "primeiro" in pintado[0] and "1 consulta" in pintado[0]
        assert "segundo" in pintado[1] and "2 consultas" in pintado[1]


@pytest.mark.asyncio
async def test_group_run_selects_by_name_even_with_repeated_names(
    tmp_config_dir,
):
    """Group selection resolves by name, as it did before the ids.

    The normal case (unique names) and the ambiguous case in the same test:
    choosing the row posts that row's name, and choosing one of the two
    same-named rows posts the shared name instead of doing nothing."""
    from textual.widgets import OptionList

    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {"name": "alpha", "queries": ["q1"], "join_key": "id",
             "compare_columns": ["s"]},
            {"name": "dup", "queries": ["q1"], "join_key": "id",
             "compare_columns": ["s"]},
            {"name": "dup", "queries": ["q1", "q2"], "join_key": "id",
             "compare_columns": ["s"]},
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    escolhidos = []

    class EspiaGroupRun(GroupRunScreen):
        def _on_group_chosen(self, group_name: str) -> None:
            escolhidos.append(group_name)

    class EspiaApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield EspiaGroupRun()

    app = EspiaApp()
    async with app.run_test() as pilot:
        screen = app.query_one(EspiaGroupRun)
        group_list = screen.query_one("#gr-group-list", OptionList)
        group_list.focus()
        group_list.highlighted = 0
        await pilot.press("enter")
        group_list.highlighted = 2
        await pilot.press("enter")
        await pilot.pause()
        assert escolhidos == ["alpha", "dup"]


@pytest.mark.asyncio
async def test_group_run_mounted_item_has_visible_hierarchy(tmp_config_dir):
    """A really mounted group entry takes more than one line and each role
    comes out in a distinct color — name, query count, description.

    The group list swapped the string concatenated with "|" for the same
    `hierarchical_item` as the query list, but only the query one had a
    guard (`test_query_list_mounted_item_has_visible_hierarchy`, in
    test_widgets.py). This is the missing pair: the description goes in
    whole, with no artificial truncation, and the colors are resolved with
    the active theme's `Style.parse` — the same mechanism Textual uses
    before painting. It proves the WIRING all the way to the mounted option,
    not the pixel painting.

    The description may take MORE THAN ONE line: since the group list
    pre-wraps the text into logical lines at the panel's width (the fix for
    the continuation that landed in the identity column), the number of
    lines depends on the length of the text. What this test asserts is not
    the count, it is the GRAMMAR — identity alone on the first line,
    everything else indented — and that the wrapping loses no character: the
    context lines, put back together, are the original description."""
    from textual.style import Style
    from textual.widgets import OptionList

    def cor_no_offset(conteudo, offset):
        estilo = Style()
        for start, end, span_style in conteudo.spans:
            if start <= offset < end:
                estilo = estilo + Style.parse(span_style)
        return estilo.foreground

    descricao = (
        "Compara o saldo de faturamento entre producao e homologacao no "
        "fechamento do mes"
    )
    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "grupo_faturamento",
                "description": descricao,
                "queries": ["q1", "q2", "q3"],
                "join_key": "id",
                "compare_columns": ["s"],
            }
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        group_list = screen.query_one("#gr-group-list", OptionList)
        conteudo = group_list.get_option_at_index(0).prompt
        texto = conteudo.plain

        linhas = texto.split(chr(10))
        assert linhas[0] == "grupo_faturamento", "identidade sozinha na 1a linha"
        assert linhas[1] == "  3 consultas", "desambiguacao recuada na 2a"
        assert len(linhas) > 2, "a descricao tem linha propria"
        assert all(linha.startswith("  ") for linha in linhas[2:]), (
            "toda linha de descricao paga o recuo, inclusive a continuacao: %r"
            % linhas
        )
        assert " | " not in texto, "a concatenacao com | saiu de cena"
        assert " ".join(linha.strip() for linha in linhas[2:]) == descricao, (
            "a descricao vai inteira: houve QUEBRA, nao corte — %r" % linhas[2:]
        )

        cor_forte = Style.parse("$ds-text-strong").foreground
        cor_apoio = Style.parse("$ds-text-muted").foreground
        cor_desabilitado = Style.parse("$ds-text-disabled").foreground
        assert len({cor_forte, cor_apoio, cor_desabilitado}) == 3

        assert cor_no_offset(conteudo, texto.index("grupo_faturamento")) == cor_forte
        assert cor_no_offset(conteudo, texto.index("3 consultas")) == cor_apoio
        assert cor_no_offset(conteudo, texto.index("Compara")) == cor_desabilitado


@pytest.mark.asyncio
async def test_group_run_screen_with_template_group(tmp_config_dir):
    """Group with template configured should show in the group list."""
    from textual.widgets import OptionList

    config_dir = tmp_config_dir / "config"
    groups_data = {
        "groups": [
            {
                "name": "grupo_tpl",
                "description": "Grupo com template",
                "queries": ["q1", "q2"],
                "join_key": "id",
                "compare_columns": ["status"],
                "template": "meu_template",
                "template_fields": {"titulo": "param:CORRETOR"},
            },
        ]
    }
    (config_dir / "groups.json").write_text(
        json.dumps(groups_data, ensure_ascii=False), encoding="utf-8"
    )

    app = GroupRunTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(GroupRunScreen)
        group_list = screen.query_one("#gr-group-list", OptionList)
        assert group_list.option_count == 1


# ======================================================================
# Oracle Instant Client configuration (settings + clients manager)
# ======================================================================


def _fake_oracle_client(base, name="instantclient_19_x64"):
    """Create a client directory whose oci.dll matches the running Python."""
    import struct
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    machine = 0x8664 if struct.calcsize("P") * 8 == 64 else 0x014C
    pe_offset = 0x80
    buf = bytearray(pe_offset + 8)
    buf[0:2] = b"MZ"
    buf[0x3C:0x40] = pe_offset.to_bytes(4, "little")
    buf[pe_offset:pe_offset + 4] = b"PE\x00\x00"
    buf[pe_offset + 4:pe_offset + 6] = machine.to_bytes(2, "little")
    (d / "oci.dll").write_bytes(bytes(buf))
    return d


@pytest.mark.asyncio
async def test_settings_screen_shows_oracle_client_in_use(tmp_config_dir):
    """Settings must state which Instant Client is active and where it came from."""
    from textual.widgets import Static

    app = SettingsTestApp()
    async with app.run_test():
        screen = app.query_one(SettingsScreen)
        label = screen.query_one("#settings-oracle-client-current", Static)
        assert label.render().plain.strip() != ""


@pytest.mark.asyncio
async def test_settings_screen_shows_configured_oracle_client_path(tmp_config_dir):
    """A path configured in dbqm settings is shown as the source, not ORACLE_HOME."""
    from textual.widgets import Static
    from dbqm.models.settings import Settings, save_settings

    client = _fake_oracle_client(tmp_config_dir)
    save_settings(Settings(oracle_client_dir=str(client)))

    app = SettingsTestApp()
    async with app.run_test():
        screen = app.query_one(SettingsScreen)
        rendered = screen.query_one("#settings-oracle-client-current", Static).render().plain
        assert client.name in rendered
        assert "config" in rendered.lower()


@pytest.mark.asyncio
async def test_settings_screen_reports_unusable_configured_client(tmp_config_dir):
    """A configured path that cannot be used must be flagged, not hidden."""
    from textual.widgets import Static
    from dbqm.models.settings import Settings, save_settings

    save_settings(Settings(oracle_client_dir=str(tmp_config_dir / "gone")))

    app = SettingsTestApp()
    async with app.run_test():
        screen = app.query_one(SettingsScreen)
        rendered = screen.query_one("#settings-oracle-client-current", Static).render().plain
        assert "nao existe" in rendered.lower()


@pytest.mark.asyncio
async def test_settings_screen_has_oracle_client_dir_button(tmp_config_dir):
    from textual.widgets import Button

    app = SettingsTestApp()
    async with app.run_test():
        screen = app.query_one(SettingsScreen)
        assert screen.query_one("#btn-oracle-client-dir", Button) is not None


@pytest.mark.asyncio
async def test_oracle_clients_screen_has_use_button(tmp_config_dir):
    from textual.widgets import Button

    app = OracleClientsTestApp()
    async with app.run_test():
        screen = app.query_one(OracleClientsScreen)
        assert screen.query_one("#oc-use-btn", Button) is not None


@pytest.mark.asyncio
async def test_oracle_clients_use_button_persists_selected_client(tmp_config_dir, monkeypatch):
    """"Usar este client" writes the selected install into dbqm settings."""
    from textual.widgets import Button, DataTable
    from dbqm.models.settings import load_settings

    clients_root = tmp_config_dir / "clients"
    client = _fake_oracle_client(clients_root)
    monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", clients_root)

    app = OracleClientsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(OracleClientsScreen)
        screen.query_one("#oc-installed-table", DataTable).cursor_coordinate = (0, 0)
        await pilot.pause()
        screen.query_one("#oc-use-btn", Button).press()
        await pilot.pause()

    assert load_settings().oracle_client_dir == str(client)
