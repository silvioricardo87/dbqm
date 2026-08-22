"""Design tokens do dbqm — camadas 1 e 2 do design system "Plano".

Este modulo e a camada mais baixa do projeto: nao importa nada de `dbqm`.
Consumidores: `ui/theme.py` (Textual), `cli.py` (Rich) e `core/html_report.py`
(CSS). Isso existe porque `core/` nao pode importar `ui/`, e foi por essa regra
que o relatorio HTML acabou inventando uma paleta propria.

A paleta Plano (Task 8) substitui os valores herdados do tema GitHub. As
chaves nao mudam — so os valores.
"""
from __future__ import annotations

from typing import Final

# --------------------------------------------------------------- camada 1
# Primitivas ordenadas por luminancia: numero maior e sempre mais escuro.
# ardosia (escuro): 950 #0b0e14 · 900 #0f131b · 850 #151a24 · 800 #1e2531
#                   700 #2b3342 · 500 #6b7688 · 450 #6b7a93 · 300 #9aa4b5
#                   100 #d5dae4 · 050 #f2f5fa
# neve (claro):     000 #ffffff · 050 #f4f6f9 · 100 #f2f5f8 · 150 #eaeef3
#                   300 #d3dae3 · 500 #7b8798 · 600 #788291 · 700 #5b6577
#                   900 #1c2230 · 950 #0a0e16
# tintas:  ambar 400 #e3b341 / 800 #7d5600   (identidade, linhagem SQL*Plus)
#          persimmon 400 #ff8a5c / 800 #a83a0c   (discorda)
#          indigo 400 #8b9bff / 800 #3f49c4   (ausente)
#          carmim 400 #ff6b72 / 800 #c02434   (falha)

# --------------------------------------------------------------- camada 2
# Tokens semanticos: o que a cor SIGNIFICA. Componentes consomem so estes.

TOKENS_ESCURO: Final[dict[str, str]] = {
    "fundo": "#0b0e14",
    "superficie": "#0f131b",
    "painel": "#151a24",
    "superficie-elevada": "#1e2531",
    "borda": "#2b3342",
    "borda-forte": "#6b7a93",
    "texto": "#d5dae4",
    "texto-apoio": "#9aa4b5",
    "texto-forte": "#f2f5fa",
    "texto-desabilitado": "#6b7688",
    "identidade": "#e3b341",
    # O dbqm nao tem verde: OK e a ausencia de tinta. Reverter o risco e
    # trocar este unico valor.
    "veredito-igual": "#9aa4b5",
    "veredito-difere": "#ff8a5c",
    "veredito-ausente": "#8b9bff",
    "op-falha": "#ff6b72",
}

TOKENS_CLARO: Final[dict[str, str]] = {
    "fundo": "#f4f6f9",
    "superficie": "#eaeef3",
    "painel": "#ffffff",
    "superficie-elevada": "#f2f5f8",
    "borda": "#d3dae3",
    "borda-forte": "#7b8798",
    "texto": "#1c2230",
    "texto-apoio": "#5b6577",
    "texto-forte": "#0a0e16",
    "texto-desabilitado": "#788291",
    "identidade": "#7d5600",
    "veredito-igual": "#5b6577",
    "veredito-difere": "#a83a0c",
    "veredito-ausente": "#3f49c4",
    "op-falha": "#c02434",
}

TEMAS: Final[dict[str, dict[str, str]]] = {
    "plano-escuro": TOKENS_ESCURO,
    "plano-claro": TOKENS_CLARO,
}

# Superficies sobre as quais texto pode ser desenhado.
SUPERFICIES: Final[tuple[str, ...]] = (
    "fundo", "superficie", "painel", "superficie-elevada",
)

# Regra do par (guia, secao 3): cada token de tinta declara sobre quais fundos
# e valido. Nenhum e valido sobre preenchimento translucido — sobre translucido,
# use o texto da superficie de baixo.
VALIDO_SOBRE: Final[dict[str, tuple[str, ...]]] = {
    "texto": SUPERFICIES,
    "texto-apoio": SUPERFICIES,
    "texto-forte": SUPERFICIES,
    "texto-desabilitado": SUPERFICIES,
    "borda-forte": SUPERFICIES,
    "identidade": SUPERFICIES,
    "op-falha": ("painel", "superficie"),
    # "fundo" entra aqui porque `core/html_report.py` desenha `.ok`/`.diff`/
    # `.absent` direto sobre `body { background: var(--fundo) }` — o par
    # mais comum do relatorio. Ficar de fora era narrowing gratuito: o
    # teste de contraste so calcula pares declarados, entao um par
    # composto real (e o mais frequente do relatorio) ficava invisivel
    # para a catraca. Os tres passam nas duas variantes, minimo 5.42:1.
    "veredito-igual": ("painel", "superficie", "superficie-elevada", "fundo"),
    "veredito-difere": ("painel", "superficie", "superficie-elevada", "fundo"),
    "veredito-ausente": ("painel", "superficie", "superficie-elevada", "fundo"),
}

# Tokens julgados pelo piso de interface (3:1) em vez do de texto (4.5:1).
TOKENS_DE_INTERFACE: Final[frozenset[str]] = frozenset(
    {"texto-desabilitado", "borda-forte"}
)

PISO_TEXTO: Final[float] = 4.5
PISO_INTERFACE: Final[float] = 3.0
