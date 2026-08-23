"""Guardas da gramatica de layout (fase 2).

Fase 1 vigiou a **cor**; esta vigia a **estrutura**. O primeiro guarda:
`Panel` (e `Dialog`, seu equivalente modal) e a unica moldura de secao do
produto. Uma tela que desenha a propria caixa cria um terceiro vocabulario
de moldura — foi exatamente assim que o produto chegou a tres.
"""
from __future__ import annotations

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
    # vazia a direita. As acoes DENTRO dele nao estao isentas — a isencao
    # e por seletor, entao um `.empty-acoes { align: center }` novo
    # continua sendo reprovado.
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


def clusters_centralizados() -> list[tuple[str, int, str, str]]:
    """Toda centralizacao de layout fora de um dialogo.

    Devolve `(arquivo, linha, seletor, declaracao)`.
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
                if (rel, seletor) in CENTRO_ISENTOS:
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
    assert len(clusters_centralizados()) < total / 2, (
        "a deteccao de dialogo parou de isentar os modais"
    )
    # A forma de linha `class` que a varredura precisa ler: nome e bases
    # com generico entre colchetes, como todo modal deste repositorio
    # declara. Se a regex parar de casar com ela, `dialogo` fica preso no
    # valor da classe ANTERIOR do arquivo e a isencao vira sorte.
    casada = CLASSE.match("class ConfirmModal(ModalScreen[bool]):")
    assert casada is not None
    assert casada.group("nome") == "ConfirmModal"
    assert casada.group("bases") == "ModalScreen[bool]"
