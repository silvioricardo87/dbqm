r"""item_hierarquico — item de lista com hierarquia de ate tres linhas.

O problema que este componente resolve (gramatica de layout, Task 3): uma
lista de conexoes com mais de duas linhas ficava ilegivel porque identidade e
metadado disputavam a mesma linha — `connections.py` montava
`nome (tipo - alvo) | descricao` como uma unica string, o ListView quebrava
essa string onde coubesse, e sem hierarquia visual o olho nao distinguia uma
continuacao de uma entrada nova. `query_list.py` tinha o mesmo problema e um
remendo em cima dele: truncar a descricao em 35 caracteres com o comentario
"keep line readable".

A cura nao e um separador — e hierarquia. Cada linha diz o que ela e pela
cor, nao por pontuacao:
  1. identidade — o que a pessoa esta procurando, em negrito, sozinha.
  2. desambiguacao — tipo, alvo, conexao; recuada, em $texto-apoio.
  3. contexto — descricao; recuada, em $texto-desabilitado; opcional.

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
"""
from __future__ import annotations

from textual.content import Content

_RECUO = "  "


def _campo_recuado(texto: str, estilo: str) -> Content:
    """Monta um campo (desambiguacao ou contexto) com o recuo em TODA
    linha, nao so na primeira.

    Um campo pode chegar aqui com quebra de linha ja embutida — por
    exemplo `connections.py` pre-quebra uma descricao longa em duas
    linhas logicas antes de chamar `item_hierarquico`. Se o recuo fosse
    aplicado uma vez so, na frente do bloco inteiro (como uma unica
    `Content.assemble` faria), a segunda linha em diante ficaria alinhada
    a coluna 0 — a MESMA coluna da identidade da proxima entrada. Recuo e
    a pista de "isto pertence a entrada acima"; perde-la numa continuacao
    e o defeito que motivou esta fase inteira, so que numa escala menor.

    Cada linha vira seu proprio `Content.assemble(_RECUO, (linha, estilo))`
    — recuo como span proprio, nao espaco somado ao texto do campo por
    quem chama — e as linhas sao unidas com `Content("\n").join(...)`,
    que preserva os spans de cada uma. Nenhum espaco extra entra no
    `.plain` alem do recuo em si; `.plain` continua igual ao texto que o
    chamador passou, so que com o recuo antes de cada linha.
    """
    partes = [
        Content.assemble(_RECUO, (linha, estilo))
        for linha in texto.split("\n")
    ]
    return Content("\n").join(partes)


def item_hierarquico(
    identidade: str,
    desambiguacao: str = "",
    contexto: str = "",
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
    recuo — ver `_campo_recuado`. Isto NAO cobre a quebra automatica que
    o proprio Textual faz quando uma linha unica (sem `\n`) e mais larga
    que o widget: aquele wrap e feito no render, depois que este `Content`
    ja foi montado, e o Textual nao oferece um jeito de dar indentacao
    persistente a continuacao de uma linha assim. Quem quiser recuo
    garantido numa linha muito longa precisa pre-quebra-la em `\n` antes
    de chamar esta funcao (e dimensionar a largura de quebra contando que
    agora toda linha do campo paga o recuo).
    """
    linha = Content.assemble((identidade, "bold $texto-forte"))
    if desambiguacao:
        linha = linha + "\n" + _campo_recuado(desambiguacao, "$texto-apoio")
    if contexto:
        linha = linha + "\n" + _campo_recuado(contexto, "$texto-desabilitado")
    return linha
