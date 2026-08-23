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
#
# O prefixo `ds-` nao e decoracao: sem ele, sete dos quinze nomes colidiriam
# com variaveis EMBUTIDAS do Textual — `background`, `surface`, `panel`,
# `border`, `text`, `text-muted`, `text-disabled`. Colisao ali nao e erro: o
# `Theme.variables` SOBRESCREVE o builtin de mesmo nome
# (`ColorSystem._generate` le cada um por `self.variables.get(nome, padrao)`),
# entao `$text-muted` deixaria de ser o valor derivado que os widgets nativos
# do Textual usam e viraria o nosso token, mudando pintura fora do dbqm sem
# nenhum aviso. E o codigo depende dessa separacao: `tests/design/
# test_tokens.py::DOCUMENTED_BUILTINS` existe justamente para distinguir
# "builtin do Textual" de "token nosso" no CSS.
DARK_TOKENS: Final[dict[str, str]] = {
    "ds-background": "#0b0e14",
    "ds-surface": "#0f131b",
    "ds-panel": "#151a24",
    "ds-surface-raised": "#1e2531",
    "ds-border": "#2b3342",
    "ds-border-strong": "#6b7a93",
    "ds-text": "#d5dae4",
    "ds-text-muted": "#9aa4b5",
    "ds-text-strong": "#f2f5fa",
    "ds-text-disabled": "#6b7688",
    "ds-identity": "#e3b341",
    # O dbqm nao tem verde: OK e a ausencia de tinta. Reverter o risco e
    # trocar este unico valor.
    "ds-verdict-match": "#9aa4b5",
    "ds-verdict-diff": "#ff8a5c",
    "ds-verdict-absent": "#8b9bff",
    "ds-op-failure": "#ff6b72",
}

LIGHT_TOKENS: Final[dict[str, str]] = {
    "ds-background": "#f4f6f9",
    "ds-surface": "#eaeef3",
    "ds-panel": "#ffffff",
    "ds-surface-raised": "#f2f5f8",
    "ds-border": "#d3dae3",
    "ds-border-strong": "#7b8798",
    "ds-text": "#1c2230",
    "ds-text-muted": "#5b6577",
    "ds-text-strong": "#0a0e16",
    "ds-text-disabled": "#788291",
    "ds-identity": "#7d5600",
    "ds-verdict-match": "#5b6577",
    "ds-verdict-diff": "#a83a0c",
    "ds-verdict-absent": "#3f49c4",
    "ds-op-failure": "#c02434",
}

# `plano-escuro`/`plano-claro` sao os unicos nomes PORTUGUESES que ficam, e de
# proposito: eles nao sao identificadores de codigo, sao VALORES GRAVADOS no
# `settings.json` de quem ja usa o dbqm. `ui/theme.py::LEGACY_NAMES` ja carrega
# um mapa de migracao de `github-dark`/`github-light` para eles; renomea-los
# agora quebraria a configuracao salva uma segunda vez e obrigaria a uma
# segunda camada de migracao. As CHAVES de token acima sao internas (so o
# codigo as le) e por isso foram traduzidas; estes dois nomes nao sao.
THEMES: Final[dict[str, dict[str, str]]] = {
    "plano-escuro": DARK_TOKENS,
    "plano-claro": LIGHT_TOKENS,
}

# Superficies sobre as quais texto pode ser desenhado.
SURFACES: Final[tuple[str, ...]] = (
    "ds-background", "ds-surface", "ds-panel", "ds-surface-raised",
)

# Regra do par (guia, secao 3): cada token de tinta declara sobre quais fundos
# e valido. Nenhum e valido sobre preenchimento translucido — sobre translucido,
# use o texto da superficie de baixo.
VALID_OVER: Final[dict[str, tuple[str, ...]]] = {
    "ds-text": SURFACES,
    "ds-text-muted": SURFACES,
    "ds-text-strong": SURFACES,
    "ds-text-disabled": SURFACES,
    "ds-border-strong": SURFACES,
    "ds-identity": SURFACES,
    "ds-op-failure": ("ds-panel", "ds-surface"),
    # "ds-background" entra aqui porque `core/html_report.py` desenha `.ok`/`.diff`/
    # `.absent` direto sobre `body { background: var(--ds-background) }` — o par
    # mais comum do relatorio. Ficar de fora era narrowing gratuito: o
    # teste de contraste so calcula pares declarados, entao um par
    # composto real (e o mais frequente do relatorio) ficava invisivel
    # para a catraca. Os tres passam nas duas variantes, minimo 5.42:1.
    "ds-verdict-match": ("ds-panel", "ds-surface", "ds-surface-raised", "ds-background"),
    "ds-verdict-diff": ("ds-panel", "ds-surface", "ds-surface-raised", "ds-background"),
    "ds-verdict-absent": ("ds-panel", "ds-surface", "ds-surface-raised", "ds-background"),
}

# Tokens julgados pelo piso de interface (3:1) em vez do de texto (4.5:1).
INTERFACE_TOKENS: Final[frozenset[str]] = frozenset(
    {"ds-text-disabled", "ds-border-strong"}
)

TEXT_FLOOR: Final[float] = 4.5
INTERFACE_FLOOR: Final[float] = 3.0
