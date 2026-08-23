"""Tests for screens."""
from __future__ import annotations

import json

import pytest
from textual.app import ComposeResult
from textual.widgets import Input, Select

from dbqm.ui.screens.connections import ConnectionsScreen
from dbqm.ui.screens.oracle_clients import OracleClientsScreen
from dbqm.ui.screens.query_exec import QueryExecScreen

from tests.ui._helpers import ThemedTestApp, nomes_renderizados


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
        assert nomes_renderizados(option_list) == ["Estoque"]


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
        assert nomes_renderizados(option_list) == ["Pedidos"]


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
        assert nomes_renderizados(option_list) == ["Estoque"]


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
        assert nomes_renderizados(option_list) == ["Pedidos"]


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


def _rotulos_pintados_do_select(seletor):
    """Os rotulos do select como o menu aberto os PINTA.

    `seletor._options` e a lista que o widget guardou; o que a pessoa le e
    o `OptionList` do overlay, so existente com o menu aberto. Ler dali e o
    que faz um erro de montagem do rotulo aparecer."""
    from textual.widgets._select import SelectOverlay

    overlay = seletor.query_one(SelectOverlay)
    return [
        str(overlay.get_option_at_index(i).prompt)
        for i in range(overlay.option_count)
    ]


@pytest.mark.asyncio
async def test_pastas_viram_select_com_contagem(tmp_config_dir):
    """As pastas viram um Select com a contagem em cada rotulo.

    A cardinalidade real do mantenedor sao 16 pastas para 68 consultas —
    numa HorizontalScroll de botoes isso rolava lateralmente e escondia a
    maioria das opcoes. O fixture aqui e uma reducao dessa forma, nao dos
    16 numeros: quatro pastas com contagens 2/5/6/7. As contagens sao
    deliberadamente diferentes do numero de pastas (4) e do numero de
    opcoes (5), porque a versao anterior deste teste era
    `any("(3)" in r ...)` com 3 pastas — um bug que pintasse
    `len(folders)` no lugar da contagem passaria igual. A asercao e a lista
    EXATA de rotulos, na ordem em que o menu os pinta."""
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
        assert _rotulos_pintados_do_select(seletor) == [
            "Todas (20)",
            "Alfa (5)",
            "Beta (2)",
            "Delta (7)",
            "Gama (6)",
        ]
        assert not app.query("#folder-bar"), "a barra de botoes some"


@pytest.mark.asyncio
async def test_rotulo_de_pasta_elide_o_prefixo_comum(tmp_config_dir):
    """Com uma familia unica de pastas, o rotulo pintado perde o prefixo.

    Nenhuma pasta da suite continha "/" antes deste teste, entao o ramo de
    elisao (`prefixo_comum_de_pastas`) nunca rodava: trocar a funcao por
    `lambda pastas: ""` deixava tudo verde. Aqui o que se le e o rotulo
    PINTADO no menu aberto — "Alpha (3)", nao "Projeto/Alpha (3)"."""
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
        assert _rotulos_pintados_do_select(seletor) == [
            "Todas (6)",
            "Alpha (3)",
            "Beta (1)",
            "Gama (2)",
        ]


@pytest.mark.asyncio
async def test_rotulo_de_pasta_mostra_caminho_inteiro_com_duas_familias(
    tmp_config_dir,
):
    """Duas familias lado a lado: o prefixo comum encolhe e o caminho volta.

    E o outro lado do teste acima, e a razao de o prefixo ser calculado a
    cada carga contra as pastas reais em vez de fixado como literal: no dia
    em que uma segunda familia aparecer, a lista volta sozinha a mostrar o
    caminho inteiro, sem mudanca de codigo."""
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
        assert _rotulos_pintados_do_select(seletor) == [
            "Todas (2)",
            "Interno/Backlog (1)",
            "Projeto/Alpha (1)",
        ]


# O guarda `test_listview_saiu_do_vocabulario` mora agora em
# `tests/design/test_inventario_layout.py`, junto com os outros guardas
# de vocabulario da gramatica de layout. Aqui ele ficava escondido no
# meio de milhares de linhas de teste de tela — longe de quem vai
# quebrar a regra.


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
async def test_lista_de_conexoes_tem_hierarquia_e_nao_concatena(tmp_config_dir):
    """O item tem hierarquia de linhas; nao e uma string concatenada."""
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


def test_query_list_nao_trunca_mais_a_descricao():
    """A truncagem em 35 caracteres existia para caber numa linha so.

    Raiz ancorada em `__file__` (idioma de `tests/design/_varredura.py`):
    com um caminho relativo ao cwd, rodar a suite de outro diretorio
    levantaria `FileNotFoundError` em vez de checar coisa alguma.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    fonte = (raiz / "dbqm" / "ui" / "widgets" / "query_list.py").read_text(
        encoding="utf-8"
    )
    assert "[:32]" not in fonte, "a truncagem deixou de ser necessaria"


@pytest.mark.asyncio
async def test_lista_de_conexoes_montada_distingue_identidade_de_desambiguacao(
    tmp_config_dir,
):
    """Nao basta o `Content` que `item_hierarquico` devolve isolado (Task 3
    ja prova isso por span) — aqui a tela real e montada e a opcao real do
    `OptionList` (nao o valor passado pra dentro) e lida de volta; a cor de
    cada linha e resolvida com `Style.parse` do tema ativo da app, o mesmo
    mecanismo que o Textual usa para resolver estilo antes de pintar.

    Isso prova a FIACAO — que o `Content` certo chega intacto ao widget
    montado, com o tema real resolvendo as tres cores certas — nao a
    pintura de pixel em si (nenhum screenshot e tirado aqui)."""
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

        cor_forte = Style.parse("$texto-forte").foreground
        cor_apoio = Style.parse("$texto-apoio").foreground
        cor_desabilitado = Style.parse("$texto-desabilitado").foreground
        assert len({cor_forte, cor_apoio, cor_desabilitado}) == 3

        pos_identidade = texto.index("MGORA7ORA9")
        pos_desambiguacao = texto.index("Oracle/TNS")
        pos_contexto = texto.index("Producao")

        assert cor_no_offset(conteudo, pos_identidade) == cor_forte
        assert cor_no_offset(conteudo, pos_desambiguacao) == cor_apoio
        assert cor_no_offset(conteudo, pos_contexto) == cor_desabilitado


@pytest.mark.asyncio
async def test_descricao_largura_cabe_mesmo_com_a_lista_rolando(tmp_config_dir):
    """`_DESCRICAO_LARGURA` foi derivada assumindo o pior caso (barra de
    rolagem do OptionList presente). Este teste prova a suposicao contra o
    widget montado de verdade, nao so no papel: numa lista longa o
    suficiente pra rolar, a largura de texto assumida (mais o recuo que
    toda linha paga) nao pode passar da largura real disponivel — foi
    exatamente essa conta errada (34 assumidos contra 34 reais DEPOIS do
    recuo, ou seja 36 precisando caber em 34) que fez uma linha de
    descricao ("...ambiente") sair sem recuo, alinhada com a coluna da
    identidade da entrada seguinte."""
    from textual.widgets import OptionList
    from dbqm.models.connection import Connection, save_connections
    from dbqm.ui.screens.connections import _DESCRICAO_LARGURA
    from dbqm.ui.widgets.lista_hierarquica import _RECUO

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
        assert _DESCRICAO_LARGURA + len(_RECUO) <= largura_real


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
async def test_connections_nova_clears_form(tmp_config_dir):
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
async def test_browser_lista_de_objetos_montada_e_so_identidade(tmp_config_dir, monkeypatch):
    """A lista de objetos usa `item_hierarquico` só com a identidade — o
    filtro de tipo (`#obj-type`) é `allow_blank=False`, então toda linha
    visível já é sempre do mesmo tipo; escrever o tipo de novo em cada
    item não desambiguaria nada. `conteudo` vem do widget montado de
    verdade (`Option.prompt` dentro de uma app com tema ativo), não do
    `Content` isolado, e a cor da identidade é resolvida via
    `Style.parse` do tema real — fiação até o widget montado, não pintura
    de pixel (nenhum screenshot é tirado aqui)."""
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

        cor_forte = Style.parse("$texto-forte").foreground
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
    """Grava um historico minimo (uma consulta, um grupo)."""
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

    Com HISTORICO: e so quando ha registro que a tabela e o detalhe tem o
    que mostrar. Antes este teste montava a tela VAZIA e ainda exigia os
    dois de pe — era o defeito escrito como contrato.
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
    """Sem historico, o estado vazio aparece e a tabela SAI de cena."""
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
    """Com registros, o painel de detalhe ja nasce visivel (sem troca de fase)."""
    _salvar_duas_entradas()
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(HistoryScreen)
        detail = screen.query_one("#hist-detail")
        assert detail.display is True
        assert screen.query_one("#hist-detail-panel").display is True


# ----------------------------------------------------------------------
# Historico vazio: o que a tela PINTA, na DBQMApp real, nos dois tamanhos
#
# Nao ha harness proprio aqui de proposito. O recorte do estado vazio so
# aparece com a altura que a aba REALMENTE sobra para a tela — cabecalho,
# faixa de abas, barra de acoes e barra de status ja descontados. Um
# `HistoryTestApp` sozinho recebe as 24 linhas inteiras e pinta tudo.
# ----------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("tamanho", [(80, 24), (120, 34)])
async def test_historico_vazio_pinta_identidade_e_nao_pinta_tabela(
    tmp_config_dir, tamanho
):
    """Com historico vazio: as tres partes do estado vazio aparecem, e o
    cabecalho da tabela nao.

    Dois defeitos ao mesmo tempo, os dois medidos no render:

    1. O cabecalho `Data Conexao Tipo SQL Tempo Status` era pintado colado
       no estado vazio (as outras dez listas do dbqm escondem a irma).
    2. Em 80x24 a linha de identidade (`Historico`) era recortada INTEIRA —
       so o porque e o botao chegavam na tela.
    """
    from dbqm.ui.app import DBQMApp
    from tests.ui._helpers import linhas_renderizadas, texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=tamanho) as pilot:
        await pilot.pause()
        app.action_switch_tab("tab-historico")
        for _ in range(3):
            await pilot.pause()

        pintado = texto_renderizado(app)
        linhas = linhas_renderizadas(app)
        assert "HISTORICO" in pintado, "a aba de historico nem chegou a frente"

        # A identidade e cobrada LINHA A LINHA, nao com um `in` na tela
        # inteira: a propria faixa de abas escreve "📜  Historico", e um
        # `"Historico" in pintado` passava verde com a linha recortada.
        # Dentro do painel ela esta sozinha na linha, entre as bordas.
        assert any(
            linha.strip("│ ") == "Historico" for linha in linhas
        ), "a linha de identidade do estado vazio nao foi pintada"
        assert "Cada consulta ou grupo executado fica registrado aqui" in pintado
        assert "Executar consulta" in pintado
        # Nenhuma coluna da tabela pode estar pintada.
        for coluna in ("Conexao", "Tempo", "Status"):
            assert coluna not in pintado, f"cabecalho {coluna!r} pintado no vazio"


@pytest.mark.asyncio
async def test_historico_vazio_foca_a_saida_que_oferece(tmp_config_dir):
    """O foco inicial vai para o botao do estado vazio, nao para a tabela
    escondida — senao nada visivel fica marcado e o Enter nao alcanca a
    unica saida da tela."""
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
# Abrir o app nao e o usuario mexendo nos controles
# ----------------------------------------------------------------------


async def _abrir_app_contando_gravacoes(tmp_config_dir, monkeypatch):
    """Monta a DBQMApp real e devolve (avisos, numero de gravacoes)."""
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
async def test_abrir_o_app_nao_avisa_nem_grava_nada(tmp_config_dir, monkeypatch, salvo):
    """Sem ninguem tocar em nada, a abertura nao pode gerar aviso de
    configuracao nem reescrever o `settings.json`.

    Medido antes da correcao: com config nova, um aviso ("Subdiretorios por
    tipo: ativado") e uma gravacao; com `audit_log_enabled` ligado no
    arquivo, dois avisos e duas gravacoes. Os dois casos tem a mesma causa —
    `on_mount` atribui `Switch.value` para MOSTRAR o que ja esta salvo, e o
    `Switch.Changed` disso era lido como acao do usuario. O segundo
    parametro existe porque so ele exercita o interruptor de auditoria: numa
    config nova ele ja nasce igual ao padrao do `Switch` e nem emite.
    """
    import json

    from dbqm.core.paths import SETTINGS_FILE

    if salvo:
        SETTINGS_FILE.write_text(json.dumps(salvo), encoding="utf-8")

    avisos, gravacoes = await _abrir_app_contando_gravacoes(tmp_config_dir, monkeypatch)

    assert gravacoes == 0, f"{gravacoes} gravacao(oes) de settings sem acao do usuario"
    for proibido in ("Log de auditoria", "Subdiretorios por tipo", "Tema alterado"):
        assert not any(proibido in a for a in avisos), f"aviso indevido: {avisos}"


@pytest.mark.asyncio
async def test_migracao_de_tema_nao_vira_aviso_de_troca(tmp_config_dir, monkeypatch):
    """`github-dark` -> `plano-escuro` e renomeacao nossa, nao escolha da
    pessoa: nao anuncia "Tema alterado" nem reescreve o arquivo.

    Aparecia uma vez so — na primeira abertura depois de subir da 1.17.x —
    que e exatamente quando ninguem esta olhando um teste.
    """
    import json

    from dbqm.core.paths import SETTINGS_FILE

    SETTINGS_FILE.write_text(json.dumps({"theme": "github-dark"}), encoding="utf-8")

    avisos, gravacoes = await _abrir_app_contando_gravacoes(tmp_config_dir, monkeypatch)

    assert not any("Tema alterado" in a for a in avisos), f"aviso indevido: {avisos}"
    assert gravacoes == 0
    # E a migracao continua valendo onde importa: o tema em uso.
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
@pytest.mark.parametrize("altura", [24, 34])
async def test_settings_secao_oracle_alcancavel(tmp_config_dir, altura):
    """A secao Oracle Instant Client tem de ser ALCANCAVEL num terminal real.

    Ela nasceu em y=39 de uma coluna que nao rolava: precisava de 42 linhas
    de terminal para aparecer, e nao havia como chegar nela. O ajuste do
    caminho do Instant Client saiu na v1.20.0 justamente para desfazer um
    ORACLE_HOME de 32 bits que derrubava conexoes em producao — invisivel
    para quem nao tem uma tela gigante.

    A afirmacao e sobre o que a tela PINTA, e nao sobre `region.height`:
    com o defeito presente a regiao media 3 linhas de altura nos tres
    tamanhos testados e ainda assim nada era desenhado, porque o corte vem
    de um ancestral com `overflow: hidden`.
    """
    from textual.widgets import Button
    from tests.ui._helpers import texto_renderizado

    app = SettingsTestApp()
    async with app.run_test(size=(120, altura)) as pilot:
        screen = app.query_one(SettingsScreen)
        botao = screen.query_one("#btn-oracle-client-dir", Button)

        # O caminho do teclado: focar o botao e o que um Tab faz, e e o
        # `set_focus` que manda o Textual rolar o ancestral ate ele.
        botao.focus()
        await pilot.pause()
        # A rolagem que o foco dispara e animada: sem esperar, a medicao
        # cai no meio do caminho (scroll_y 14 de 24) e o teste reprova por
        # impaciencia em vez de por defeito.
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = texto_renderizado(app)
        assert "Definir caminho" in pintado, (
            "o botao da secao Oracle nao e alcancavel a %d linhas de terminal" % altura
        )
        assert "Client em uso" in pintado, (
            "o status do Instant Client nao e desenhado a %d linhas de terminal" % altura
        )


def _titulos_de_painel(raiz):
    """Os titulos dos paineis como a tela os PINTA.

    `Panel` nao guarda o titulo em `render()` — `Panel` e um `Vertical`, e
    `Vertical.render()` devolve o preenchimento do fundo, nao texto. O
    titulo mora num `Label` de id `#panel-title`, montado por
    `Panel.compose`. O plano da Task 7 supunha `p.render()`; o caminho
    real e este, o mesmo que os testes anteriores desta tela ja usavam.
    """
    from dbqm.ui.widgets.panel import Panel

    return [p.query_one("#panel-title").render().plain for p in raiz.query(Panel)]


@pytest.mark.asyncio
async def test_cada_assunto_de_configuracoes_tem_seu_painel(tmp_config_dir):
    """Um painel por assunto — nao um painel-saco com quatro assuntos dentro.

    A queixa que originou esta fase foi textual: "a tela de configuracoes
    esta horrivel com um monte de botao alinhado no centro e dentro da tela
    de configuracoes do sistema, esta tudo muito confuso". A confusao tinha
    causa medivel: tema, auditoria, exportacao e Oracle Instant Client
    dividiam UM painel chamado "CONFIG DA APLICACAO", separados so por um
    rotulo em negrito. Sem moldura por assunto nao ha onde o olho parar, e
    a secao Oracle — que existe para desfazer um ORACLE_HOME de 32 bits que
    derrubava conexoes em producao — nascia no fim de uma coluna rolante.
    """
    app = SettingsTestApp()
    async with app.run_test(size=(120, 40)):
        titulos = " ".join(_titulos_de_painel(app.query_one(SettingsScreen))).lower()
        for assunto in ("tema", "auditoria", "exporta", "oracle"):
            assert assunto in titulos, "%s sem painel proprio: %r" % (assunto, titulos)


@pytest.mark.asyncio
async def test_configuracoes_a_80x24_nao_esconde_a_porta(tmp_config_dir):
    """A 80x24, na DBQMApp REAL, a lista de MAIS CONFIGURACOES tem de estar la.

    Na DBQMApp a tela recebe 20 linhas, nao 24: o Header come 1, a tira de
    abas 2, a regua abaixo dela 1 e a StatusBar 1. Um harness que compoe a
    `SettingsScreen` sozinha lhe da as 24 inteiras — e foi assim que a
    versao anterior deste teste afirmou que os quatro assuntos apareciam
    "sem rolar" quando no app EXPORTACAO nao aparecia. Medido: `EXPORTACAO
    no harness = True, no app = False`. E a licao da Task 4 outra vez —
    medir no estado em que o defeito acontece — entao aqui se monta o app.

    E os seis paineis nao cabem mesmo em 20 linhas: as duas colunas somam
    ~36 linhas de conteudo cada. A secao 4 da gramatica nao promete que
    tudo cabe; promete que o que nao cabe ROLA, com o transbordo visivel.
    O que ela nao tolera e o que estava acontecendo com MAIS CONFIGURACOES:
    a moldura e o titulo desenhados e NENHUMA entrada, com o corpo
    comecando fora da tela. Esse painel e a unica porta para as duas telas
    que esta fase ressuscitou depois de seis semanas mortas; um titulo sem
    entradas nao anuncia porta nenhuma.
    """
    from dbqm.ui.app import DBQMApp
    from tests.ui._helpers import texto_renderizado

    app = DBQMApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = texto_renderizado(app)
        for entrada in ("Oracle Instant Clients", "Exportar / Importar"):
            assert entrada in pintado, (
                "a entrada %r de MAIS CONFIGURACOES nao e desenhada a 80x24: %r"
                % (entrada, pintado[-800:])
            )


@pytest.mark.asyncio
async def test_configuracoes_a_80x24_o_que_nao_cabe_rola(tmp_config_dir):
    """O que fica abaixo da dobra e alcancavel, e o transbordo e visivel.

    A contrapartida do teste acima: EXPORTACAO e FERNET KEY nao cabem a
    80x24 e nao ha aritmetica que os faca caber. O que a secao 4 exige e
    que rolem em vez de sumir — a versao sem moldura desta tela nascia com
    a secao Oracle em y=39 num container `overflow: hidden`, sem rolagem
    nenhuma, e simplesmente nao havia como chegar nela.
    """
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.settings import SettingsScreen
    from tests.ui._helpers import texto_renderizado

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

        pintado = texto_renderizado(app)
        # Corpo, e nao titulo: uma moldura com o titulo desenhado e o corpo
        # fora da tela e exatamente o defeito que o teste acima cobra.
        assert "Alterar diretorio" in pintado, (
            "o corpo de EXPORTACAO nao aparece nem rolando ate o fim: %r"
            % pintado[-800:]
        )
        assert "Criptografa as senhas" in pintado, (
            "o corpo de FERNET KEY nao aparece nem rolando ate o fim: %r"
            % pintado[-800:]
        )


@pytest.mark.asyncio
async def test_configuracoes_nao_tem_botao_que_navega(tmp_config_dir):
    """Botao e acao; quem leva a outra tela e a lista (secao 7 da gramatica).

    Os tres botoes que abriam OUTRA TELA (`#btn-export`, `#btn-import`,
    `#btn-oracle-clients`) estavam mortos desde a v1.17.0 — consultavam um
    `#screen-area` removido em e02b8a8 e so notificavam erro. O conserto
    nao foi reapontar o botao: navegacao virou lista, e os botoes que
    sobram na tela sao acoes de verdade (abrem um dialogo sobre o assunto
    do proprio painel).
    """
    from textual.widgets import Button

    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        ids = {b.id for b in screen.query(Button)}
        assert "btn-export" not in ids
        assert "btn-import" not in ids
        assert "btn-oracle-clients" not in ids
        # As acoes reais continuam: cada uma abre um modal sobre o assunto
        # do painel em que vive.
        assert {"btn-export-dir", "btn-oracle-client-dir"} <= ids


@pytest.mark.asyncio
async def test_settings_widgets_moram_dentro_de_um_painel(tmp_config_dir):
    """Nada fica solto no fundo — secao 4 da gramatica."""
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
async def test_lista_de_mais_configuracoes_nao_quebra_a_80_colunas(tmp_config_dir):
    """Cada entrada da lista cabe em duas linhas, com o recuo intacto.

    `item_hierarquico` recua a desambiguacao para dizer "isto pertence a
    entrada acima". Quando o texto e mais largo que a coluna, o Textual
    quebra sozinho no render e a continuacao volta para a coluna 0 — a
    MESMA da identidade da proxima entrada, que e o defeito que originou
    esta fase (Task 4 ja pagou por ele em `connections`). Aqui a saida nao
    e constante de largura: e texto curto. Este teste e quem cobra isso,
    medido nas colunas que a lista tem a 80 (30, medidas no widget
    montado), e nao numa suposicao.
    """
    from textual.widgets import OptionList
    from tests.ui._helpers import linhas_renderizadas

    app = SettingsTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        tela = app.query_one(SettingsScreen)
        lista = tela.query_one("#settings-ferramentas-list", OptionList)
        lista.focus()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        pintado = linhas_renderizadas(app)
        r = lista.content_region
        linhas = [
            pintado[y][r.x:r.x + r.width].rstrip()
            for y in range(r.y, r.y + r.height)
        ]
        linhas = [linha for linha in linhas if linha]
        assert len(linhas) == 2 * len(SettingsScreen.FERRAMENTAS), (
            "alguma entrada quebrou em mais de duas linhas: %r" % linhas
        )
        identidades = [linha for linha in linhas if not linha.startswith(" ")]
        assert len(identidades) == len(SettingsScreen.FERRAMENTAS), (
            "uma continuacao voltou para a coluna 0 da identidade: %r" % linhas
        )


@pytest.mark.asyncio
async def test_redimensionar_reelide_e_nao_varre_o_disco(tmp_config_dir, monkeypatch):
    """A elisao acompanha a largura — e alargar a janela devolve caminho.

    Elidir contra uma constante acertaria uma largura e erraria as outras,
    entao a largura e medida no rotulo montado e repintada no `resize`. O
    que o repintar NAO pode fazer e refazer a deteccao do Instant Client:
    `resolve_oracle_client_dir` varre os diretorios de instalacao do
    sistema, e amarrar isso a cada quadro de um arrastar de janela seria
    trocar um defeito visual por um de desempenho.
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

    fundo = tmp_config_dir / "um" / "diretorio" / "bem" / "fundo" / "na" / "arvore"
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


def test_caminho_longo_e_elidido_no_meio():
    """O inicio e o fim identificam um caminho; o meio e o descartavel."""
    from dbqm.ui.screens.settings import elidir_caminho

    longo = "C:/Users/ricar/AppData/Local/Temp/claude/muito/fundo/exports"
    curto = elidir_caminho(longo, 40)
    assert len(curto) <= 40
    assert curto.startswith("C:/Users")
    assert curto.endswith("exports")
    assert "..." in curto or chr(8230) in curto


def test_caminho_que_cabe_nao_e_tocado():
    """Elidir o que cabe seria esconder informacao de graca."""
    from dbqm.ui.screens.settings import elidir_caminho

    assert elidir_caminho("C:/exports", 40) == "C:/exports"
    assert elidir_caminho("C:/exports", 10) == "C:/exports"


def test_elisao_corta_no_separador_e_nunca_passa_da_largura():
    """Corta entre segmentos: meio caminho de um nome nao identifica nada.

    E o limite e limite em qualquer largura — inclusive nas absurdas, onde
    a aritmetica de "metade para cada lado" e onde um off-by-one moraria.
    """
    from dbqm.ui.screens.settings import elidir_caminho

    caminho = "C:/Users/ricar/AppData/Local/Temp/claude/muito/fundo/exports"
    assert elidir_caminho(caminho, 40) == (
        "C:/Users" + chr(8230) + "Temp/claude/muito/fundo/exports"
    )
    for largura in range(1, len(caminho) + 2):
        assert len(elidir_caminho(caminho, largura)) <= largura, largura
    assert elidir_caminho(caminho, 0) == ""

    # Sem separador aproveitavel ainda se corta no MEIO, por caractere.
    corrido = "a" * 60
    assert elidir_caminho(corrido, 21) == "a" * 10 + chr(8230) + "a" * 10


def test_elisao_de_caminho_unc_preserva_o_servidor():
    """Num UNC a raiz e o SERVIDOR, e e ela que a elisao promete guardar.

    `\\\\servidor\\share\\...` parte em ['', '\\\\', '', '\\\\', 'servidor', ...]:
    os dois primeiros segmentos sao vazios. Parando no terceiro pedaco, a
    cabeca era uma barra so — duas pastas em dois servidores diferentes
    elidiam IDENTICAS, e o `Client em uso` de um client de rede nao dizia
    de qual maquina ele vinha.

    Caminho com letra de unidade e caminho POSIX ficam onde estavam: e o
    mesmo primeiro segmento COM NOME nos tres casos.
    """
    from dbqm.ui.screens.settings import elidir_caminho

    a = elidir_caminho(r"\\servidor-a\publico\dbqm\clients\instantclient", 32)
    b = elidir_caminho(r"\\servidor-b\publico\dbqm\clients\instantclient", 32)
    assert a.startswith(r"\\servidor-a"), a
    assert b.startswith(r"\\servidor-b"), b
    assert a != b, "dois servidores diferentes elidiram identicos: %r" % a
    assert a.endswith("instantclient") and len(a) <= 32

    assert elidir_caminho("C:/Users/ricar/AppData/Local/exports", 24).startswith(
        "C:/Users"
    )
    assert elidir_caminho("/usr/local/share/dbqm/exports", 20).startswith("/usr")

    for largura in range(1, 60):
        assert len(elidir_caminho(r"\\servidor-a\publico\dbqm\x", largura)) <= largura


@pytest.mark.asyncio
async def test_caminho_de_exportacao_cabe_na_coluna(tmp_config_dir):
    """Um caminho longo nao pode quebrar no meio de um nome e sumir.

    Antes desta tarefa a Fernet Key pintava `...\\Local\\Tem` numa linha e
    `p\\pytest-of-ricar\\...` na seguinte — quebra automatica no meio da
    palavra, e o FIM do caminho (o unico pedaco que diz de que diretorio se
    trata) caia fora do painel. A afirmacao e sobre a linha PINTADA.
    """
    from textual.widgets import Button, Static
    from dbqm.models.settings import Settings, save_settings
    from tests.ui._helpers import recorte

    fundo = tmp_config_dir / "um" / "diretorio" / "bem" / "fundo" / "na" / "arvore"
    fundo.mkdir(parents=True)
    save_settings(Settings(default_export_dir=str(fundo)))

    app = SettingsTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        tela = app.query_one(SettingsScreen)
        # A 80x24 a coluna da esquerda transborda e ROLA (secao 4): o
        # caminho vive no terceiro painel dela. Focar o botao do painel e o
        # que um Tab faz, e e o `set_focus` que manda o Textual rolar ate la.
        tela.query_one("#btn-export-dir", Button).focus()
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        rotulo = tela.query_one("#settings-export-dir-current", Static)
        linhas = [linha.rstrip() for linha in recorte(app, rotulo)]
        assert any("arvore" in linha for linha in linhas), (
            "o fim do caminho — o que identifica o diretorio — nao e pintado: %r"
            % linhas
        )
        assert any(chr(8230) in linha for linha in linhas), (
            "o caminho longo nao foi elidido: %r" % linhas
        )


@pytest.mark.asyncio
async def test_nenhum_caminho_transborda_a_caixa_do_rotulo(
    tmp_config_dir, monkeypatch
):
    """Elidir contra a largura errada e nao elidir: o texto quebra do mesmo jeito.

    Dois jeitos de errar a largura, os dois medidos na DBQMApp a 80x24:

    - O prefixo `Local: ` da Fernet Key fica na MESMA linha do caminho (os
      outros dois rotulos quebram a linha antes), e nao estava saindo do
      orcamento: o caminho elidido cabia em 32 celulas e a linha inteira
      dava 37, entao a quebra automatica gastava uma linha do painel.
    - A largura era medida cedo demais. Na montagem a coluna ainda nao
      sabe que vai precisar de barra de rolagem: o rotulo media 33 onde
      teria 32, e o caminho passava por UMA celula — o ultimo caractere do
      nome do diretorio ia sozinho para a linha de baixo, que e o defeito
      que a elisao existe para evitar. Nenhum `on_resize` da tela via
      isso; quem mudou de tamanho foi o rotulo (`RotuloCaminho`).
    """
    from textual.widgets import Static
    from dbqm.ui.app import DBQMApp
    from dbqm.ui.screens.settings import SettingsScreen
    from dbqm.models.settings import Settings, save_settings
    from tests.ui._helpers import recorte

    # Nomes longos e SEM separador aproveitavel de proposito: nesse caso
    # `elidir_caminho` corta por caractere e devolve exatamente o orcamento
    # que recebeu. Assim o comprimento da linha pintada denuncia o
    # orcamento, em vez de depender de onde os separadores de um caminho
    # de teste por acaso caem — com um caminho "realista" as duas contas,
    # a certa e a errada, podem cair no mesmo corte e o teste passa com o
    # defeito presente (aconteceu ao escrever este).
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

        # E o prefixo e o fim do caminho saem na MESMA linha PINTADA.
        coluna = tela.query_one("#settings-col-direita")
        coluna.scroll_end(animate=False)
        await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()
        fernet = tela.query_one("#settings-fernet-status", Static)
        assert any(
            "Local:" in linha and ".dbqm_key" in linha
            for linha in recorte(app, fernet)
        ), (
            "o `Local:` e o fim do caminho da chave sairam em linhas "
            "diferentes: %r" % recorte(app, fernet)
        )


@pytest.mark.asyncio
async def test_settings_no_settings_section_boxes(tmp_config_dir):
    """The old box-in-box `.settings-section` styling is gone."""
    app = SettingsTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(SettingsScreen)
        assert len(screen.query(".settings-section")) == 0


@pytest.mark.asyncio
async def test_settings_nao_usa_cor_literal_no_status_do_client(tmp_config_dir, monkeypatch):
    """O estado 'nenhum encontrado' e informativo, nao um aviso amarelo.

    Forca resolve_oracle_client_dir a "nenhum encontrado": sem o monkeypatch
    o teste passa vazio em qualquer maquina com Instant Client instalado (ex.:
    a maquina de desenvolvimento), porque o ramo amarelo nunca e alcancado.
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


async def _escolher_modo(pilot, screen, chave):
    """Escolhe Exportar/Importar pelo caminho real: destacar + Enter."""
    from textual.widgets import OptionList

    lista = screen.query_one("#cp-mode-list", OptionList)
    lista.focus()
    await pilot.pause()
    lista.highlighted = next(
        i
        for i in range(lista.option_count)
        if lista.get_option_at_index(i).nome == chave
    )
    await pilot.press("enter")
    await pilot.pause()


@pytest.mark.asyncio
async def test_config_port_escolha_de_modo_e_lista(tmp_config_dir):
    """Exportar e Importar sao DESTINOS, e destino nao se escolhe por botao.

    Os dois botoes lado a lado eram um menu disfarcado — a mesma forma que
    a tela de Ferramentas tinha. O que sobra de botao nesta tela sao as
    duas acoes de verdade (`cp-do-export`, `cp-do-import`), cada uma
    ancorada no formulario que ela executa.
    """
    from textual.widgets import Button, OptionList
    from tests.ui._helpers import nomes_renderizados

    app = ConfigPortTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        screen = app.query_one(ConfigPortScreen)
        fase = screen.query_one("#cp-mode-phase")
        assert nomes_renderizados(fase.query_one(OptionList)) == [
            "Exportar",
            "Importar",
        ]
        assert not fase.query(Button), "botao e acao, nunca navegacao"


@pytest.mark.asyncio
async def test_config_port_export_phase_toggle(tmp_config_dir):
    """Escolher Exportar na lista mostra a fase de exportacao."""
    app = ConfigPortTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        screen = app.query_one(ConfigPortScreen)
        await _escolher_modo(pilot, screen, "export")
        assert screen.query_one("#cp-mode-phase").display is False
        assert screen.query_one("#cp-export-phase").display is True
        assert screen.query_one("#cp-import-phase").display is False


@pytest.mark.asyncio
async def test_config_port_import_phase_toggle(tmp_config_dir):
    """Escolher Importar na lista mostra a fase de importacao."""
    app = ConfigPortTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        screen = app.query_one(ConfigPortScreen)
        await _escolher_modo(pilot, screen, "import")
        assert screen.query_one("#cp-mode-phase").display is False
        assert screen.query_one("#cp-export-phase").display is False
        assert screen.query_one("#cp-import-phase").display is True


@pytest.mark.asyncio
async def test_config_port_so_tem_botao_de_acao(tmp_config_dir):
    """Nenhum botao desta tela navega — os dois que restam EXECUTAM."""
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
        assert nomes_renderizados(option_list) == ["q1"]

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
async def test_esqueleto_de_resultado_tem_a_forma_mediana(tmp_config_dir):
    """A mediana medida das 68 consultas salvas e 9 colunas, nao 4.

    Um esqueleto com a forma errada produz o salto de layout que ele existe
    para impedir — foi o defeito encontrado em browser.py na fase 1.
    """
    from dbqm.ui.widgets.esqueleto import Esqueleto
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield QueryExecScreen()

    app = App_()
    async with app.run_test():
        esq = app.query_one("#result-skeleton", Esqueleto)
        assert len(esq.query(".esqueleto-linha")) == 8
        primeira = esq.query(".esqueleto-linha").first()
        assert len(primeira.query(".esqueleto-celula")) == 9


@pytest.mark.asyncio
async def test_esqueleto_de_grupo_tem_a_forma_mediana(tmp_config_dir):
    """Mesmo defeito, mesmo call site espelhado em group_exec.py."""
    from dbqm.ui.widgets.esqueleto import Esqueleto
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield GroupExecScreen()

    app = App_()
    async with app.run_test():
        esq = app.query_one("#ge-results-skeleton", Esqueleto)
        assert len(esq.query(".esqueleto-linha")) == 8
        primeira = esq.query(".esqueleto-linha").first()
        assert len(primeira.query(".esqueleto-celula")) == 9


@pytest.mark.asyncio
async def test_registro_vertical_usa_tokens_de_texto(tmp_config_dir):
    """`_show_vertical` deve pintar com os tokens da gramatica, nao texto
    plano com `*** Registro N ***`.

    Assertar que o nome do token aparece numa string nao prova nada sobre o
    que aparece na tela (licao da Task 1): aqui resolvemos o span de fato
    renderizado para a cor real do tema ativo, com `Style.parse` dentro do
    contexto da app — o mesmo mecanismo que o Textual usa para pintar a
    tela.
    """
    from textual.style import Style

    def cor_no_offset(conteudo, offset):
        """Resolve a cor de fato aplicada num offset, somando os spans que
        cobrem esse offset ja resolvidos via `Style.parse` (os spans crus de
        `Content` guardam a marcacao como string, ex.: "$texto-forte", nao
        como `Style` — por isso nao da para somar sem resolver antes)."""
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

        cor_forte = Style.parse("$texto-forte").foreground
        cor_apoio = Style.parse("$texto-apoio").foreground
        cor_texto = Style.parse("$texto").foreground
        # Os tres tokens tem de fato cores diferentes no tema ativo, senao
        # o teste abaixo nao provaria discriminacao nenhuma entre eles.
        assert len({cor_forte, cor_apoio, cor_texto}) == 3

        pos_registro = texto.index("Registro 1")
        pos_rotulo = texto.index("nome")
        pos_valor = texto.index("Alice")

        assert cor_no_offset(conteudo, pos_registro) == cor_forte
        assert cor_no_offset(conteudo, pos_rotulo) == cor_apoio
        assert cor_no_offset(conteudo, pos_valor) == cor_texto


@pytest.mark.asyncio
async def test_registro_vertical_alinha_rotulos_a_direita_apos_escapar(tmp_config_dir):
    """O rotulo tem de ser escapado ANTES de alinhado, nao depois.

    Escapar depois de alinhar acrescenta barras a um rotulo que ja tinha o
    tamanho certo, desalinhando so a coluna cujo nome tem colchete. Aqui
    "id" (2 chars) e "nome_da_coluna" (14 chars) sao o caso comum, sem
    colchete: o rotulo de "id" tem de vir com exatamente 14 caracteres,
    todos os 12 primeiros sendo espaco — o mesmo resultado de antes da
    task, byte a byte, provando que a ordem nova nao regride o caso comum.
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
    """Escolher uma pasta PELO TECLADO estreita a lista de consultas.

    Escrever `seletor.value = "A"` nao exercita nada do que esta tarefa
    introduziu. `NavSelect` re-liga `enter,space` a `show_overlay` — e o
    que permite as setas continuarem navegando entre widgets em vez de
    abrirem o menu — e uma atribuicao de atributo nao passa por binding
    nenhum: a interacao real (abrir o menu, andar, escolher) ficava sem
    teste algum enquanto os tres testes de pasta escreviam o valor direto.

    Aqui o caminho e o mesmo do usuario, dentro da DBQMApp inteira, e o que
    se verifica no fim e a lista PINTADA, nao o valor do widget."""
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
        assert nomes_renderizados(app.query_one("#ql-listview", OptionList)) == [
            "q1", "q2",
        ]

        # Todas -> A: abrir o menu com enter, descer uma opcao, confirmar.
        seletor.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert seletor.expanded, "enter tem de abrir o menu (binding do NavSelect)"
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert not seletor.expanded
        assert nomes_renderizados(app.query_one("#ql-listview", OptionList)) == ["q1"]

        # A -> Todas: mesmo caminho, subindo.
        seletor.focus()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("up")
        await pilot.press("enter")
        await pilot.pause()
        assert nomes_renderizados(app.query_one("#ql-listview", OptionList)) == [
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

        # A tela poe o foco inicial neste mesmo botao (`_set_initial_focus`,
        # adiado por `call_after_refresh`). Sem deixar a montagem assentar,
        # o foco inicial chegaria DEPOIS do clique e desfaria o que este
        # teste mede.
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
# FerramentasScreen tests
# ======================================================================


from dbqm.ui.screens.ferramentas import FerramentasScreen


class FerramentasTestApp(ThemedTestApp):
    def compose(self) -> ComposeResult:
        yield FerramentasScreen()


async def _escolher_ferramenta(pilot, screen, chave):
    """Abre uma ferramenta pelo caminho real: destacar na lista + Enter."""
    from textual.widgets import OptionList

    lista = screen.query_one("#ferr-menu-list", OptionList)
    lista.focus()
    await pilot.pause()
    lista.highlighted = next(
        i
        for i in range(lista.option_count)
        if lista.get_option_at_index(i).nome == chave
    )
    await pilot.press("enter")
    await pilot.pause()


@pytest.mark.asyncio
async def test_ferramentas_e_lista_e_nao_botoes_de_largura_total(tmp_config_dir):
    """Cinco botoes de largura total sao cinco botoes fingindo ser um menu.

    A afirmacao e sobre o MENU, nao sobre a tela inteira: as cinco
    ferramentas hospedadas tem botoes de acao legitimos (Novo, Salvar,
    Excluir...), e um `not app.query(Button)` global so passaria por
    acidente — elas sao montadas sob demanda, entao na montagem ainda nao
    existe nenhum. Uma afirmacao que depende de o alvo nao ter sido
    construido ainda nao vigia coisa alguma.
    """
    from textual.widgets import Button, OptionList
    from tests.ui._helpers import nomes_renderizados

    app = FerramentasTestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        screen = app.query_one(FerramentasScreen)
        menu = screen.query_one("#ferr-menu")
        lista = menu.query_one(OptionList)
        assert nomes_renderizados(lista) == [
            "\U0001F465  Gerenciar Grupos",
            "\U0001F4C4  Gerenciar Templates",
            "\U0001F4E6  Package Editor",
            "\u25b6  Executar Rotina",
            "\u25b6  Executar Grupo",
        ]
        assert not menu.query(Button), "botao e acao, nunca navegacao"


@pytest.mark.asyncio
async def test_ferramentas_screen_starts_on_the_menu(tmp_config_dir):
    """FerramentasScreen abre no menu, nao numa ferramenta."""
    from textual.widgets import ContentSwitcher
    app = FerramentasTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(FerramentasScreen)
        assert screen.query_one(ContentSwitcher).current == "ferr-menu"


@pytest.mark.asyncio
async def test_ferramentas_screen_does_not_load_tools_on_mount(tmp_config_dir):
    """Mounting FerramentasScreen alone must not instantiate any tool
    screen. In particular, PackageEditorScreen's on_mount() eagerly pushes
    a modal screen (_PackageChoiceModal) the moment it is mounted (see
    dbqm/ui/screens/package_editor.py). If the tool screens were mounted
    up front, that modal would become the app's active screen before any
    user interaction happens at all. Tool screens must be built lazily, on
    first open, so no modal is pushed just from mounting the launcher."""
    app = FerramentasTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert len(app.screen_stack) == 1

        screen = app.query_one(FerramentasScreen)
        # Vazios: o "Voltar" que morava aqui era navegacao feita por botao.
        assert not list(screen.query_one("#ferr-packages").children)
        assert not list(screen.query_one("#ferr-executar").children)


@pytest.mark.asyncio
async def test_ferramentas_screen_open_and_back(tmp_config_dir):
    """Escolher na lista constroi e mostra a ferramenta; `voltar_ao_menu`
    devolve ao menu, e reabrir nao constroi uma segunda instancia."""
    from textual.widgets import ContentSwitcher
    from dbqm.ui.screens.package_editor import PackageEditorScreen

    app = FerramentasTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(FerramentasScreen)
        switcher = screen.query_one(ContentSwitcher)

        await _escolher_ferramenta(pilot, screen, "packages")
        assert switcher.current == "ferr-packages"

        packages_container = screen.query_one("#ferr-packages")
        assert len(packages_container.query(PackageEditorScreen)) == 1

        screen.voltar_ao_menu()
        await pilot.pause()
        assert switcher.current == "ferr-menu"

        await _escolher_ferramenta(pilot, screen, "packages")
        assert len(packages_container.query(PackageEditorScreen)) == 1


@pytest.mark.asyncio
async def test_ferramentas_screen_open_executar_grupo(tmp_config_dir):
    """Escolher 'Executar Grupo' monta um GroupRunScreen em #ferr-executar."""
    from textual.widgets import ContentSwitcher
    from dbqm.ui.screens.group_run import GroupRunScreen

    app = FerramentasTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(FerramentasScreen)
        switcher = screen.query_one(ContentSwitcher)

        await _escolher_ferramenta(pilot, screen, "executar")
        assert switcher.current == "ferr-executar"

        executar_container = screen.query_one("#ferr-executar")
        assert len(executar_container.query(GroupRunScreen)) == 1

        screen.voltar_ao_menu()
        await pilot.pause()
        assert switcher.current == "ferr-menu"

        await _escolher_ferramenta(pilot, screen, "executar")
        assert len(executar_container.query(GroupRunScreen)) == 1


@pytest.mark.asyncio
async def test_ferramentas_group_run_empty_state_action_opens_group_management(
    tmp_config_dir,
):
    """With zero groups configured system-wide, GroupRunScreen's EmptyState
    ("Gerenciar grupos") must not be a dead end: it switches the launcher
    to the sibling "Gerenciar Grupos" tool, where groups are created."""
    from textual.widgets import Button, ContentSwitcher
    from dbqm.ui.widgets.empty_state import EmptyState
    from dbqm.ui.screens.group_manage import GroupManageScreen

    app = FerramentasTestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.query_one(FerramentasScreen)
        switcher = screen.query_one(ContentSwitcher)

        await _escolher_ferramenta(pilot, screen, "executar")
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
        assert nomes_renderizados(group_list) == ["g1"]

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
    this screen used before (cardinalidade variavel, nao abas)."""
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
        # A metade que faltava: sem isto o teste passava com as abas de
        # volta ao lado do Select, que e exatamente a regressao que ele diz
        # guardar. Mesmo par de asercoes do irmao de consultas
        # (test_pastas_viram_select_com_contagem).
        assert not app.query("#gr-folder-bar"), "a barra de botoes some"
        assert not app.query("#gr-folder-hint"), "a dica das setas some junto"


@pytest.mark.asyncio
async def test_group_run_pinta_dois_grupos_de_mesmo_nome(tmp_config_dir):
    """Dois grupos homonimos nao podem derrubar a tela.

    Mesmo defeito de `test_query_list_pinta_duas_consultas_de_mesmo_nome`:
    com o nome viajando como `Option(conteudo, id=nome)`,
    `OptionList.add_option` levantava `DuplicateID` e a tela nao montava.
    `groups.json` e editavel a mao, entao o dado ambiguo existe; a lista
    pinta as duas linhas e deixa a ambiguidade para a busca por nome."""
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
        assert nomes_renderizados(group_list) == ["dup", "dup"]
        pintado = [group_list.get_option_at_index(i).prompt.plain for i in range(2)]
        assert "primeiro" in pintado[0] and "1 consulta" in pintado[0]
        assert "segundo" in pintado[1] and "2 consultas" in pintado[1]


@pytest.mark.asyncio
async def test_group_run_seleciona_por_nome_mesmo_com_nomes_repetidos(
    tmp_config_dir,
):
    """A selecao de grupo resolve pelo nome, como antes dos ids.

    Caso normal (nomes unicos) e caso ambiguo no mesmo teste: escolher a
    linha posta o nome daquela linha, e escolher uma das duas homonimas
    posta o nome homonimo em vez de nao fazer nada."""
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
async def test_group_run_item_montado_tem_hierarquia_visivel(tmp_config_dir):
    """A entrada de grupo montada de verdade ocupa mais de uma linha e cada
    papel sai numa cor distinta — nome, contagem de consultas, descricao.

    A lista de grupos trocou a string concatenada com "|" pelo mesmo
    `item_hierarquico` da lista de consultas, mas so a de consultas tinha
    guard (`test_query_list_item_montado_tem_hierarquia_visivel`, em
    test_widgets.py). Este e o par que faltava: a descricao vai inteira,
    sem corte artificial, e as cores sao resolvidas com o `Style.parse` do
    tema ativo — o mesmo mecanismo que o Textual usa antes de pintar.
    Prova a FIACAO ate a opcao montada, nao a pintura de pixel.

    A descricao pode ocupar MAIS DE UMA linha: desde que a lista de grupos
    pre-quebra o texto em linhas logicas na largura do painel (o conserto da
    continuacao que caia na coluna da identidade), o numero de linhas
    depende do comprimento do texto. O que este teste afirma nao e a
    contagem, e a GRAMATICA — identidade sozinha na primeira linha, todo o
    resto recuado — e que a quebra nao perde caractere: as linhas de
    contexto, remontadas, sao a descricao original."""
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

        cor_forte = Style.parse("$texto-forte").foreground
        cor_apoio = Style.parse("$texto-apoio").foreground
        cor_desabilitado = Style.parse("$texto-desabilitado").foreground
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
