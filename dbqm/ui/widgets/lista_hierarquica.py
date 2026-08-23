"""item_hierarquico — item de lista com hierarquia de ate tres linhas.

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
"""
from __future__ import annotations

from textual.content import Content

from dbqm.ui.utils import escape_markup

_RECUO = "  "


def item_hierarquico(
    identidade: str,
    desambiguacao: str = "",
    contexto: str = "",
) -> Content:
    """Monta um item de lista com ate tres linhas de hierarquia visual.

    Devolve `Content`, nao `str`: e o que `OptionList.add_option` e
    `DataTable` aceitam sem cair no Rich puro, que levanta `MarkupError` ao
    ver um token `$nome` (o mesmo problema documentado em
    `group_result.py._status_cell`). Cada campo passa por `escape_markup`
    antes de entrar no template — nome de conexao e descricao sao dado do
    usuario, e um valor com `[/]` nao pode fechar a tag em volta dele.
    """
    linhas = [f"[bold $texto-forte]{escape_markup(identidade)}[/]"]
    if desambiguacao:
        linhas.append(f"{_RECUO}[$texto-apoio]{escape_markup(desambiguacao)}[/]")
    if contexto:
        linhas.append(f"{_RECUO}[$texto-desabilitado]{escape_markup(contexto)}[/]")
    return Content.from_markup("\n".join(linhas))
