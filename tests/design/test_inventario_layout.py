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
