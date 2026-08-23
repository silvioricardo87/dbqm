"""Temas do Textual, construidos a partir de dbqm/design/tokens.py, mais o
CSS global de estados inertes (INERT_STATES_CSS) que os consome.

Nenhuma cor e escrita aqui: este modulo so traduz os tokens semanticos para o
formato que o Textual espera. Trocar a paleta e trocar tokens.py.

INERT_STATES_CSS vive aqui, nao em dbqm/ui/app.py, porque DBQMApp e
ThemedTestApp (tests/ui/_helpers.py) sao irmas — as duas estendem
textual.app.App diretamente, sem parentesco entre si — entao uma constante
definida so em DBQMApp nunca chegaria aos testes de tela que montam
ThemedTestApp. As duas importam daqui.
"""
from __future__ import annotations

from textual.theme import Theme

from dbqm.design.tokens import THEMES

# Nomes gravados em settings.json antes do design system.
LEGACY_NAMES: dict[str, str] = {
    "github-dark": "plano-escuro",
    "github-light": "plano-claro",
}

DEFAULT_THEME = "plano-escuro"

# Estados inertes distintos (Task 12): um controle desabilitado e uma acao
# indisponivel agora — o motivo precisa estar alcancavel, nunca so a cor;
# somente-leitura e conteudo para consumir, nao um formulario quebrado. As
# duas regras usam tokens diferentes (texto-desabilitado vs texto-apoio) e a
# segunda tambem tira borda/fundo de controle, para que as duas nunca fiquem
# visualmente iguais — o defeito que esta tarefa existe para prevenir.
#
# Vive aqui (nao em app.py) e e consumido tanto por `DBQMApp.DEFAULT_CSS`
# quanto por `tests/ui/_helpers.py::ThemedTestApp.DEFAULT_CSS`: as duas Apps
# nao tem parentesco entre si (irmas, ambas direto de `textual.app.App`), e
# so `DEFAULT_CSS` se combina ao longo da MRO sem apagar o que uma subclasse
# ad-hoc de teste declarar por conta propria — `CSS` (atributo unico, sem
# merge) apagaria isso.
INERT_STATES_CSS = """
*:disabled { color: $ds-text-disabled; }
.-read-only { color: $ds-text-muted; border: none; background: $ds-panel; }
"""


def _build_theme(name: str, tokens: dict[str, str], dark: bool) -> Theme:
    """Traduz os tokens semanticos para um Theme do Textual.

    Todo token vira variavel de CSS, inclusive os que tambem alimentam um
    campo nomeado do Theme: os componentes referenciam sempre `$token`, e os
    campos nomeados existem so para os widgets embutidos do Textual.

    Os campos nomeados (`warning`, `error`, `success`) sao eixo OPERACAO,
    nunca eixo VEREDITO — eles pintam toast/notify e outros widgets nativos
    do Textual que nao tem nocao de "estes dois dados diferem", so de
    "esta acao falhou/teve sucesso/e um aviso". Alimenta-los com
    `veredito-*` pinta chrome e notificacoes com a cor de um resultado de
    comparacao, e destrava a alavanca de rollback documentada: reverter
    `veredito-igual` para verde pintaria de verde toda notificacao de
    sucesso, exatamente a superficie que o desenho manda deixar sem cor.
    Por isso `success` e `warning` mapeiam para `texto-apoio` (sucesso sem
    tinta, aviso informativo sem tinta) e so `error` usa um token de
    operacao (`op-falha`).
    """
    return Theme(
        name=name,
        primary=tokens["ds-identity"],
        secondary=tokens["ds-text-muted"],
        accent=tokens["ds-identity"],
        warning=tokens["ds-text-muted"],
        error=tokens["ds-op-failure"],
        success=tokens["ds-text-muted"],
        foreground=tokens["ds-text"],
        background=tokens["ds-background"],
        surface=tokens["ds-surface"],
        panel=tokens["ds-panel"],
        dark=dark,
        variables=dict(tokens),
    )


TEXTUAL_THEMES: dict[str, Theme] = {
    "plano-escuro": _build_theme("plano-escuro", THEMES["plano-escuro"], dark=True),
    "plano-claro": _build_theme("plano-claro", THEMES["plano-claro"], dark=False),
}


def get_theme(name: str) -> Theme:
    """Devolve um tema pelo nome, aceitando os nomes antigos e caindo no padrao."""
    name_ = LEGACY_NAMES.get(name, name)
    return TEXTUAL_THEMES.get(name_, TEXTUAL_THEMES[DEFAULT_THEME])
