r"""hierarchical_item — item de lista com hierarquia de ate tres linhas.

O problema que este componente resolve (gramatica de layout, Task 3): uma
lista de conexoes com mais de duas linhas ficava ilegivel porque identidade e
metadado disputavam a mesma linha — `connections.py` montava
`nome (tipo - alvo) | descricao` como uma unica string, a lista quebrava essa
string onde coubesse na largura disponivel, e sem hierarquia visual o olho nao
distinguia uma continuacao de uma entrada nova. `query_list.py` tinha o mesmo
problema e um remendo em cima dele: truncar a descricao em 35 caracteres com o
comentario "keep line readable".

A cura nao e um separador — e hierarquia. Cada linha diz o que ela e pela
cor, nao por pontuacao:
  1. identidade — o que a pessoa esta procurando, em negrito, sozinha.
  2. desambiguacao — tipo, alvo, conexao; recuada, em $ds-text-muted.
  3. contexto — descricao; recuada, em $ds-text-disabled; opcional.

Linhas vazias sao omitidas, nao renderizadas em branco: um item so com
identidade fica com uma unica linha, nao com duas linhas fantasmas.

Nome de conexao e descricao sao dado do usuario, e o texto e livre — uma tag
de ambiente (`Proposta [PROD]`) ou referencia de ticket com colchete e padrao
plausivel neste dominio. Por isso o `Content` e montado programaticamente com
`Content.assemble`/tuplas `(texto, estilo)`, nunca passando o dado do usuario
pelo parser de markup (`Content.from_markup`/`[tag]...[/]`): o parser nunca
ve o texto, entao nao ha nada para interpretar como tag e nada para escapar.
Isso evita de raiz a assimetria conhecida do parser do Textual entre `\[` e
`\]` (documentada em `result_table.py`, onde a compensacao de largura foi
construida em cima desse comportamento) sem tocar em `escape_markup` — que e
compartilhada com seis outros chamadores e nao e usada aqui.

Ao lado do `Content`, o modulo entrega o par `wrap_width` /
`wrap_lines`, que e o que torna a hierarquia verdadeira em texto
longo: sem pre-quebra em `\n`, a continuacao de uma linha larga demais
volta para a coluna 0 — a coluna da identidade da entrada SEGUINTE — e o
defeito reaparece inteiro. A conta mora aqui, e nao em cada tela, porque
so depende do CSS de `Panel`/`OptionList`; a largura do painel e que fica
com a tela.

E entrega tambem `NamedOption` — a `Option` que leva esse conteudo pro
`OptionList` carregando o nome do item como dado, e nao como `id`. A
razao esta na docstring da classe.
"""
from __future__ import annotations

import textwrap

from textual.content import Content
from textual.widgets.option_list import Option

_INDENT = "  "


# ----------------------------------------------------------------------
# Largura de quebra — a conta que todo chamador que pre-quebra texto
# precisa fazer, num lugar so.
#
# Quem pre-quebra (ver `wrap_lines` e a docstring de
# `hierarchical_item`) precisa saber quantas colunas sobram para o TEXTO
# dentro de um `OptionList` que vive num `Panel`. Cada parcela abaixo e
# lida do CSS que a declara, nenhuma medida em runtime:
#
#   - `Panel` (dbqm/ui/widgets/panel.py): `border: round` = 1 coluna de
#     cada lado.
#   - `Panel > #panel-body`: `padding: 1 1` = 1 coluna de cada lado
#     (vertical, horizontal); o horizontal e o que importa aqui.
#   - `OptionList` (textual.widgets, DEFAULT_CSS): `padding: 0 1` = 1
#     coluna de cada lado; a borda propria dela (`border: tall`) e zerada
#     por `Panel #panel-body OptionList { border: none; }`, entao nao
#     entra nesta conta.
#
# Cada "de cada lado" vale 2 (esquerda + direita).
_PANEL_BORDER = 2
_PANEL_BODY_PADDING = 2
_OPTION_LIST_PADDING = 2

# A barra de rolagem vertical do OptionList — 2 colunas, o padrao do
# proprio Textual (`Widget().styles.scrollbar_size_vertical == 2`; nenhuma
# das listas sobrescreve `scrollbar-size-vertical`, entao vale o padrao).
# So aparece quando a lista transborda verticalmente, o que depende de
# quantos itens existem — fora do controle de quem monta a tela.
# Descontada INCONDICIONALMENTE: o pior caso (lista rolavel) e o caso
# comum em uso real, e nao descontar significa que a largura calculada so
# bate pra uma lista curta demais pra rolar.
#
# Esta e a parcela que custou quatro rodadas na lista de Conexoes, e o
# motivo esta na assimetria da API do Textual: `content_region` NAO
# desconta a barra de rolagem, `scrollable_content_region` desconta. Uma
# largura derivada de `content_region` medido numa lista curta passa em
# teste e sai errada em uso — foi assim que a linha "...ambiente" saiu
# sem recuo, alinhada com a coluna de identidade da entrada seguinte.
# Quem for reverificar esta conta: meca com a lista REALMENTE rolando
# (`show_vertical_scrollbar is True`) e leia `scrollable_content_region`.
_VERTICAL_SCROLLBAR = 2

# O recuo que `_indented_field` antepoe a CADA linha de
# desambiguacao/contexto. Entra na conta porque a largura util e a do
# texto, nao a da linha: pre-quebrar em N colunas e depois somar o recuo
# devolve N+2 colunas de linha, que e exatamente 2 a mais do que cabe.
_CONTEXT_INDENT = len(_INDENT)


def wrap_width(panel_width: int) -> int:
    """Colunas de TEXTO disponiveis num item de lista, dado o painel.

    Recebe a largura do `Panel` que hospeda o `OptionList` (o valor que o
    CSS da tela declara) e devolve o que sobra para o texto depois da
    borda do Panel, do padding do corpo, do padding do OptionList, da
    barra de rolagem (pior caso) e do recuo que a propria linha paga.

    A largura do painel FICA COM A TELA — Conexoes e Consultas tem
    paineis de tamanhos diferentes e assim deve ser (um e a coluna
    esquerda de um master-detail, o outro e a tela inteira). O que e
    compartilhado e a DERIVACAO, que so depende do CSS de `Panel` e de
    `OptionList` e e identica nos dois lugares — duplica-la seria abrir
    espaco para as duas copias divergirem quando esse CSS mudar.
    """
    return (
        panel_width
        - _PANEL_BORDER
        - _PANEL_BODY_PADDING
        - _OPTION_LIST_PADDING
        - _VERTICAL_SCROLLBAR
        - _CONTEXT_INDENT
    )


def wrap_lines(text: str, width: int) -> str:
    """Pre-quebra *texto* em `\\n` a cada *largura* colunas.

    O `\\n` e o que garante o recuo: `hierarchical_item` recua cada linha
    logica, e so elas — a quebra automatica que o Textual faz numa linha
    unica larga demais acontece no render e nao tem como ser recuada (ver
    a docstring de `hierarchical_item`). Colapsa espaco em branco antes de
    quebrar para que uma descricao com quebras proprias nao estoure a
    gramatica de uma linha por papel.
    """
    if not text:
        return ""
    flattened = " ".join(text.split())
    return "\n".join(textwrap.wrap(flattened, width=width) or [""])


def _indented_field(text: str, style: str) -> Content:
    """Monta um campo (desambiguacao ou contexto) com o recuo em TODA
    linha, nao so na primeira.

    Um campo pode chegar aqui com quebra de linha ja embutida — por
    exemplo `connections.py` pre-quebra uma descricao longa em duas
    linhas logicas antes de chamar `hierarchical_item`. Se o recuo fosse
    aplicado uma vez so, na frente do bloco inteiro (como uma unica
    `Content.assemble` faria), a segunda linha em diante ficaria alinhada
    a coluna 0 — a MESMA coluna da identidade da proxima entrada. Recuo e
    a pista de "isto pertence a entrada acima"; perde-la numa continuacao
    e o defeito que motivou esta fase inteira, so que numa escala menor.

    Cada linha vira seu proprio `Content.assemble(_INDENT, (linha, estilo))`
    — recuo como span proprio, nao espaco somado ao texto do campo por
    quem chama — e as linhas sao unidas com `Content("\n").join(...)`,
    que preserva os spans de cada uma. Nenhum espaco extra entra no
    `.plain` alem do recuo em si; `.plain` continua igual ao texto que o
    chamador passou, so que com o recuo antes de cada linha.
    """
    parts = [
        Content.assemble(_INDENT, (line, style))
        for line in text.split("\n")
    ]
    return Content("\n").join(parts)


def hierarchical_item(
    identity: str,
    disambiguation: str = "",
    context: str = "",
) -> Content:
    """Monta um item de lista com ate tres linhas de hierarquia visual.

    Devolve `Content`, nao `str`: e o que `OptionList.add_option` e
    `DataTable` aceitam sem cair no Rich puro, que levanta `MarkupError` ao
    ver um token `$nome` (o mesmo problema documentado em
    `group_result.py._status_cell`). Cada campo e um trecho estilizado via
    `Content.assemble`, nao markup parseado — o texto do usuario chega ao
    `Content` final byte a byte, sem escape e sem risco de fechar tag.

    Se `desambiguacao` ou `contexto` trouxerem `\n` (um chamador que
    pre-quebra texto longo em varias linhas logicas), CADA linha recebe o
    recuo — ver `_indented_field`. Isto NAO cobre a quebra automatica que
    o proprio Textual faz quando uma linha unica (sem `\n`) e mais larga
    que o widget: aquele wrap e feito no render, depois que este `Content`
    ja foi montado, e o Textual nao oferece um jeito de dar indentacao
    persistente a continuacao de uma linha assim. Quem quiser recuo
    garantido numa linha muito longa precisa pre-quebra-la em `\n` antes
    de chamar esta funcao — e e o que `wrap_lines` faz, na largura
    que `wrap_width` deriva (ela ja desconta o recuo que toda
    linha do campo passa a pagar). As listas de Conexoes e de Consultas
    fazem isso; e por isso que os paineis das duas tem largura fixa no
    CSS.
    """
    line = Content.assemble((identity, "bold $ds-text-strong"))
    if disambiguation:
        line = line + "\n" + _indented_field(disambiguation, "$ds-text-muted")
    if context:
        line = line + "\n" + _indented_field(context, "$ds-text-disabled")
    return line


class NamedOption(Option):
    """`Option` que carrega o nome do item como DADO, nao como `id`.

    Nome e a chave de busca do dbqm (`find_query`/`find_group`), entao a
    tentacao e passa-lo como `Option(conteudo, id=nome)` e recupera-lo em
    `event.option.id`. Mas `OptionList.add_option` levanta `DuplicateID`
    num id repetido: duas consultas de mesmo nome num `queries.json`
    editado a mao (os fluxos de criacao da UI barram duplicatas, um
    arquivo legado ou editado no editor nao) faziam a TELA INTEIRA falhar
    ao montar. Dado ambiguo continua ambiguo — nao da pra tornar a
    selecao inequivoca, e nao e papel da lista tentar; o que ela deve e
    NAO QUEBRAR: pintar as duas linhas e resolver a selecao pelo nome
    exatamente como fazia antes, deixando a ambiguidade aparecer no
    resultado da busca, nao numa tela morta.

    Guardar o nome num atributo proprio tira o `id` da jogada por
    completo: nao ha id para colidir, e `nome` continua sendo "" quando o
    dado tem nome vazio, em vez de virar `None` e produzir uma linha
    silenciosamente morta.
    """

    def __init__(self, content: Content, name: str) -> None:
        super().__init__(content)
        self.name = name
