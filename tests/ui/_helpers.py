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

from textual.app import App

from dbqm.ui.theme import PADRAO, TEMAS_TEXTUAL


class ThemedTestApp(App):
    """Base para App de teste: registra e ativa os temas do design system."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for tema in TEMAS_TEXTUAL.values():
            self.register_theme(tema)
        self.theme = PADRAO
