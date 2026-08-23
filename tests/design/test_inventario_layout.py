"""Guardas da gramatica de layout (fase 2).

Fase 1 vigiou a **cor**; esta vigia a **estrutura**. O primeiro guarda:
`Panel` (e `Dialog`, seu equivalente modal) e a unica moldura de secao do
produto. Uma tela que desenha a propria caixa cria um terceiro vocabulario
de moldura — foi exatamente assim que o produto chegou a tres.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

# Ancorado no arquivo, nao no cwd: `Path("dbqm/ui")` varre zero arquivo
# quando o pytest roda de outro diretorio e o teste passa em silencio.
# Mesmo idioma de `tests/design/_varredura.py` e `test_inventario.py`.
RAIZ_UI = Path(__file__).resolve().parents[2] / "dbqm" / "ui"
RAIZ_PROJETO = RAIZ_UI.parents[1]

# As duas molduras do produto. Sao os unicos arquivos onde desenhar caixa
# e o trabalho. Caminhos relativos a raiz do projeto, no mesmo formato que
# `_rel()` produz — a primeira redacao deste guarda comparava string posix
# relativa contra caminho absoluto e nunca isentava ninguem.
MOLDURAS = {
    "dbqm/ui/widgets/panel.py",
    "dbqm/ui/widgets/dialog.py",
}

# Uma declaracao CSS de verdade termina em `;` ou `}`. Exigir o terminador
# e o que separa a declaracao da PROSA: `connections.py` explica a largura
# do Panel citando "`border: round`" em comentario, e uma varredura sem
# terminador acusa tres falsos positivos so nesse arquivo.
#
# `outline` entra junto porque DESENHA A MESMA CAIXA: `outline: round
# $accent` pinta os quatro lados no Textual, so que por dentro da area do
# widget em vez de fora. Uma varredura que so olhasse `border` deixaria a
# porta aberta — trocar uma palavra passava o guarda com a caixa intacta.
BORDA = re.compile(
    r"\b(?:border|outline)(?P<lado>-top|-bottom|-left|-right)?"
    r"\s*:\s*(?P<valor>[^;{}\n]*?)\s*[;}]"
)
ABRE_REGRA = re.compile(r"^\s*(?P<seletor>[^{}]+?)\s*\{")

# Isencoes por (arquivo, seletor), com o motivo escrito. Por SELETOR e nao
# por arquivo de proposito: uma caixa de secao nova no mesmo arquivo
# continua sendo reprovada.
ISENTOS = {
    # RECOLORE a afordancia que o widget ja desenha sozinho — nao soma
    # caixa nenhuma. O `SelectCurrent` do Textual nasce com `border: tall`;
    # aqui so a COR muda, para `$identidade`, como sinal de "conexao
    # escolhida". Duas coisas fazem esta isencao diferente das que estavam
    # aqui antes e nao eram verdade:
    #   - a geometria nao muda (a caixa ja existia, e do proprio controle);
    #   - `tall` nao e `round`: o vocabulario da moldura de secao continua
    #     exclusivo de Panel/Dialog.
    # A redacao anterior isentava `#adhoc-conn-select` alegando que "a borda
    # e a afordancia do campo". Nao era: `Panel #panel-body Select { border:
    # none }` tem especificidade maior e apagava aquela regra — a isencao
    # protegia CSS morto. E `#adhoc-dbms-toggle` desenhava `border: round
    # $primary`, byte a byte o mesmo que `Panel:focus-within`: um checkbox
    # parado com cara de painel focado. Os dois sairam do CSS; sobrou este,
    # que e real.
    (
        "dbqm/ui/screens/adhoc.py",
        "AdhocScreen #adhoc-conn-select.--conn-selected SelectCurrent",
    ),
}

# Limites conhecidos, escolhidos e nao descuidados (mesma disciplina da
# fase 1):
#   - borda montada por interpolacao ou por CSS vindo de outra camada
#     nao e vista por varredura textual;
#   - quatro `border-<lado>` somados desenham uma caixa e passam, porque
#     UM lado e regua de separacao (o proprio `Panel` usa `border-bottom`
#     no titulo, a `ActionBar` no topo e a `TemplatesSidebar` na lateral)
#     e distinguir os dois casos exigiria interpretar o bloco inteiro;
#   - a varredura e LINHA A LINHA, entao uma declaracao quebrada em duas
#     (`border:` numa linha, `round $accent;` na seguinte) escapa — e CSS
#     valido, e o Textual desenha a caixa. Nao esta fechado porque juntar
#     linhas antes de varrer exigiria distinguir quebra de declaracao de
#     fim de bloco sem um parser de CSS, e o guarda passaria a depender de
#     um. Se aparecer um caso real, o caminho e o parser, nao mais regex.


def _rel(arquivo: Path) -> str:
    return arquivo.relative_to(RAIZ_PROJETO).as_posix()


def bordas_cruas() -> list[tuple[str, int, str, str]]:
    """Toda caixa desenhada fora de um componente de moldura.

    Devolve `(arquivo, linha, seletor, declaracao)`.
    """
    achados: list[tuple[str, int, str, str]] = []
    for arquivo in sorted(RAIZ_UI.rglob("*.py")):
        rel = _rel(arquivo)
        if rel in MOLDURAS:
            continue
        seletor = ""
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            abre = ABRE_REGRA.match(linha)
            if abre:
                seletor = abre.group("seletor")
            for m in BORDA.finditer(linha):
                # Um lado so e regua, nao caixa.
                if m.group("lado"):
                    continue
                # `border: none` APAGA uma borda; nao desenha nenhuma. O
                # teste original excluia a linha inteira quando ela contivesse
                # a palavra "none" em qualquer posicao — `#nonexistent { border:
                # round $accent; }` escaparia. Aqui e o VALOR que decide.
                if m.group("valor").split()[0:1] == ["none"]:
                    continue
                if (rel, seletor) in ISENTOS:
                    continue
                achados.append((rel, numero, seletor, m.group(0)))
    return achados


def test_a_varredura_de_borda_encontra_arquivos():
    """Um guarda que varre zero arquivo passa sem vigiar nada."""
    arquivos = list(RAIZ_UI.rglob("*.py"))
    assert len(arquivos) > 20, f"varredura vazia ou rasa: {len(arquivos)} arquivos"
    assert all((RAIZ_PROJETO / rel).is_file() for rel in MOLDURAS)


def test_sem_borda_crua_fora_de_componente_de_moldura():
    """Um terceiro vocabulario de moldura foi como se chegou a tres."""
    fora = bordas_cruas()
    assert not fora, "caixa desenhada fora de Panel/Dialog:\n" + "\n".join(
        f"  {rel}:{n}  [{sel}]  {decl}" for rel, n, sel, decl in fora
    )


def test_o_guarda_ve_outline_como_caixa():
    """`outline: round $accent` desenha os quatro lados — e nao e `border`.

    Escrito porque a primeira redacao so varria `border`: renderizado, um
    `outline: round $accent;` pinta laterais e base exatamente como a
    moldura, e trocar uma palavra fazia uma caixa nova passar pelo guarda.
    Os `outline-<lado>` continuam sendo regua, como os `border-<lado>`.
    """
    caixa = BORDA.search("    #qualquer-tela { outline: round $accent; }")
    assert caixa is not None and caixa.group("lado") is None
    regua = BORDA.search("    #qualquer-tela { outline-bottom: solid $borda; }")
    assert regua is not None and regua.group("lado") == "-bottom"


# ======================================================================
# Guarda 2: cluster de acao centralizado fora de dialogo
# ======================================================================

# So alinhamento de LAYOUT — as quatro propriedades que reposicionam o
# conteudo dentro do container. `text-align` fica de fora de proposito:
# ela centraliza o texto DENTRO da caixa do proprio widget e nao desgruda
# cluster nenhum do assunto que ele opera, que e o dano que a secao 7
# descreve.
CENTRO = re.compile(
    r"(?<![\w-])(?:content-)?align(?:-horizontal)?\s*:\s*"
    r"(?P<valor>[^;{}\n]*?)\s*[;}]"
)
CLASSE = re.compile(r"^class\s+(?P<nome>\w+)\s*(?:\((?P<bases>[^)]*)\))?\s*:")

# Isencoes por (arquivo, seletor), com o motivo escrito — mesmo formato do
# guarda de borda. Nenhuma delas e um cluster de acao: sao conteudos que
# OCUPAM a area inteira e nao tem assunto ao lado para se ancorar.
CENTRO_ISENTOS = {
    # O estado vazio E a area em que vive: nao ha lista, tabela ou
    # formulario ao lado de quem ele pudesse se desgrudar. Alinhar a
    # esquerda deixaria o texto encostado numa borda com a area toda
    # vazia a direita.
    #
    # A redacao anterior prometia demais: "as acoes DENTRO dele nao estao
    # isentas". O que a isencao por SELETOR garante e mais estreito — um
    # seletor NOVO (`.empty-acoes { align: center }`) nao herda isencao
    # nenhuma, mas uma declaracao acrescentada A ESTES TRES seletores
    # nunca mais e examinada pelo guarda.
    #
    # Medido, porque a diferenca importa: hoje o botao de call-to-action
    # NAO fica centralizado. Na DBQMApp real a 100x30, o `hist-empty`
    # ocupa x=2..96 e o botao `Executar consulta` renderiza em x=4 —
    # encostado no padding, alinhado a esquerda. A razao e que os dois
    # `Static` do estado vazio sao `width: 100%`: eles fixam a largura do
    # grupo de filhos, e `align`/`content-align` no container nao tem o
    # que centralizar horizontalmente. Acrescentar `align: center middle`
    # a este bloco tambem nao muda o x do botao (medido nas duas ordens,
    # com e sem o `content-align`). Ou seja, o que hoje mantem o CTA
    # ancorado a esquerda e a largura dos irmaos, nao este guarda.
    ("dbqm/ui/widgets/empty_state.py", "EmptyState"),
    ("dbqm/ui/widgets/empty_state.py", "EmptyState .empty-o-que"),
    ("dbqm/ui/widgets/empty_state.py", "EmptyState .empty-porque"),
    # O indicador de progresso cobre a tela enquanto uma chamada remota
    # acontece; mesma razao do estado vazio.
    ("dbqm/ui/widgets/progress.py", "ProgressIndicator Static"),
    # `#pe-empty` e o estado vazio/carregando do editor de packages, com
    # `height: 1fr` e nenhum botao dentro: enquanto ele aparece, os dois
    # paineis do editor estao com `display: none` e ELE e a tela — o caso
    # que a propria secao 7 excetua. Alinha-lo a esquerda criaria um
    # segundo vocabulario de estado vazio, contra o `EmptyState` acima.
    ("dbqm/ui/screens/package_editor.py", "PackageEditorScreen #pe-empty"),
}

# Limites conhecidos, escolhidos:
#   - a varredura e LINHA A LINHA: `align:` numa linha e `center;` na
#     seguinte e CSS valido e escapa, como no guarda de borda acima;
#   - so a DECLARACAO e vista. Um cluster centralizado por padding, por
#     espacador `1fr` ou por `widget.styles.align` escrito em Python nao
#     aparece aqui;
#   - dialogo e reconhecido pela linha `class`: nome ou base contendo
#     `Modal`/`Dialog`. Isto foi CONFERIDO contra as bases reais neste
#     repositorio — toda subclasse de `ModalScreen` e pega, e o unico
#     nome pego que nao e `ModalScreen` e o proprio `Dialog`, que e a
#     moldura do dialogo. Uma tela de trabalho batizada com "Modal" no
#     nome seria isentada por engano;
#   - o guarda nao olha se o bloco contem BOTAO. Ele reprova qualquer
#     centralizacao de layout fora de dialogo, e as excecoes legitimas
#     entram em `CENTRO_ISENTOS` com o motivo escrito. E de proposito: a
#     redacao anterior casava por NOME de seletor (`#botoes`, `.acoes`) e
#     um cluster chamado `#adhoc-btn-bar` — real, medido — escapava.
#
# Mais dois limites da deteccao de dialogo, achados na revisao da Task 8 e
# escritos aqui porque a lista acima se apresentava como completa:
#   - `CLASSE` esta ancorada em `^class`: uma classe INDENTADA e invisivel
#     para a varredura, e o CSS dentro dela herda o veredito da classe que
#     a envolve. Ha uma no repositorio hoje — `TemplateChosen`, aninhada
#     em `TemplatesSidebar` (dbqm/ui/widgets/templates_sidebar.py) — e ela
#     nao declara CSS, entao o efeito e nulo. Aceitar `^\s*class` seria
#     pior sem mais trabalho: uma `class Mensagem(Message)` aninhada num
#     modal ZERARIA o `dialogo` do arquivo dali para baixo, e a
#     centralizacao legitima do modal passaria a reprovar. Fechar isso
#     exige rastrear indentacao, nao afrouxar a ancora;
#   - `dialogo` vale ate o fim do ARQUIVO depois da ultima classe. CSS de
#     modulo escrito abaixo de uma classe de modal sairia isento. Nenhum
#     existe hoje (o CSS deste produto mora sempre em `DEFAULT_CSS` dentro
#     da classe), e o preco de nao fechar e conhecido.


def clusters_centralizados(
    aplicar_isencoes: bool = True,
) -> list[tuple[str, int, str, str]]:
    """Toda centralizacao de layout fora de um dialogo.

    Devolve `(arquivo, linha, seletor, declaracao)`. Com
    `aplicar_isencoes=False` devolve tambem as de `CENTRO_ISENTOS` — e o
    que o canario usa para medir quanto a deteccao de dialogo isenta.
    """
    achados: list[tuple[str, int, str, str]] = []
    for arquivo in sorted(RAIZ_UI.rglob("*.py")):
        rel = _rel(arquivo)
        dialogo = False
        seletor = ""
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            classe = CLASSE.match(linha)
            if classe:
                nome = classe.group("nome")
                bases = classe.group("bases") or ""
                dialogo = any(
                    marca in texto
                    for texto in (nome, bases)
                    for marca in ("Modal", "Dialog")
                )
                seletor = ""
                continue
            abre = ABRE_REGRA.match(linha)
            if abre:
                seletor = abre.group("seletor")
            if dialogo:
                continue
            for m in CENTRO.finditer(linha):
                if "center" not in m.group("valor"):
                    continue
                if aplicar_isencoes and (rel, seletor) in CENTRO_ISENTOS:
                    continue
                achados.append((rel, numero, seletor, m.group(0)))
    return achados


def test_sem_cluster_de_botao_centralizado_fora_de_dialogo():
    """Centralizar so faz sentido quando o cluster E a tela — um dialogo.

    Numa tela de trabalho, centralizar desconecta a acao daquilo que ela
    opera: a acao tem de encostar no painel que e o seu assunto.
    """
    fora = clusters_centralizados()
    assert not fora, "centralizacao em tela de trabalho:\n" + "\n".join(
        f"  {rel}:{n}  [{sel}]  {decl}" for rel, n, sel, decl in fora
    )


def test_a_varredura_de_centralizacao_ve_os_dialogos():
    """Um guarda que isenta tudo (ou nada) nao vigia nada.

    Ancorado em numeros medidos: se a deteccao de dialogo parar de
    funcionar, as dezenas de centralizacoes LEGITIMAS dos modais entram no
    resultado e o teste acima passa a reprovar o produto inteiro.
    """
    total = 0
    for arquivo in RAIZ_UI.rglob("*.py"):
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            for m in CENTRO.finditer(linha):
                if "center" in m.group("valor"):
                    total += 1
    assert total > 40, f"varredura rasa demais: {total} centralizacoes"
    # Medido em d2367bb: 62 declaracoes de centralizacao em dbqm/ui, 57
    # delas dentro de dialogo (legitimas pela secao 7) e 5 fora — as cinco
    # de `CENTRO_ISENTOS`. O teto de 8 e esse 5 com uma folga estreita de
    # proposito: a redacao anterior deste canario era `< total / 2`, que
    # so disparava se a deteccao de dialogo quebrasse quase por inteiro.
    # Ela tolerava perder 25 modais em silencio — e um canario que tolera
    # perder metade nao e canario, e decoracao.
    fora_de_dialogo = clusters_centralizados(aplicar_isencoes=False)
    assert len(fora_de_dialogo) <= 8, (
        "a deteccao de dialogo parou de isentar os modais: %d centralizacoes "
        "fora de dialogo (eram 5)\n%s"
        % (
            len(fora_de_dialogo),
            "\n".join(
                "  %s:%d  [%s]" % (r, n, s_) for r, n, s_, _d in fora_de_dialogo
            ),
        )
    )
    # A forma de linha `class` que a varredura precisa ler: nome e bases
    # com generico entre colchetes, como todo modal deste repositorio
    # declara. Se a regex parar de casar com ela, `dialogo` fica preso no
    # valor da classe ANTERIOR do arquivo e a isencao vira sorte.
    casada = CLASSE.match("class ConfirmModal(ModalScreen[bool]):")
    assert casada is not None
    assert casada.group("nome") == "ConfirmModal"
    assert casada.group("bases") == "ModalScreen[bool]"


# ======================================================================
# Guarda 3: `ListView` fora do vocabulario
# ======================================================================

# Veio de `tests/ui/test_screens.py`, onde nasceu junto com a Task 5. Mora
# aqui porque e uma varredura repo-wide de VOCABULARIO, irma das outras
# quatro desta fase — e porque um guarda de gramatica escondido no meio de
# 5 mil linhas de teste de tela nao e achado por quem vai quebra-lo.
def mencoes_a_listview() -> list[str]:
    """Todo arquivo de `dbqm/ui` que ainda cita `ListView`.

    Casa por QUALQUER mencao, nao por `ListView(`: a primeira redacao so
    via o construtor e por isso passou verde por cima de tres residuos que
    nao constroem nada — um seletor CSS `Panel #panel-body ListView`
    casando com nada, um `isinstance(w, (..., ListView, ...))` cujo ramo
    nao pode disparar, e prosa de docstring narrando o widget como se
    ainda estivesse em uso. Residuo assim custa exatamente o que um guarda
    de vocabulario existe pra evitar: o proximo leitor procura o ListView
    que o codigo promete e nao acha.
    """
    return [
        _rel(arquivo)
        for arquivo in sorted(RAIZ_UI.rglob("*.py"))
        if "ListView" in arquivo.read_text(encoding="utf-8")
    ]


# Limites conhecidos, escolhidos:
#   - a varredura e por SUBSTRING no texto do arquivo: um `getattr(
#     textual.widgets, "List" + "View")` monta o nome em runtime e passa.
#     Fechar isso exigiria executar o modulo, nao le-lo;
#   - varre so `dbqm/ui`. `ListView` num teste, num script ou na CLI nao e
#     reprovado — o vocabulario que esta fase governa e o da interface;
#   - a mencao pode ser esta propria frase. Um arquivo de produto que
#     EXPLIQUE por que nao usa `ListView` seria reprovado; o lugar dessa
#     explicacao e aqui, no guarda.


def test_listview_saiu_do_vocabulario():
    """`ListView` fazia o mesmo que `OptionList` em dois lugares.

    Dois componentes para uma funcao e o que o teste de inventario da
    fase 1 reprova; a secao 5 da gramatica escolheu `OptionList`.
    """
    fontes = list(RAIZ_UI.rglob("*.py"))
    assert fontes, "varredura nao achou fonte nenhuma em %s" % RAIZ_UI
    achados = mencoes_a_listview()
    assert not achados, "ListView ainda mencionado em: %s" % achados


# ======================================================================
# Infra comum dos guardas de AST
# ======================================================================
#
# Os tres guardas abaixo leem a ARVORE, nao o texto. A troca e deliberada:
# o que eles vigiam nao e uma declaracao de CSS numa linha, e sim a forma
# de uma chamada (o argumento de `Option(...)`, o argumento de
# `add_column(...)`, o corpo de um `on_button_pressed`). Regex sobre isso
# ja falhou nesta fase — a primeira versao do guarda de centralizacao
# capturava `#buttons {` no lugar da linha da classe e teria reprovado 16
# clusters corretos sem ver nenhum dos 3 reais.
#
# O que a AST NAO ve, em qualquer um dos tres:
#   - valor montado em runtime (`"%s | %s" % ...` guardado num dict de
#     modulo, rotulo vindo de um `.json`, coluna vinda do banco);
#   - o que outra camada faz com o objeto depois (um `Option` correto que
#     um wrapper achate na hora de montar);
#   - qualquer coisa fora de `dbqm/ui` — CLI e testes nao sao varridos.


def _modulos() -> list[tuple[str, ast.Module]]:
    """(caminho relativo, arvore) de cada fonte de `dbqm/ui`."""
    modulos = []
    for arquivo in sorted(RAIZ_UI.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        modulos.append((_rel(arquivo), ast.parse(texto, filename=str(arquivo))))
    return modulos


def _nome_chamado(no: ast.Call) -> str:
    """`Option(...)` -> "Option"; `self.x.add_column(...)` -> "add_column"."""
    if isinstance(no.func, ast.Name):
        return no.func.id
    if isinstance(no.func, ast.Attribute):
        return no.func.attr
    return ""


# ======================================================================
# Guarda 4: item de lista achatado numa string
# ======================================================================

# Os construtores de item de lista do produto. `Option` e `Selection` sao
# do Textual; `OpcaoNomeada` e o nosso (dbqm/ui/widgets/lista_hierarquica.py).
CONSTRUTORES_DE_ITEM = {"Option", "OpcaoNomeada", "Selection"}

# Isencoes por (arquivo, construtor), com o motivo MEDIDO escrito.
ACHATADO_ISENTOS = {
    # `SelectionList` (checklist de conexoes do group_exec) pinta SO A
    # PRIMEIRA LINHA do prompt: montei um `Selection(item_hierarquico(
    # "MGORA7ORA9", "oracle - host:1521/svc"), ...)` num app de teste a
    # 60x20 e a linha de desambiguacao simplesmente nao foi desenhada — o
    # item aparece como `▐X▌ MGORA7ORA9` e o alvo some. Aplicar a
    # hierarquia aqui nao deixaria o item mais legivel: APAGARIA o dado
    # que hoje ele mostra. Enquanto o checklist for `SelectionList`, a
    # string unica e a forma menos ruim, e a saida real e trocar o widget
    # — decisao de fluxo, fora do escopo desta fase (secao 11 do spec).
    ("dbqm/ui/screens/group_exec.py", "Selection"),
}

# Limites conhecidos, escolhidos:
#   - a resolucao de variavel e por NOME, no arquivo inteiro, sem escopo:
#     `label = f"..."` numa funcao e `Selection(label, ...)` noutra se
#     misturam, e a ultima atribuicao vence. Foi o suficiente para pegar o
#     unico caso real (group_exec) e um resolvedor de escopo de verdade
#     seria mais codigo do que o guarda inteiro. Se um falso positivo
#     aparecer, o caminho e o escopo, nao afrouxar a regra;
#   - so UM nivel de indirecao: `a = f"{x} {y}"; b = a; Option(b)` escapa;
#   - `f"{x}"` com UM campo passa de proposito — e identidade com prefixo
#     (`f"📄  {t.name}"` na barra de templates), nao metadado colado. E de
#     DOIS campos numa linha que nasce o `nome (tipo - alvo) | descricao`
#     que a secao 5 proibe;
#   - a isencao e por (arquivo, construtor): um SEGUNDO `Selection`
#     achatado no mesmo arquivo tambem passaria. Em compensacao um
#     `Selection` achatado em QUALQUER outro arquivo e reprovado.


def _campos_interpolados(no: ast.JoinedStr) -> int:
    return sum(1 for parte in no.values if isinstance(parte, ast.FormattedValue))


def _operandos_da_soma(no: ast.AST) -> list[ast.AST]:
    """Achata `a + b + c` na lista de operandos."""
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        return _operandos_da_soma(no.left) + _operandos_da_soma(no.right)
    return [no]


def _achatamento(no: ast.AST) -> str:
    """Descreve o achatamento, ou "" se o no nao achata nada."""
    if isinstance(no, ast.JoinedStr):
        campos = _campos_interpolados(no)
        if campos >= 2:
            return "f-string com %d campos numa linha so" % campos
        return ""
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        partes = _operandos_da_soma(no)
        colas = [
            p.value
            for p in partes
            if isinstance(p, ast.Constant)
            and isinstance(p.value, str)
            and p.value.strip()
        ]
        variaveis = [p for p in partes if not isinstance(p, ast.Constant)]
        if colas and variaveis:
            return "concatenacao com separador %r" % colas[0]
    return ""


def rotulos_achatados() -> list[tuple[str, int, str, str]]:
    """Todo item de lista montado como uma string unica.

    Devolve `(arquivo, linha, construtor, motivo)`.
    """
    achados: list[tuple[str, int, str, str]] = []
    for rel, modulo in _modulos():
        # Uma indirecao: `label = f"..."` e depois `Selection(label, ...)`.
        # Sem isto, mover a f-string para uma variavel desarma o guarda —
        # e e exatamente assim que o unico caso real do produto esta
        # escrito.
        atribuicoes: dict[str, ast.AST] = {}
        for no in ast.walk(modulo):
            if isinstance(no, ast.Assign) and len(no.targets) == 1:
                alvo = no.targets[0]
                if isinstance(alvo, ast.Name):
                    atribuicoes[alvo.id] = no.value
        for no in ast.walk(modulo):
            if not isinstance(no, ast.Call) or not no.args:
                continue
            construtor = _nome_chamado(no)
            if construtor not in CONSTRUTORES_DE_ITEM:
                continue
            primeiro = no.args[0]
            if isinstance(primeiro, ast.Name):
                primeiro = atribuicoes.get(primeiro.id, primeiro)
            motivo = _achatamento(primeiro)
            if not motivo:
                continue
            if (rel, construtor) in ACHATADO_ISENTOS:
                continue
            achados.append((rel, no.lineno, construtor, motivo))
    return achados


def test_a_varredura_de_rotulo_ve_os_construtores_de_item():
    """Um guarda que nao acha construtor nenhum nao vigia lista nenhuma."""
    vistos = {
        _nome_chamado(no)
        for _rel_, modulo in _modulos()
        for no in ast.walk(modulo)
        if isinstance(no, ast.Call)
    }
    assert CONSTRUTORES_DE_ITEM <= vistos, (
        "construtor de item de lista sumiu do produto: %s"
        % (CONSTRUTORES_DE_ITEM - vistos)
    )
    # A forma que o guarda precisa reconhecer, verificada aqui e nao so
    # confiada: dois campos numa string sao achatamento, um campo nao.
    dois = ast.parse('Option(f"{a} | {b}")').body[0].value.args[0]
    um = ast.parse('Option(f"icone {a}")').body[0].value.args[0]
    assert _achatamento(dois)
    assert not _achatamento(um)


def test_rotulo_de_lista_nao_e_string_achatada():
    """Um item de lista nunca e uma string concatenada (secao 5).

    Identidade, desambiguacao e contexto sao TRES papeis; espremidos numa
    linha so, a lista quebra o texto onde couber e o olho nao distingue
    uma continuacao de uma entrada nova. Foi a queixa que originou esta
    fase. A cura e `item_hierarquico`, nao um separador melhor.
    """
    fora = rotulos_achatados()
    assert not fora, "item de lista achatado numa string:\n" + "\n".join(
        f"  {rel}:{n}  {construtor}(...)  {motivo}"
        for rel, n, construtor, motivo in fora
    )


# ======================================================================
# Guarda 5: tabela de resultado sem coluna-chave fixa
# ======================================================================

# Uma tabela de RESULTADO e a que descobre as proprias colunas no dado:
# `add_column(str(col))` num laco sobre o que voltou do banco. E ela que
# pode ter 1 coluna ou 36 (medido: mediana 9 nas consultas do mantenedor),
# e por isso e ela que precisa da chave fixa — o dbqm existe para COMPARAR,
# e uma linha cuja chave saiu de vista ao rolar nao compara nada.
#
# Uma tabela de esquema fixo (`add_columns("#", "Nome", "Descricao")`) foi
# escrita por alguem que sabia a largura dela; nao entra nesta regra.
def _colunas_dinamicas(escopo: ast.AST) -> list[tuple[int, str, ast.Call]]:
    """`add_column(...)` cujo nome de coluna nao e literal, neste escopo.

    Devolve `(linha, argumento, chamada)`.
    """
    dinamicas: list[tuple[int, str, ast.Call]] = []
    for no in ast.walk(escopo):
        if not (isinstance(no, ast.Call) and _nome_chamado(no) in {
            "add_column",
            "add_columns",
        }):
            continue
        for arg in no.args:
            literal = isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            if not literal:
                dinamicas.append((no.lineno, ast.unparse(arg), no))
                break
    return dinamicas


def _fixa_a_chave(escopo: ast.AST) -> bool:
    for no in ast.walk(escopo):
        if isinstance(no, ast.Attribute) and no.attr == "fixed_columns":
            return True
        if isinstance(no, ast.keyword) and no.arg == "fixed_columns":
            return True
    return False


def tabelas_de_resultado_sem_chave_fixa() -> list[tuple[str, int, str]]:
    """Funcao que monta coluna a partir de dado e nao fixa a chave.

    Devolve `(arquivo, linha, coluna_dinamica)`.

    A granularidade e a FUNCAO, e nao o arquivo — a primeira redacao deste
    guarda media por arquivo e passava nos dois estados: apagando a
    fixacao de `_render_flat` em `group_result.py`, o `fixed_columns` de
    `_render_pivoted`, no mesmo arquivo, mantinha o guarda verde. Guarda
    que passa com a regra quebrada e pior que guarda nenhum, e este foi
    pego pelo teste de quebra da propria tarefa que o escreveu.
    """
    achados: list[tuple[str, int, str]] = []
    for rel, modulo in _modulos():
        pais: dict[int, ast.AST] = {}
        nos: dict[int, ast.AST] = {}
        for pai in ast.walk(modulo):
            for filho in ast.iter_child_nodes(pai):
                pais[id(filho)] = pai
                nos[id(filho)] = filho
        for linha, arg, chamada in _colunas_dinamicas(modulo):
            # Escopo = a funcao mais interna que contem a chamada (ou o
            # modulo, se ela estiver solta). A chave pode ser fixada ali
            # ou em qualquer funcao que a envolva — as duas leituras sao
            # legiveis; o que o guarda recusa e a fixacao morar noutro
            # ramo do arquivo.
            escopos: list[ast.AST] = []
            atual = pais.get(id(chamada))
            while atual is not None:
                if isinstance(atual, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    escopos.append(atual)
                atual = pais.get(id(atual))
            if not escopos:
                escopos = [modulo]
            if not any(_fixa_a_chave(e) for e in escopos):
                achados.append((rel, linha, arg))
    return achados


# Limites conhecidos, escolhidos:
#   - a granularidade e a FUNCAO que monta as colunas (mais as que a
#     envolvem), nao o objeto `DataTable`. Uma tela que montasse as
#     colunas num metodo e fixasse a chave em OUTRO metodo irmao seria
#     reprovada por engano — e a saida certa e mover a fixacao para junto
#     das colunas, que e onde ela e legivel. Seguir o objeto entre metodos
#     (`query_one("#tabela")` num, `mount` noutro) e aliasing que a AST
#     sozinha nao resolve;
#   - `fixed_columns` MENCIONADO na funcao ja satisfaz: o guarda nao le o
#     valor. Que o valor esteja certo (1 quando ha mais de uma coluna, 0
#     quando ha uma so) e o que os testes de renderizacao em
#     `tests/ui/test_widgets.py` afirmam — rolando a tabela de verdade e
#     lendo o que ficou pintado, nao o atributo;
#   - uma coluna cujo nome venha de constante de modulo (`add_column(TITULO)`)
#     conta como dinamica e pede chave fixa. Falso positivo possivel,
#     ainda nao observado: a saida e escrever o literal ou fixar a chave,
#     e nenhuma das duas piora a tela;
#   - tabela de ESQUEMA FIXO fica de fora por desenho (`add_columns("#",
#     "Nome", ...)`). Quem escreveu os literais sabia a largura deles; a
#     regra da secao 6 existe para a tabela que descobre as colunas no
#     dado e pode ter 1 ou 36.


def test_a_varredura_de_tabela_encontra_as_colunas():
    """Se ninguem mais monta coluna, este guarda parou de vigiar."""
    total = 0
    for _rel_, modulo in _modulos():
        for no in ast.walk(modulo):
            if isinstance(no, ast.Call) and _nome_chamado(no) in {
                "add_column",
                "add_columns",
            }:
                total += 1
    assert total > 15, "varredura rasa demais: %d chamadas de coluna" % total


def test_tabela_de_resultado_fixa_a_coluna_chave():
    """Rolar sem fixar a chave destroi a comparacao (secao 6)."""
    fora = tabelas_de_resultado_sem_chave_fixa()
    assert not fora, "tabela de resultado sem chave fixa:\n" + "\n".join(
        f"  {rel}:{n}  add_column({arg})" for rel, n, arg in fora
    )


# ======================================================================
# Guarda 6: botao que navega
# ======================================================================
#
# A outra metade da secao 7: "botao e acao, nunca navegacao nem menu". A
# metade do menu foi resolvida na Task 8 (`Ferramentas` e o seletor de
# modo do `config_port` viraram lista escolhivel) e a da centralizacao tem
# o guarda 2. Esta faltava guarda nenhum — e a nota de escopo da Task 8
# dizia que UM call-to-action navegava. Sao QUATRO. Foi o que decidiu
# construir este guarda em vez de deixar a regra para revisao humana: uma
# regra sem guarda ja errou a propria contagem por fator 4 na semana em
# que foi escrita.

# O que e navegar: trocar de aba do shell, ou abrir outra ferramenta.
NAVEGACAO = {"action_switch_tab", "open_tool"}

# Isencoes por (arquivo, id do botao), com o motivo escrito. Os quatro
# CTAs abaixo sao estados vazios: `EmptyState` (dbqm/ui/widgets/empty_state.py)
# EXIGE `acao_rotulo` e `acao_id` — os quatro parametros sao obrigatorios
# de proposito, para impedir "Nenhuma consulta configurada" sem oferecer a
# saida. Quando a saida honesta de um estado vazio esta noutra aba (nao ha
# consulta para criar AQUI; ela nasce na Coleta), o unico jeito de honrar
# o contrato e navegar.
#
# Deixar os quatro assim foi decisao, nao esquecimento: tornar a acao
# opcional muda o contrato de `EmptyState` em 14 call sites e e mudanca de
# fluxo, fora do escopo da gramatica de layout (secao 11 do spec). O que
# este guarda entrega enquanto isso e o TETO: sao quatro, estao nomeados,
# e o quinto reprova a suite.
NAVEGACAO_ISENTA = {
    # "Executar consulta" -> aba Consultas. Nao ha historico para criar
    # aqui; ele nasce de uma execucao noutra aba.
    ("dbqm/ui/screens/history.py", "executar-consulta"),
    # "Criar consulta" -> aba Coleta. Consulta se salva de la ("Salvar
    # como consulta"), nunca desta tela.
    ("dbqm/ui/screens/query_exec.py", "criar-consulta-coleta"),
    # "Gerenciar grupos" -> ferramenta Grupos. Esta tela EXECUTA grupos;
    # criar e trabalho da ferramenta ao lado.
    ("dbqm/ui/screens/group_run.py", "gerenciar-grupos"),
    # "Abrir Ferramentas" -> aba Ferramentas. A barra de templates mostra
    # templates; eles se criam na ferramenta Templates.
    ("dbqm/ui/widgets/templates_sidebar.py", "abrir-ferramentas"),
}

# Limites conhecidos, escolhidos:
#   - so o corpo do handler de botao e lido. Um handler que chame
#     `self._ir_para_consultas()`, e ESSE metodo troque de aba, passa: a
#     AST nao segue chamada entre metodos, e segui-la exigiria um grafo de
#     chamadas do modulo inteiro;
#   - o id do botao sai da comparacao literal (`if event.button.id ==
#     "x"`). Um handler que resolva o id por variavel ou por dict e
#     reportado com id vazio — e id vazio nao casa com isencao nenhuma,
#     entao reprova. E o lado seguro: obscurecer o id nao compra silencio;
#   - `action_switch_tab` chamado de um handler de TECLA, de `on_mount` ou
#     do `OptionList` nao e reprovado, e isso e a regra e nao um furo:
#     lista, aba e atalho SAO navegacao legitima. So botao nao e;
#   - a lista de verbos e fechada (`NAVEGACAO`). Um terceiro jeito de
#     navegar que apareca amanha precisa ser acrescentado aqui — e o mesmo
#     custo que `MOLDURAS` e `CONSTRUTORES_DE_ITEM` ja pagam.


def _e_handler_de_botao(no: ast.AST) -> bool:
    if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    if no.name.startswith("on_button_pressed"):
        return True
    # Tambem pelo TIPO do parametro e pelo decorador: um handler renomeado
    # (`@on(Button.Pressed)` ou `def _cliquei(self, e: Button.Pressed)`)
    # continua sendo handler de botao.
    anotacoes = [ast.unparse(a.annotation) for a in no.args.args if a.annotation]
    decoradores = [ast.unparse(d) for d in no.decorator_list]
    return any("Button.Pressed" in t for t in anotacoes + decoradores)


def _ids_do_ramo(no: ast.AST, pais: dict[ast.AST, ast.AST], raiz: ast.AST) -> set[str]:
    """Os ids de botao comparados no `if` que envolve *no*."""
    ids: set[str] = set()
    atual = pais.get(no)
    while atual is not None and atual is not raiz:
        if isinstance(atual, ast.If):
            for teste in ast.walk(atual.test):
                if isinstance(teste, ast.Constant) and isinstance(teste.value, str):
                    ids.add(teste.value)
        atual = pais.get(atual)
    return ids


def botoes_que_navegam() -> list[tuple[str, int, str, str]]:
    """Todo handler de botao que troca de aba ou abre outra ferramenta.

    Devolve `(arquivo, linha, id do botao, verbo de navegacao)`.
    """
    achados: list[tuple[str, int, str, str]] = []
    for rel, modulo in _modulos():
        for handler in ast.walk(modulo):
            if not _e_handler_de_botao(handler):
                continue
            pais: dict[ast.AST, ast.AST] = {}
            for pai in ast.walk(handler):
                for filho in ast.iter_child_nodes(pai):
                    pais[filho] = pai
            for no in ast.walk(handler):
                verbo = ""
                if isinstance(no, ast.Attribute) and no.attr in NAVEGACAO:
                    verbo = no.attr
                elif isinstance(no, ast.Name) and no.id in NAVEGACAO:
                    verbo = no.id
                elif (
                    isinstance(no, ast.Constant)
                    and isinstance(no.value, str)
                    and no.value in NAVEGACAO
                ):
                    # `getattr(self.app, "action_switch_tab", None)` — a
                    # forma que os quatro CTAs reais usam.
                    verbo = no.value
                if not verbo:
                    continue
                ids = _ids_do_ramo(no, pais, handler) - NAVEGACAO
                botao = sorted(ids)[0] if ids else ""
                if (rel, botao) in NAVEGACAO_ISENTA:
                    continue
                achados.append((rel, no.lineno, botao, verbo))
    return achados


def test_a_varredura_de_navegacao_ve_os_handlers():
    """Um guarda que nao acha handler de botao nao vigia botao nenhum."""
    handlers = [
        no
        for _rel_, modulo in _modulos()
        for no in ast.walk(modulo)
        if _e_handler_de_botao(no)
    ]
    assert len(handlers) > 15, "varredura rasa demais: %d handlers" % len(handlers)
    # As isencoes valem por SER reais: se um CTA isento deixar de navegar
    # (ou de existir), a isencao vira letra morta e o teto de quatro deixa
    # de ser um teto medido.
    sem_isencao = {(rel, botao) for rel, _n, botao, _v in _botoes_que_navegam_cru()}
    assert NAVEGACAO_ISENTA <= sem_isencao, (
        "isencao que nao corresponde a nenhum botao real: %s"
        % (NAVEGACAO_ISENTA - sem_isencao)
    )


def _botoes_que_navegam_cru() -> list[tuple[str, int, str, str]]:
    """`botoes_que_navegam()` sem aplicar as isencoes."""
    guardadas = set(NAVEGACAO_ISENTA)
    NAVEGACAO_ISENTA.clear()
    try:
        return botoes_que_navegam()
    finally:
        NAVEGACAO_ISENTA.update(guardadas)


def test_botao_nao_navega():
    """Botao e acao, nunca navegacao (secao 7).

    Navegar e trabalho de aba, de lista e de atalho. Um botao que troca de
    aba promete "isto opera o que voce esta vendo" e faz outra coisa —
    alem de fazer o proximo layout crescer um botao-menu, que foi o que a
    Task 8 acabou de desfazer.
    """
    fora = botoes_que_navegam()
    assert not fora, "botao usado como navegacao:\n" + "\n".join(
        f"  {rel}:{n}  [{botao or '?'}]  -> {verbo}" for rel, n, botao, verbo in fora
    )
