"""Design tokens do dbqm — camadas 1 e 2 do design system "Plano".

Este modulo e a camada mais baixa do projeto: nao importa nada de `dbqm`.
Consumidores: `ui/theme.py` (Textual), `cli.py` (Rich) e `core/html_report.py`
(CSS). Isso existe porque `core/` nao pode importar `ui/`, e foi por essa regra
que o relatorio HTML acabou inventando uma paleta propria.

NOTA DE MIGRACAO: nesta etapa os valores sao os do tema GitHub atual, de
proposito. Trocar nome e valor ao mesmo tempo torna impossivel saber de onde
veio uma regressao. A paleta Plano entra na Task 8.
"""
from __future__ import annotations

from typing import Final

# --------------------------------------------------------------- camada 1
# Primitivas: o que a cor E. Ordenadas por luminancia — numero maior e sempre
# mais escuro, para que o nome nunca contradiga o valor.
# (Nesta etapa sao os valores GitHub; a escala ardosia/neve chega na Task 8.)

# --------------------------------------------------------------- camada 2
# Tokens semanticos: o que a cor SIGNIFICA. Componentes consomem so estes.

TOKENS_ESCURO: Final[dict[str, str]] = {
    # superficies
    "fundo": "#0d1117",
    "superficie": "#090b10",
    "painel": "#161b22",
    "superficie-elevada": "#21262d",
    # estrutura
    "borda": "#30363d",
    "borda-forte": "#6e7175",
    # texto
    "texto": "#c9d1d9",
    "texto-apoio": "#a1a3a6",
    "texto-forte": "#f0f6fc",
    "texto-desabilitado": "#6e7175",
    # tinta — eixo de identidade
    "identidade": "#e3b341",
    # tinta — eixo de veredito (dados)
    "veredito-igual": "#3fb950",
    "veredito-difere": "#d29922",
    "veredito-ausente": "#f85149",
    # tinta — eixo de operacao
    "op-falha": "#f85149",
}

TOKENS_CLARO: Final[dict[str, str]] = {
    "fundo": "#f6f8fa",
    "superficie": "#ebedf0",
    "painel": "#ffffff",
    "superficie-elevada": "#eaeef2",
    "borda": "#d0d7de",
    "borda-forte": "#9e9e9e",
    "texto": "#1f2328",
    "texto-apoio": "#666666",
    "texto-forte": "#000000",
    "texto-desabilitado": "#9e9e9e",
    "identidade": "#e3b341",
    "veredito-igual": "#1a7f37",
    "veredito-difere": "#9a6700",
    "veredito-ausente": "#cf222e",
    "op-falha": "#cf222e",
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
    "veredito-igual": ("painel", "superficie", "superficie-elevada"),
    "veredito-difere": ("painel", "superficie", "superficie-elevada"),
    "veredito-ausente": ("painel", "superficie", "superficie-elevada"),
}

# Tokens julgados pelo piso de interface (3:1) em vez do de texto (4.5:1).
TOKENS_DE_INTERFACE: Final[frozenset[str]] = frozenset(
    {"texto-desabilitado", "borda-forte"}
)

PISO_TEXTO: Final[float] = 4.5
PISO_INTERFACE: Final[float] = 3.0
