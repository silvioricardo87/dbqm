"""Tests for UI widgets."""
import pytest
from textual.app import ComposeResult

from tests.ui._helpers import ThemedTestApp


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
async def test_status_bar_bolinha_contrasta_com_o_fundo_da_barra():
    """A bolinha de conexao precisa contrastar com o fundo da propria barra.

    O bug original nunca foi "a bolinha usa o token errado" — foi "a
    bolinha nao contrasta com o que esta atras dela". Por isso este teste
    nao nomeia nenhum token: nem o da bolinha (ja vem resolvido do conteudo
    renderizado), nem o do fundo da barra. O fundo e lido de
    `barra.styles.background` — a cor que o Textual efetivamente resolveu
    e vai pintar atras do widget montado, seja qual for a regra CSS que a
    produziu. Se `StatusBar.DEFAULT_CSS` trocar de `background: $primary`
    para outro token, este teste continua medindo o par real; nomear
    `$primary` aqui seria a mesma armadilha que a asserção anterior tinha
    contra `$background` — presa a uma grafia, nao a relacao.
    """
    from textual.style import Style

    from tests.design._contraste import razao

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

        contraste = razao(cor_bolinha.hex, cor_fundo_barra.hex)
        assert contraste >= 3.0, (
            f"bolinha ({cor_bolinha.hex}) sobre o fundo real da barra "
            f"({cor_fundo_barra.hex}) = {contraste:.2f}:1, abaixo do piso de interface"
        )


# ---------------------------------------------------------------------------
# Veredito / StatusOperacao tests
# ---------------------------------------------------------------------------

def test_veredito_comunica_estado_alem_da_cor():
    """Piso de acessibilidade: cor sozinha nao comunica estado."""
    from dbqm.ui.widgets.veredito import marcar_veredito

    glifos = {marcar_veredito(v).split("]")[1].split("[")[0] for v in
              ("igual", "igual-normalizado", "difere", "ausente")}
    assert len(glifos) == 4, f"glifos repetidos: {glifos}"


def test_veredito_igual_usa_o_token_do_proprio_eixo():
    from dbqm.ui.widgets.veredito import marcar_veredito

    assert "$veredito-igual" in marcar_veredito("igual")


def test_veredito_rejeita_status_desconhecido():
    from dbqm.ui.widgets.veredito import marcar_veredito

    with pytest.raises(ValueError, match="status"):
        marcar_veredito("talvez")


def test_operacao_bem_sucedida_nao_recebe_tinta():
    """Sucesso e a ausencia de alarme, mas nao de peso: `ok` nao pode levar
    NENHUM token de cor (nao so `$op-falha` — qualquer `$token`, inclusive
    um token de veredito colado por engano), e mantem `[bold]`. Uma versao
    anterior deste teste so checava a ausencia de `$op-falha`, o que passaria
    mesmo se sucesso fosse pintado com uma cor de veredito."""
    from dbqm.ui.widgets.veredito import marcar_operacao

    ok = marcar_operacao("ok")
    assert "$" not in ok, f"operacao bem sucedida nao deve carregar token de cor: {ok!r}"
    assert "[bold]" in ok, f"operacao bem sucedida perde peso sem cor: {ok!r}"
    assert "$op-falha" in marcar_operacao("falha")


def test_operacao_bem_sucedida_mantem_peso_nos_call_sites_manuais():
    """Os quatro pontos que montam markup de sucesso a mao — fora de
    `marcar_operacao`, porque a mensagem tambem carrega o tempo decorrido —
    tem que seguir a mesma regra: sem token de cor, com `[bold]` preservado.
    Nada testava isso ate agora; um `[bold]` apagado num desses sites
    passaria a suite inteira em silencio."""
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


def test_operacao_rejeita_estado_desconhecido():
    from dbqm.ui.widgets.veredito import marcar_operacao

    with pytest.raises(ValueError, match="estado"):
        marcar_operacao("talvez")


def test_marcar_veredito_texto_troca_rotulo_mantem_glifo_e_token():
    """`texto` deixa o chamador colorir sua propria palavra sem duplicar o
    rotulo padrao do componente ao lado dela (achado da revisao da Task 11:
    `_render_summary` gerava "= OK Iguais:" antes deste parametro existir).

    O glifo e o token continuam vindo so de `VEREDITOS` — `texto` nunca
    expõe o nome do token para o chamador montar `[$token]` por fora; se
    expusesse, reabriria exatamente o buraco de montagem a mao que o resto
    deste modulo fecha.
    """
    from dbqm.ui.widgets.veredito import marcar_veredito

    padrao = marcar_veredito("difere")
    customizado = marcar_veredito("difere", texto="DIVERGENTE")

    assert "DIVERGENTE" in customizado
    assert "DIFERE" not in customizado
    assert "$veredito-difere" in customizado
    # mesmo glifo do padrao, sem duplicar o rotulo "DIFERE" dele
    assert customizado.split("]")[1].split(" ", 1)[0] == padrao.split("]")[1].split(" ", 1)[0]


def test_marcar_veredito_escapa_texto_para_nao_vazar_markup():
    """`texto` existe para um rotulo, nao para injetar markup. Nenhum
    chamador de hoje passa texto vindo de dado (todos sao literais fixos),
    mas nada impede um chamador futuro de passar algo derivado de dado —
    e um `[/]` ou um `$token` dentro desse valor nao pode fechar a tag do
    componente mais cedo nem abrir um estilo diferente no meio do
    marcador.
    """
    from textual.content import Content
    from dbqm.ui.widgets.veredito import marcar_veredito

    perigoso = "fim[/][$op-falha]injetado"
    saida = marcar_veredito("igual", texto=perigoso)

    # so o fechamento legitimo do proprio componente sobra sem escape
    assert saida.count("[/]") == 1
    assert saida.endswith("[/]")

    # o markup inteiro resolve como UM UNICO span, com o token do estado —
    # se o texto perigoso tivesse escapado do escape, apareceria um
    # segundo span (o "[$op-falha]" injetado abrindo um estilo por conta
    # propria) ou o texto "injetado" ficaria fora de qualquer span.
    conteudo = Content.from_markup(saida)
    assert len(conteudo.spans) == 1
    assert conteudo.spans[0].style == "$veredito-igual"
    assert "fim" in conteudo.plain
    assert "injetado" in conteudo.plain


def test_veredito_sem_markup_montado_a_mao_fora_do_componente():
    """Fecha a porta que sobrou depois da primeira rodada da Task 11: nada
    fora de `veredito.py` pode escrever `$veredito-*`/`$op-falha` direto no
    markup sem que este teste acuse — nem hoje, nem um quinto caso amanha.

    A distincao que decide o que entra em `PROSA_DE_ERRO_FORA_DO_ESCOPO`
    abaixo: um MARCADOR nomeia um estado dentro de um vocabulario fechado
    (`igual`/`difere`/`ausente`/`ok`/`falha`/...) e por isso PRECISA de
    glifo — a cor sozinha nunca basta, porque o vocabulario e finito e
    repetido em toda a interface. PROSA ja nomeia a falha em palavras
    proprias, escritas uma vez para aquele erro especifico ("DDL executado
    com erros de compilacao", "Erro na execucao") — a cor so reforca o que
    a frase ja diz, entao pintar essa prosa com `$op-falha` nao e o mesmo
    buraco que este teste fecha.

    O eixo veredito (`$veredito-*`) e so marcador, nunca prosa, em toda a
    interface hoje — por isso fica de porta fechada de verdade, sem
    excecao: qualquer ocorrencia fora de `veredito.py` falha.

    O eixo operacao (`$op-falha`) tem os dois usos: `marcar_operacao` para
    marcador (convertido) e, em cinco telas que a Task 11 nunca tocou
    (DDL, rotina, client Oracle, configuracoes), coloracao de prosa de erro
    que ja nomeia a falha em palavras — fora do escopo de
    `marcar_operacao` por natureza, nao por preguica; converter essas
    telas prependeria "x FALHA" na frente de frases como "Erro na
    execucao", a mesma duplicacao que o parametro `texto` acabou de tirar
    do resumo da comparacao. `PROSA_DE_ERRO_FORA_DO_ESCOPO` trava o numero
    exato de ocorrencias por arquivo para que a porta feche para qualquer
    ocorrencia NOVA (nesses arquivos ou em qualquer outro) sem reabrir a
    conversa sobre esses cinco. Se um deles for reescrito para citar um
    estado do vocabulario fechado em vez de prosa, o numero aqui muda
    junto — o teste acusa nos dois sentidos.

    Trechos de `DEFAULT_CSS` sao ignorados: sao declaracao estatica de
    estilo do widget (o mesmo uso que `theme.py` faz dos tokens), nao
    markup dinamico — nao tem o problema de "estado comunicado so por
    cor" que este teste vigia.

    Limite deliberado deste teste, aceito na revisao (nao amplie sem
    reabrir a conversa): e uma varredura de texto sobre `dbqm/ui/`, entao
    nao pega um token remontado por interpolacao ou partido entre
    literais concatenados, nao pega uma constante de token definida fora
    de `dbqm/ui` e so referenciada aqui, e nao pega markup montado em
    `dbqm/core`/`dbqm/cli.py` e apenas renderizado por um widget da UI.
    """
    import re
    from pathlib import Path

    raiz_ui = Path(__file__).resolve().parents[2] / "dbqm" / "ui"
    padrao_token = re.compile(r"\$veredito-[a-z]+|\$op-falha")
    padrao_css = re.compile(r'DEFAULT_CSS\s*=\s*""".*?"""', re.DOTALL)

    # Prosa de erro que ja nomeia a falha em palavras proprias — fora do
    # escopo de marcar_operacao por natureza (ver docstring). Caminho
    # relativo a dbqm/ui -> numero exato de ocorrencias de `$op-falha`
    # hoje.
    PROSA_DE_ERRO_FORA_DO_ESCOPO: dict[str, int] = {
        "screens/adhoc.py": 2,  # cabecalho + detalhe de erro de compilacao DDL
        "screens/exec_routine.py": 2,  # cabecalho + detalhe de erro de execucao
        "screens/oracle_clients.py": 1,  # nivel info/ok/err de mensagens livres
        "screens/package_editor.py": 2,  # contagem + mensagem de erro de compilacao
        "screens/settings.py": 1,  # texto de excecao embutido num rotulo
    }

    ofensores = []
    for arquivo in sorted(raiz_ui.rglob("*.py")):
        rel = str(arquivo.relative_to(raiz_ui)).replace("\\", "/")
        if rel == "widgets/veredito.py":
            continue
        texto_fonte = arquivo.read_text(encoding="utf-8")
        texto_sem_css = padrao_css.sub("", texto_fonte)
        n = len(padrao_token.findall(texto_sem_css))
        permitido = PROSA_DE_ERRO_FORA_DO_ESCOPO.get(rel, 0)
        if n != permitido:
            ofensores.append(f"{rel}: {n} ocorrencia(s), esperado {permitido}")

    assert not ofensores, (
        "markup de veredito/operacao montado a mao fora de veredito.py, "
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


def _resultado(colunas, linhas):
    return QueryResult(
        query_name="t", connection_name="c",
        columns=colunas, rows=linhas, row_count=len(linhas), elapsed=0.01,
    )


@pytest.mark.asyncio
async def test_result_table_fixa_a_coluna_chave_e_lista_zebra():
    """A primeira coluna nunca sai de vista ao rolar lateralmente.

    O dbqm existe para comparar: sem saber de qual registro e a linha, as
    demais colunas nao significam nada.
    """
    from textual.widgets import DataTable

    class App_(ThemedTestApp):
        def compose(self):
            yield ResultTable(id="rt")

    app = App_()
    async with app.run_test() as pilot:
        rt = app.query_one("#rt", ResultTable)
        rt.load_result(_resultado(
            ["NUM_APOLICE", "SITUACAO", "VLR_PREMIO"],
            [["8801194920", "ATIVA", "3.482,90"]],
        ))
        await pilot.pause()
        dt = rt.query_one(DataTable)
        assert dt.fixed_columns == 1
        assert dt.zebra_stripes is True


@pytest.mark.asyncio
async def test_result_table_nao_fixa_coluna_quando_ha_uma_so():
    """Fixar a unica coluna nao protege nada e rouba largura.

    Afirma a TRANSICAO (varias colunas -> uma so), nao so o valor final: o
    padrao do Textual para fixed_columns ja e 0, entao um teste que so
    carrega uma coluna passaria mesmo se a linha que zera fixed_columns
    fosse apagada. Carregando primeiro um resultado largo (fixa em 1) e
    depois o de coluna unica no MESMO widget, um fixed_columns preso em 1
    do carregamento anterior reprova o teste pelo motivo certo.
    """
    from textual.widgets import DataTable

    class App_(ThemedTestApp):
        def compose(self):
            yield ResultTable(id="rt")

    app = App_()
    async with app.run_test() as pilot:
        rt = app.query_one("#rt", ResultTable)
        dt = app.query_one(DataTable)
        rt.load_result(_resultado(
            ["NUM_APOLICE", "SITUACAO", "VLR_PREMIO"],
            [["8801194920", "ATIVA", "3.482,90"]],
        ))
        await pilot.pause()
        assert dt.fixed_columns == 1

        rt.load_result(_resultado(["TOTAL"], [["42"]]))
        await pilot.pause()
        assert dt.fixed_columns == 0


@pytest.mark.asyncio
async def test_result_table_coluna_chave_permanece_renderizada_ao_rolar():
    """A prova de renderizacao, nao so do atributo reativo.

    `fixed_columns == 1` pode ficar setado e mesmo assim a coluna parar de
    pintar na tela se um upgrade do Textual ou uma mudanca de CSS quebrar a
    renderizacao da fixacao. Este teste rola de verdade (pilot.press) e le o
    screenshot exportado — o mesmo texto que um usuario veria — em vez de só
    inspecionar o atributo.
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
        rt.load_result(_resultado(colunas, [linha]))
        await pilot.pause()
        dt = rt.query_one(DataTable)

        # Antes de rolar: a chave esta visivel, e a ultima coluna larga NAO
        # esta — confirma que o cenario realmente exige rolagem lateral.
        antes = app.export_screenshot()
        assert "CHAVE_REGISTRO" in antes
        assert "COLUNA_LARGA_NUMERO_08" not in antes

        # Rola de verdade, ate o fim.
        for _ in range(40):
            await pilot.press("right")
        await pilot.pause()
        assert dt.scroll_x > 0  # a rolagem lateral realmente aconteceu

        # Depois de rolar: a coluna-chave (cabecalho E valor) continua
        # pintada na tela, e a coluna que antes estava fora de vista agora
        # apareceu — provando que rolou colunas nao-fixas por baixo dela.
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
    queries = [
        {"name": "q1", "connection": "conn1", "table": "t1", "description": "desc1", "is_favorite": False, "folder": ""},
        {"name": "q2", "connection": "conn2", "table": "t2", "description": "desc2", "is_favorite": True, "folder": ""},
    ]
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        assert len(items) == 2
        # Favorites should be first
        assert items[0].query_name == "q2"
        assert items[1].query_name == "q1"


@pytest.mark.asyncio
async def test_query_list_empty():
    """A ListItem can't host a widget, so an empty/filtered-to-nothing
    list shows an EmptyState beside the ListView (which hides), never a
    fake row inside it."""
    from textual.widgets import ListItem, ListView
    from dbqm.ui.widgets.empty_state import EmptyState

    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries([])
        await pilot.pause()
        assert len(ql.query(ListItem)) == 0
        assert ql.query_one("#ql-filter-empty", EmptyState).display is True
        assert ql.query_one("#ql-listview", ListView).display is False


@pytest.mark.asyncio
async def test_query_list_filtered_empty_state_clears_search_and_notifies_host():
    """The EmptyState shown when a filter matches nothing must not be a
    dead end: it clears the widget's own inline search AND tells the host
    screen (which owns folder/connection filters up there) to clear its
    own."""
    from textual.widgets import Button, ListView
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
        assert ql.query_one("#ql-listview", ListView).display is False

        ql.query_one("#limpar-filtros-consultas", Button).press()
        await pilot.pause()

        assert ql._search_text == ""
        assert ql.query_one("#ql-filter-empty", EmptyState).display is False
        assert ql.query_one("#ql-listview", ListView).display is True
        assert notified == [True]


@pytest.mark.asyncio
async def test_query_list_filter_folder():
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
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        assert len(items) == 2
        names = {it.query_name for it in items}
        assert names == {"q1", "q3"}


@pytest.mark.asyncio
async def test_query_list_filter_folder_none_shows_all():
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
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        assert len(items) == 2


@pytest.mark.asyncio
async def test_query_list_posts_query_selected():
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
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries(queries)
        await pilot.pause()
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        await pilot.click(type(items[0]))
        await pilot.pause()
        assert len(messages) == 1
        assert messages[0] == "my_query"


@pytest.mark.asyncio
async def test_query_list_accepts_objects():
    """Widget should work with objects that have attributes (not just dicts)."""
    from dbqm.models.query import Query
    q = Query(name="obj_q", connection="conn", sql="SELECT 1", description="from object", is_favorite=True)
    app = QueryListTestApp()
    async with app.run_test() as pilot:
        ql = app.query_one(QueryListWidget)
        ql.load_queries([q])
        await pilot.pause()
        from dbqm.ui.widgets.query_list import _QueryListItem
        items = ql.query(_QueryListItem)
        assert len(items) == 1
        assert items[0].query_name == "obj_q"


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
async def test_group_result_status_column_resolves_veredito_colors():
    """O ganho visivel da tarefa: a coluna Status da tabela de comparacao
    tem que sair colorida, uma cor por veredito.

    Testa a cor RESOLVIDA de cada celula (nao a string de markup): um teste
    de string nao pegaria a celula continuando cinza/sem cor por `add_row`
    ter recebido `str(row.status)` cru em vez de `Content.from_markup(...)`.
    """
    from textual.style import Style
    from textual.widgets import DataTable

    from dbqm.core.group_engine import ComparisonResult, ComparisonRow, GroupResult
    from dbqm.design.tokens import TEMAS

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
        "1": TEMAS["plano-escuro"]["veredito-igual"],
        "2": TEMAS["plano-escuro"]["veredito-igual"],
        "3": TEMAS["plano-escuro"]["veredito-difere"],
        "4": TEMAS["plano-escuro"]["veredito-ausente"],
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


# ---------------------------------------------------------------------------
# Dialog tests
# ---------------------------------------------------------------------------
from dbqm.ui.widgets.dialog import Dialog


def test_dialog_rejeita_variante_desconhecida():
    """Variantes fechadas: sem porta dos fundos para estilo arbitrario."""
    with pytest.raises(ValueError, match="tom"):
        Dialog("Titulo", tom="roxo")
    with pytest.raises(ValueError, match="largura"):
        Dialog("Titulo", largura="xxl")


@pytest.mark.asyncio
async def test_dialog_renderiza_o_titulo():
    class _DialogApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            with Dialog("Confirmar exclusao", id="d"):
                yield Static("corpo")

    app = _DialogApp()
    async with app.run_test():
        titulo = app.query_one("#d-titulo", Static)
        assert "Confirmar exclusao" in titulo.render().plain


def test_dialog_variante_tela_preenche_a_viewport():
    """A quarta variante e a resposta do sistema aos casos que antes
    burlavam o enum escrevendo `.styles.width`/`.styles.height` depois de
    construir. Ela existe, e usa porcentagem (nao celulas) porque e
    conteudo a ser exibido, nao um formulario compacto."""
    d = Dialog("Titulo", largura="tela")
    # Textual guarda porcentagem como escalar "w"/"h" (viewport width/height);
    # comparar com a representacao efetivamente resolvida, nao com a string
    # de entrada.
    assert str(d.styles.width) == "90w"
    assert str(d.styles.height) == "85h"


def test_dialog_nao_tem_override_de_estilo_fora_do_componente():
    """Fecha a CLASSE, nao so a instancia: `largura`/`tom` sao validados no
    __init__, mas nada no Python impede escrever `dialog.styles.width =`
    depois — a atribuicao inline vence qualquer coisa que o __init__ tenha
    decidido, e nenhum teste nem validacao consegue ver essa escrita
    tardia. Guarda no mesmo formato de
    `test_toda_variavel_css_e_token_ou_builtin_documentado`: silencioso ate
    alguem reintroduzir o atalho, e ai falha alto. Precisar de mais espaco
    e sinal de variante nova em `LARGURAS` (ver "tela"), nunca de excecao
    local.

    Duas portas, nao uma: a atribuicao Python (`dialog.styles.width = ...`)
    e a regra CSS lado-a-lado (`AlgumaTela #meu-dialog { height: 85%; }`).
    A segunda escapava do guarda original porque ele so olhava `.styles.`;
    `template_manage.py` e `error.py` hand-rolaram exatamente a variante
    "tela" via CSS antes desta correcao. Todo id de Dialog neste repo
    contem a substring "dialog" (id="dialog", "error-dialog",
    "qp-dialog", "pkg-choice-dialog", ...), entao a regra CSS varre
    qualquer bloco `#*dialog*{ ... }` por width/height/max-height/
    min-height."""
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
async def test_templates_sidebar_empty_state_action_switches_to_ferramentas():
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

def test_empty_state_exige_uma_acao():
    """Um vazio que so informa que esta vazio e um defeito, nao um estado."""
    from dbqm.ui.widgets.empty_state import EmptyState

    with pytest.raises(TypeError):
        EmptyState("Consultas", "Voce ainda nao salvou nenhuma")  # sem acao


@pytest.mark.asyncio
async def test_empty_state_oferece_a_primeira_acao():
    from textual.widgets import Button
    from dbqm.ui.widgets.empty_state import EmptyState

    class _EmptyStateApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield EmptyState(
                o_que="Consultas",
                porque="Voce ainda nao salvou nenhuma consulta",
                acao_rotulo="Criar consulta",
                acao_id="criar-consulta",
            )

    app = _EmptyStateApp()
    async with app.run_test():
        botao = app.query_one("#criar-consulta", Button)
        assert botao.label.plain == "Criar consulta"


# ---------------------------------------------------------------------------
# Esqueleto tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_esqueleto_tem_a_forma_do_conteudo_que_vem():
    """Do formato do conteudo, nao um rodopio centralizado: evita o salto de
    layout quando o resultado real chega."""
    from dbqm.ui.widgets.esqueleto import Esqueleto

    class _EsqueletoApp(ThemedTestApp):
        def compose(self) -> ComposeResult:
            yield Esqueleto(linhas=6, colunas=3, id="e")

    app = _EsqueletoApp()
    async with app.run_test():
        esqueleto = app.query_one("#e", Esqueleto)
        assert len(esqueleto.query(".esqueleto-linha")) == 6


@pytest.mark.asyncio
async def test_somente_leitura_e_visualmente_distinto_de_desabilitado():
    """Somente leitura parece conteudo; desabilitado parece controle inerte —
    confundir os dois e o defeito que esta tarefa existe para prevenir."""
    from textual.widgets import Input

    class _EstadosApp(ThemedTestApp):
        CSS = "Input { width: 20; }"

        def compose(self) -> ComposeResult:
            yield Input(value="a", id="ro", classes="-somente-leitura")
            yield Input(value="b", id="off", disabled=True)

    app = _EstadosApp()
    async with app.run_test():
        ro = app.query_one("#ro", Input)
        off = app.query_one("#off", Input)
        assert ro.styles.color != off.styles.color


# ---------------------------------------------------------------------------
# item_hierarquico tests
# ---------------------------------------------------------------------------

def test_item_hierarquico_poe_identidade_sozinha_na_primeira_linha():
    from dbqm.ui.widgets.lista_hierarquica import item_hierarquico

    c = item_hierarquico("MGORA7ORA9", "Oracle/TNS - MGORA7ORA9", "Producao prod-day")
    linhas = str(c).split("\n")
    assert linhas[0].strip() == "MGORA7ORA9"
    assert "Oracle/TNS" in linhas[1]
    assert "Producao" in linhas[2]


def test_item_hierarquico_omite_linhas_vazias():
    from dbqm.ui.widgets.lista_hierarquica import item_hierarquico

    assert len(str(item_hierarquico("SO_NOME")).split("\n")) == 1


def test_item_hierarquico_escapa_o_conteudo():
    """Nome de conexao ou descricao vem de dado do usuario."""
    from dbqm.ui.widgets.lista_hierarquica import item_hierarquico

    c = item_hierarquico("[/]quebra", "x")
    assert "quebra" in str(c)


@pytest.mark.asyncio
async def test_item_hierarquico_usa_a_hierarquia_de_cor_da_gramatica():
    """Identidade, desambiguacao e contexto tem que sair com tres cores
    diferentes de fato resolvidas no tema ativo — nao apenas o nome do
    token aparecendo na string de markup (licao da Task 1)."""
    from textual.style import Style

    from dbqm.ui.widgets.lista_hierarquica import item_hierarquico

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
        conteudo = item_hierarquico(
            "MGORA7ORA9", "Oracle/TNS - MGORA7ORA9", "Producao prod-day"
        )
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
