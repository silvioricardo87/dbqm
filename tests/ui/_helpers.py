"""Infra compartilhada para testes de UI.

`ThemedTestApp` existe para que os harnesses ad-hoc dos testes (`class
XxxTestApp(App)` espalhados por test_screens.py/test_modals.py/test_widgets.py)
montem os mesmos temas que a DBQMApp real registra em __init__ — sem isso,
qualquer DEFAULT_CSS que use um token puro (ex.: $borda, que ao contrario de
$accent/$primary nao e variavel embutida do Textual) quebra a montagem do
widget.

Deliberadamente NAO e um fixture autouse global: uma versao anterior deste
modulo monkeypatchava `App.__init__` para toda App de teste, e isso mascarava
a propria regressao que motivou esta infra — o teste continuava verde mesmo
removendo o registro de tema da DBQMApp, porque o fixture reaplicava o
registro por fora. Cada harness precisa herdar de ThemedTestApp explicitamente,
para que so a DBQMApp real prove que registra e ativa o tema sozinha.
"""
from __future__ import annotations

import re

from textual.app import App

from dbqm.ui.theme import ESTADOS_INERTES_CSS, PADRAO, TEMAS_TEXTUAL


class ThemedTestApp(App):
    """Base para App de teste: registra e ativa os temas do design system."""

    # Espelha `DBQMApp.DEFAULT_CSS` (Task 12): sem isso, um harness ad-hoc
    # que monta `.-somente-leitura`/`disabled=True` nao veria a distincao
    # visual entre os dois — a mesma classe de lacuna que motivou este
    # arquivo para os temas.
    DEFAULT_CSS = ESTADOS_INERTES_CSS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for tema in TEMAS_TEXTUAL.values():
            self.register_theme(tema)
        self.theme = PADRAO


_ESTRELAS = "★☆ "


def nomes_renderizados(option_list) -> list[str]:
    """Os nomes de uma lista de consultas/grupos como ela os PINTA.

    Le a primeira linha (a identidade, na gramatica de `item_hierarquico`)
    do `prompt` de cada opcao montada, sem a estrela de favorito. Existe
    porque a alternativa obvia — ler `Option.id` — mede um atributo e nao
    o que a pessoa ve: os nomes deixaram de viajar no `id` justamente
    porque dois itens de mesmo nome derrubavam a tela inteira com
    `DuplicateID`, e um teste que le `id` teria seguido verde enquanto a
    lista nao montava mais.
    """
    nomes = []
    for i in range(option_list.option_count):
        prompt = option_list.get_option_at_index(i).prompt
        texto = prompt.plain if hasattr(prompt, "plain") else str(prompt)
        linhas = texto.splitlines() or [""]
        nomes.append(linhas[0].lstrip(_ESTRELAS).rstrip())
    return nomes


_ESCAPES_SVG = {"&#160;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"'}


def texto_renderizado(app) -> str:
    """O texto que a tela REALMENTE pinta, linha a linha.

    Le o SVG de `App.export_screenshot()` — que so contem o que coube na
    viewport — e devolve o texto dos `<text>` com o escape desfeito. Existe
    porque `widget.region` mente sobre visibilidade: a secao Oracle da tela
    de Configuracoes tinha `region.height == 3` e ainda assim nao aparecia,
    recortada por um ancestral com `overflow: hidden`. Um teste que afirma
    `region.height > 0` passa com o defeito presente.

    O `\xa0` do SVG vira espaco comum para que a busca por uma frase
    ("Client em uso") funcione como a pessoa a le.
    """
    svg = app.export_screenshot()
    linhas = []
    for bruto in re.findall(r">([^<>]*)</text>", svg):
        texto = bruto
        for de, para in _ESCAPES_SVG.items():
            texto = texto.replace(de, para)
        linhas.append(texto.replace("\xa0", " "))
    return "\n".join(linhas)


def linhas_renderizadas(app) -> list[str]:
    """As linhas da tela como o compositor as PINTA, com posicao.

    Complementa `texto_renderizado`: aquele acha uma frase, este diz o que
    ha em (x, y) — o que e o unico jeito de afirmar sobre MOLDURA, que nao
    e texto. `Region.height` de um painel nao prova que a linha de baixo
    foi desenhada: `#er-select-phase` media 24 de altura numa tela de 24
    linhas comecando em y=1, e a borda inferior simplesmente nao existia.
    """
    return [
        "".join(segmento.text for segmento in faixa)
        for faixa in app.screen._compositor.render_strips()
    ]


def recorte(app, widget) -> list[str]:
    """As linhas pintadas dentro da regiao de *widget*."""
    linhas = linhas_renderizadas(app)
    r = widget.region
    return [linha[r.x : r.x + r.width] for linha in linhas[r.y : r.y + r.height]]
