# Design System "Plano" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao dbqm um design system de três camadas em que os componentes consomem só tokens semânticos, a paleta é calibrada por contraste calculado, e quatro testes impedem a dívida de voltar.

**Architecture:** Um pacote-folha `dbqm/design/` guarda primitivas e tokens como dados puros, sem importar nada do `dbqm`. Três consumidores leem dele: `ui/theme.py` (Textual), `cli.py` (Rich) e `core/html_report.py` (CSS). A migração troca nomes antes de valores: os passos 1–7 apontam os tokens para as cores atuais e substituem 210 literais sem mudar um pixel; só o passo 8 troca os valores para a paleta Plano.

**Tech Stack:** Python ≥3.10, Textual 8.2.7, Rich, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-08-22-design-system-design.md`

## Global Constraints

- **Rótulos de UI omitem acentos** (`Historico`, `conexao`, `Nao`). Convenção do projeto, registrada no CLAUDE.md. Não "corrigir".
- **`core/` nunca importa `ui/`.** `dbqm/design/` é uma camada nova **abaixo** de ambos e não importa nada do `dbqm`.
- **Conventional Commits**, escopos `ui|core|models|config|web`. **Nunca** incluir linhas de atribuição a IA.
- **Windows-first, sem WSL.**
- **Suíte verde em todo commit.** `python -m pytest tests/ -q`. Baseline atual: **793 testes**.
- **Ciclo por tarefa:** build (`python -m build`) → testes → commit. **Bump de versão, README e PyPI só nos dois pontos de release: Task 8 (repintura, minor) e Task 12 (fechamento, minor).** Isto é uma leitura do AGENTS.md: as tarefas 1–7 e 9–11 são passos internos de uma única feature, não features separadas. Se o mantenedor preferir uma release por tarefa, ajustar antes de começar.
- **Markup de token verificado nos dois motores:** Textual resolve `[$veredito-difere]` a partir de `Theme.variables`; Rich resolve `[veredito.difere]` a partir de `rich.theme.Theme`. Ambos testados nesta versão das libs.

---

## File Structure

**Criar:**
- `dbqm/design/__init__.py` — reexporta os nomes públicos do pacote
- `dbqm/design/tokens.py` — camadas 1 e 2; dados puros, sem dependências
- `dbqm/ui/widgets/dialog.py` — componente `Dialog`
- `dbqm/ui/widgets/empty_state.py` — componente `EmptyState`
- `dbqm/ui/widgets/veredito.py` — componentes `Veredito` e `StatusOperacao`
- `tests/design/__init__.py`
- `tests/design/_contraste.py` — matemática de luminância (utilitário de teste, fora do produto)
- `tests/design/_varredura.py` — varredura de cor literal (utilitário de teste)
- `tests/design/test_tokens.py` — teste 2 (paridade)
- `tests/design/test_contraste.py` — teste 3 (contraste)
- `tests/design/test_sem_cor_literal.py` — teste 1 (cor literal, com teto)
- `tests/design/test_inventario.py` — teste 4 (inventário)

**Modificar:**
- `dbqm/ui/theme.py` — constrói `Theme` a partir de `design.tokens`; aliases dos nomes antigos
- `dbqm/cli.py` — `rich.theme.Theme` a partir dos tokens; 104 markups
- `dbqm/core/html_report.py` — custom properties do CSS a partir dos tokens
- `dbqm/ui/widgets/*.py`, `dbqm/ui/modals/*.py`, `dbqm/ui/screens/*.py` — literais → token
- `tests/ui/test_theme.py` — substituir `test_dark_palette_matches_prototype`
- `AGENTS.md` — registrar a camada `design/`
- `README.md` — features, árvore de estrutura, contagem de testes

---

### Task 1: Tokens com os valores atuais

Cria a camada de dados apontando para as cores de hoje. **Nada muda na tela.**

**Files:**
- Create: `dbqm/design/__init__.py`, `dbqm/design/tokens.py`
- Create: `tests/design/__init__.py`, `tests/design/_contraste.py`, `tests/design/test_tokens.py`, `tests/design/test_contraste.py`

**Interfaces:**
- Consumes: nada.
- Produces: `dbqm.design.tokens` com `TOKENS_ESCURO: dict[str, str]`, `TOKENS_CLARO: dict[str, str]`, `TEMAS: dict[str, dict[str, str]]`, `VALIDO_SOBRE: dict[str, tuple[str, ...]]`, `TOKENS_DE_INTERFACE: frozenset[str]`, `PISO_TEXTO: float`, `PISO_INTERFACE: float`, `SUPERFICIES: tuple[str, ...]`.

- [ ] **Step 1: Escrever o teste de paridade (falha)**

`tests/design/test_tokens.py`:

```python
"""Teste 2 do design system: paridade de tokens entre temas.

Sem ele, um tema fica com cor herdada errada e ninguem percebe ate alguem
reclamar. E a regra do guia: nenhuma cor pode ter definicao unica num tema.
"""
from dbqm.design.tokens import (
    SUPERFICIES,
    TEMAS,
    TOKENS_CLARO,
    TOKENS_ESCURO,
    VALIDO_SOBRE,
)


def test_temas_declaram_exatamente_as_mesmas_chaves():
    assert set(TOKENS_ESCURO) == set(TOKENS_CLARO)


def test_todo_tema_registrado_tem_as_mesmas_chaves():
    esperado = set(TOKENS_ESCURO)
    for nome, tokens in TEMAS.items():
        assert set(tokens) == esperado, f"tema {nome} diverge"


def test_todo_token_tem_valor_hexadecimal_explicito():
    """`auto 60%` nao e calculavel a partir do arquivo; hex e."""
    for nome, tokens in TEMAS.items():
        for chave, valor in tokens.items():
            assert valor.startswith("#") and len(valor) == 7, f"{nome}.{chave}={valor}"


def test_toda_superficie_declarada_existe_como_token():
    for tema, tokens in TEMAS.items():
        for s in SUPERFICIES:
            assert s in tokens, f"tema {tema} nao define a superficie {s}"


def test_todo_token_de_texto_declara_sobre_quais_fundos_e_valido():
    for token in VALIDO_SOBRE:
        assert token in TOKENS_ESCURO, f"{token} declarado em VALIDO_SOBRE nao existe"
        assert VALIDO_SOBRE[token], f"{token} nao declara nenhum fundo valido"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/design/test_tokens.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'dbqm.design'`

- [ ] **Step 3: Criar o pacote e os tokens com os valores ATUAIS**

`dbqm/design/tokens.py`:

```python
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
```

`dbqm/design/__init__.py`:

```python
"""Camada de design do dbqm: tokens consumidos pela TUI, pelo CLI e pelo HTML."""
from dbqm.design.tokens import (
    PISO_INTERFACE,
    PISO_TEXTO,
    SUPERFICIES,
    TEMAS,
    TOKENS_CLARO,
    TOKENS_DE_INTERFACE,
    TOKENS_ESCURO,
    VALIDO_SOBRE,
)

__all__ = [
    "PISO_INTERFACE",
    "PISO_TEXTO",
    "SUPERFICIES",
    "TEMAS",
    "TOKENS_CLARO",
    "TOKENS_DE_INTERFACE",
    "TOKENS_ESCURO",
    "VALIDO_SOBRE",
]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/design/test_tokens.py -q`
Expected: PASS (5 testes)

- [ ] **Step 5: Escrever o teste de contraste com dívida explícita (falha)**

`tests/design/_contraste.py`:

```python
"""Matematica de contraste WCAG. Utilitario de teste, fora do produto."""
from __future__ import annotations


def luminancia(hex_cor: str) -> float:
    h = hex_cor.lstrip("#")
    canais = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    canais = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]


def razao(a: str, b: str) -> float:
    la, lb = luminancia(a), luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
```

`tests/design/test_contraste.py`:

```python
"""Teste 3 do design system: contraste calculado a partir dos tokens.

DIVIDA_CONHECIDA e uma lista auto-limpante: o teste exige igualdade exata com
as falhas reais. Uma falha nova reprova, e uma divida quitada tambem reprova,
forcando a remocao da linha. Assim ela nao apodrece.
"""
import pytest

from dbqm.design.tokens import (
    PISO_INTERFACE,
    PISO_TEXTO,
    TEMAS,
    TOKENS_DE_INTERFACE,
    VALIDO_SOBRE,
)
from tests.design._contraste import razao

# Todas no tema claro, todas herdadas do tema GitHub. Quitadas na Task 8.
DIVIDA_CONHECIDA = {
    ("plano-claro", "texto-desabilitado", "fundo"),
    ("plano-claro", "texto-desabilitado", "superficie"),
    ("plano-claro", "texto-desabilitado", "painel"),
    ("plano-claro", "texto-desabilitado", "superficie-elevada"),
    ("plano-claro", "borda-forte", "fundo"),
    ("plano-claro", "borda-forte", "superficie"),
    ("plano-claro", "borda-forte", "painel"),
    ("plano-claro", "borda-forte", "superficie-elevada"),
    ("plano-claro", "identidade", "fundo"),
    ("plano-claro", "identidade", "superficie"),
    ("plano-claro", "identidade", "painel"),
    ("plano-claro", "identidade", "superficie-elevada"),
    ("plano-claro", "veredito-igual", "superficie"),
    ("plano-claro", "veredito-igual", "superficie-elevada"),
    ("plano-claro", "veredito-difere", "superficie"),
    ("plano-claro", "veredito-difere", "superficie-elevada"),
}


def _falhas() -> set[tuple[str, str, str]]:
    fora = set()
    for tema, tokens in TEMAS.items():
        for token, fundos in VALIDO_SOBRE.items():
            piso = PISO_INTERFACE if token in TOKENS_DE_INTERFACE else PISO_TEXTO
            for fundo in fundos:
                if razao(tokens[token], tokens[fundo]) < piso:
                    fora.add((tema, token, fundo))
    return fora


def test_contraste_bate_exatamente_com_a_divida_declarada():
    falhas = _falhas()
    novas = falhas - DIVIDA_CONHECIDA
    quitadas = DIVIDA_CONHECIDA - falhas
    assert not novas, f"contraste novo abaixo do piso: {sorted(novas)}"
    assert not quitadas, (
        f"divida quitada — remova de DIVIDA_CONHECIDA: {sorted(quitadas)}"
    )


@pytest.mark.parametrize("tema", sorted(TEMAS))
def test_texto_principal_passa_sobre_toda_superficie(tema):
    """O par mais usado do produto nao pode estar na lista de divida."""
    tokens = TEMAS[tema]
    for fundo in VALIDO_SOBRE["texto"]:
        assert razao(tokens["texto"], tokens[fundo]) >= PISO_TEXTO
```

- [ ] **Step 6: Rodar e confirmar que passa com a dívida declarada**

Run: `python -m pytest tests/design/test_contraste.py -q`
Expected: PASS. Se falhar com "contraste novo", os valores digitados divergem dos medidos — conferir contra a Task 1 Step 3.

- [ ] **Step 7: Verificar que o teste consegue falhar**

Alterar temporariamente `TOKENS_ESCURO["texto"]` para `"#171b22"` e rodar de novo.
Expected: FAIL apontando `('plano-escuro', 'texto', ...)`. **Reverter a alteração.**
Um teste que passa nos dois casos é pior que teste nenhum.

- [ ] **Step 8: Rodar a suíte inteira e commitar**

```bash
python -m pytest tests/ -q
git add dbqm/design tests/design
git commit -m "feat(ui): camada de design tokens com os valores atuais

Cria dbqm/design/ como camada abaixo de core/ e ui/, sem dependencias, para
que o relatorio HTML pare de precisar de paleta propria. Os valores sao os do
tema GitHub de hoje: nome antes de valor, para que uma regressao futura seja
atribuivel. Testes de paridade e de contraste calculado entram junto, com a
divida de contraste herdada declarada explicitamente."
```

---

### Task 2: `ui/theme.py` construído a partir dos tokens

**Files:**
- Modify: `dbqm/ui/theme.py` (arquivo inteiro)
- Modify: `tests/ui/test_theme.py:33-40` (remover `test_dark_palette_matches_prototype`)

**Interfaces:**
- Consumes: `dbqm.design.tokens.TEMAS`, `TOKENS_ESCURO`, `TOKENS_CLARO`.
- Produces: `dbqm.ui.theme.get_theme(name: str) -> Theme`, `TEMAS_TEXTUAL: dict[str, Theme]`, `NOMES_LEGADOS: dict[str, str]`.

- [ ] **Step 1: Escrever o teste (falha)**

Acrescentar a `tests/ui/test_theme.py`:

```python
def test_tema_expoe_todo_token_como_variavel_css():
    """Os componentes so podem consumir a camada semantica se ela chegar la."""
    from dbqm.design.tokens import TOKENS_ESCURO
    from dbqm.ui.theme import get_theme

    variaveis = get_theme("plano-escuro").variables
    for chave in TOKENS_ESCURO:
        assert chave in variaveis, f"token {chave} nao chega ao CSS"


def test_nomes_de_tema_antigos_continuam_funcionando():
    """settings.json de quem ja usa o dbqm guarda github-dark/github-light."""
    from dbqm.ui.theme import get_theme

    assert get_theme("github-dark").name == "plano-escuro"
    assert get_theme("github-light").name == "plano-claro"


def test_tema_desconhecido_cai_no_escuro():
    from dbqm.ui.theme import get_theme

    assert get_theme("inexistente").name == "plano-escuro"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/ui/test_theme.py -q`
Expected: FAIL — `get_theme("plano-escuro")` devolve o tema escuro antigo, cujo `.variables` não tem `fundo`.

- [ ] **Step 3: Reescrever `dbqm/ui/theme.py`**

```python
"""Temas do Textual, construidos a partir de dbqm/design/tokens.py.

Nenhuma cor e escrita aqui: este modulo so traduz os tokens semanticos para o
formato que o Textual espera. Trocar a paleta e trocar tokens.py.
"""
from __future__ import annotations

from textual.theme import Theme

from dbqm.design.tokens import TEMAS

# Nomes gravados em settings.json antes do design system.
NOMES_LEGADOS: dict[str, str] = {
    "github-dark": "plano-escuro",
    "github-light": "plano-claro",
}

PADRAO = "plano-escuro"


def _construir(nome: str, tokens: dict[str, str], escuro: bool) -> Theme:
    """Traduz os tokens semanticos para um Theme do Textual.

    Todo token vira variavel de CSS, inclusive os que tambem alimentam um
    campo nomeado do Theme: os componentes referenciam sempre `$token`, e os
    campos nomeados existem so para os widgets embutidos do Textual.
    """
    return Theme(
        name=nome,
        primary=tokens["identidade"],
        secondary=tokens["texto-apoio"],
        accent=tokens["identidade"],
        warning=tokens["veredito-difere"],
        error=tokens["op-falha"],
        success=tokens["veredito-igual"],
        foreground=tokens["texto"],
        background=tokens["fundo"],
        surface=tokens["superficie"],
        panel=tokens["painel"],
        dark=escuro,
        variables=dict(tokens),
    )


TEMAS_TEXTUAL: dict[str, Theme] = {
    "plano-escuro": _construir("plano-escuro", TEMAS["plano-escuro"], escuro=True),
    "plano-claro": _construir("plano-claro", TEMAS["plano-claro"], escuro=False),
}


def get_theme(name: str) -> Theme:
    """Devolve um tema pelo nome, aceitando os nomes antigos e caindo no padrao."""
    nome = NOMES_LEGADOS.get(name, name)
    return TEMAS_TEXTUAL.get(nome, TEMAS_TEXTUAL[PADRAO])
```

- [ ] **Step 4: Remover o teste que trava valores**

Apagar `test_dark_palette_matches_prototype` de `tests/ui/test_theme.py`. Ele afirma `panel-active == "#21262d"` — um token com zero usos — e impede que alguém olhe de novo. O teste de contraste garante a propriedade que importa.

Atualizar também `test_github_dark_has_required_vars` e `test_github_light_has_required_vars` para usarem `get_theme("plano-escuro")` / `get_theme("plano-claro")`, e renomeá-los para `test_tema_escuro_tem_variaveis_obrigatorias` / `test_tema_claro_tem_variaveis_obrigatorias`.

- [ ] **Step 5: Ajustar os pontos que registram os temas**

Run: `grep -rn "GITHUB_DARK\|GITHUB_LIGHT\|github-dark\|github-light" --include="*.py" dbqm/ tests/`

Substituir por `TEMAS_TEXTUAL` / `get_theme`. Pontos conhecidos: `dbqm/ui/app.py` (registro dos temas), `dbqm/models/settings.py:13` (`theme: str = "github-dark"` → `"plano-escuro"`), `dbqm/ui/screens/settings.py` (opções do `NavSelect`: rótulos `"Plano Escuro"` / `"Plano Claro"`).

`load_settings` continua aceitando o valor antigo porque `get_theme` mapeia — não é preciso migrar `settings.json`.

- [ ] **Step 6: Rodar tudo e ver passar**

Run: `python -m pytest tests/ -q`
Expected: PASS. Nenhuma mudança visual: os tokens ainda têm os valores GitHub.

- [ ] **Step 7: Commitar**

```bash
python -m build
git add dbqm/ui/theme.py dbqm/ui/app.py dbqm/ui/screens/settings.py dbqm/models/settings.py tests/ui/test_theme.py
git commit -m "refactor(ui): construir os temas do Textual a partir dos design tokens

Nenhuma cor e escrita em theme.py: ele so traduz tokens. Nomes de tema antigos
seguem aceitos, entao settings.json existente continua valendo. Remove
test_dark_palette_matches_prototype, que travava o valor de um token com zero
usos e impedia reavaliacao."
```

---

### Task 3: Teste de cor literal com teto

**Files:**
- Create: `tests/design/_varredura.py`, `tests/design/test_sem_cor_literal.py`

**Interfaces:**
- Consumes: nada do produto.
- Produces: `tests.design._varredura.violacoes() -> list[Violacao]` onde `Violacao = tuple[str, int, str]` (caminho relativo, linha, trecho).

- [ ] **Step 1: Escrever o utilitário de varredura**

`tests/design/_varredura.py`:

```python
"""Varre o codigo por cor escrita a mao. Utilitario de teste.

Duas formas contam como cor literal:
  - hexadecimal (`#58a6ff`)
  - nome de cor no markup do Rich/Textual (`[green]`, `[bold red]`)

`[dim]`, `[b]`, `[i]` e afins NAO contam: sao atributos de estilo, nao cores.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ_PACOTE = Path(__file__).resolve().parents[2] / "dbqm"

_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_NOMES = (
    "red", "green", "yellow", "blue", "cyan", "magenta", "white", "black",
    "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_cyan", "bright_magenta", "bright_white", "bright_black",
)
_MARKUP = re.compile(
    r"\[/?(?:(?:b|bold|i|italic|u|underline|dim)\s+)*(?:" + "|".join(_NOMES) + r")\]"
)

# Unico arquivo onde escrever cor e o trabalho.
ISENTOS = {"dbqm/design/tokens.py"}

Violacao = tuple[str, int, str]


def violacoes() -> list[Violacao]:
    """Toda cor literal fora dos arquivos isentos, com arquivo e linha."""
    achados: list[Violacao] = []
    for arquivo in sorted(RAIZ_PACOTE.rglob("*.py")):
        rel = arquivo.relative_to(RAIZ_PACOTE.parent).as_posix()
        if rel in ISENTOS:
            continue
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for padrao in (_HEX, _MARKUP):
                for m in padrao.finditer(linha):
                    achados.append((rel, numero, m.group(0)))
    return achados
```

- [ ] **Step 2: Escrever o teste com teto (falha se subir)**

`tests/design/test_sem_cor_literal.py`:

```python
"""Teste 1 do design system: cor literal fora de token.

O guia chama este de o teste de maior retorno. Ele roda com um teto que so
desce: cada tarefa da migracao baixa TETO, e a Task 13 o zera. Assim ele ja
protege contra crescimento antes de a divida acabar.
"""
from tests.design._varredura import violacoes

# Baixar a cada tarefa da migracao. Task 13 fecha em 0.
TETO = 210


def test_cor_literal_nao_cresce():
    achados = violacoes()
    assert len(achados) <= TETO, (
        f"{len(achados)} cores literais, teto {TETO}. Novas:\n"
        + "\n".join(f"  {a}:{l}  {t}" for a, l, t in achados[:20])
    )


def test_teto_esta_ajustado_ao_real():
    """Impede que o teto fique folgado e pare de proteger."""
    achados = violacoes()
    assert len(achados) == TETO, (
        f"divida caiu para {len(achados)} — baixe TETO para esse valor"
    )
```

- [ ] **Step 3: Rodar e ajustar o teto ao número real**

Run: `python -m pytest tests/design/test_sem_cor_literal.py -q`
Se `test_teto_esta_ajustado_ao_real` falhar, ajustar `TETO` para o número que ele reporta. Esse é o número de partida da migração — anotá-lo na mensagem de commit.

- [ ] **Step 4: Verificar que o teste consegue falhar**

Acrescentar temporariamente `COR = "#123456"` em `dbqm/ui/utils.py`, rodar, confirmar FAIL, e **remover**.

- [ ] **Step 5: Commitar**

```bash
python -m pytest tests/ -q
git add tests/design
git commit -m "test(ui): varredura de cor literal com teto que so desce

Teto inicial e a divida medida. Cada tarefa da migracao baixa o numero, e a
ultima o zera; ate la o teste ja impede que a divida cresca."
```

---

### Task 4: Widgets e modais — literais para token

**Files:**
- Modify: `dbqm/ui/widgets/query_list.py:53,68`, `dbqm/ui/widgets/status_bar.py:48,50`, `dbqm/ui/widgets/group_result.py:121-126,252`, `dbqm/ui/widgets/breadcrumb.py`, `dbqm/ui/widgets/progress.py`, `dbqm/ui/widgets/result_table.py`, `dbqm/ui/widgets/sql_viewer.py`, `dbqm/ui/widgets/action_bar.py`, `dbqm/ui/widgets/templates_sidebar.py`, `dbqm/ui/modals/*.py`
- Modify: `tests/design/test_sem_cor_literal.py` (baixar `TETO`)

**Interfaces:**
- Consumes: os tokens expostos como `$nome` no CSS pela Task 2.
- Produces: nada de novo.

- [ ] **Step 1: Escrever o teste de comportamento (falha)**

Acrescentar a `tests/ui/test_widgets.py`:

```python
@pytest.mark.asyncio
async def test_status_bar_usa_token_de_identidade_para_conexao_ativa():
    """A bolinha de conexao e identidade, nao 'verde de sucesso'."""
    from dbqm.ui.widgets.status_bar import StatusBar

    class App_(App):
        def compose(self) -> ComposeResult:
            yield StatusBar()

    app = App_()
    async with app.run_test():
        barra = app.query_one(StatusBar)
        barra.set_connection("MGORA7ORA9")
        await app.workers.wait_for_complete()
        conteudo = barra.render().markup if hasattr(barra.render(), "markup") else str(barra.render())
        assert "green" not in conteudo
        assert "$identidade" in conteudo
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/ui/test_widgets.py -k status_bar_usa_token -q`
Expected: FAIL — o conteúdo ainda tem `[green]`.

- [ ] **Step 3: Substituir os literais**

Mapa de tradução, aplicado em todos os arquivos desta tarefa:

| Antes | Depois | Porque |
|---|---|---|
| `[green]` em veredito | `[$veredito-igual]` | eixo de dados |
| `[yellow]` em veredito | `[$veredito-difere]` | eixo de dados |
| `[red]` em veredito | `[$veredito-ausente]` | eixo de dados |
| `[green]` em conexao/status | `[$identidade]` | eixo de operacao: conectado e identidade |
| `[red]` em erro de operacao | `[$op-falha]` | eixo de operacao |
| `[yellow]` em estado pendente | `[$texto-apoio]` | pendente nao e aviso; `op-pendente` foi cortado |
| `[#e3b341]` | `[$identidade]` | era o literal que originou o token |
| `[yellow]★[/]` (favorito) | `[$identidade]★[/]` | favorito e marcador de identidade |
| `border: thick $accent` | manter por ora | trocado na Task 9, junto com o `Dialog` |

Exemplo, `dbqm/ui/widgets/group_result.py:120-127`:

```python
    def _status_markup(self, status: str) -> str:
        """Rotula o status da comparacao com o token do eixo de veredito.

        OK sai sem tinta de proposito: num run em que quase tudo bate, pintar
        os iguais cobre a tela com uma cor que significa "nao olhe para mim".
        """
        marcas = {
            "OK": "[$veredito-igual]OK[/]",
            "OK*": "[$veredito-igual]OK*[/]",
            "DIFF": "[$veredito-difere]DIFF[/]",
            "ABSENT": "[$veredito-ausente]ABSENT[/]",
        }
        return marcas.get(status, status)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/ui/ -q`
Expected: PASS

- [ ] **Step 5: Baixar o teto e confirmar**

Run: `python -m pytest tests/design/test_sem_cor_literal.py -q`
Ajustar `TETO` para o número reportado por `test_teto_esta_ajustado_ao_real`.

- [ ] **Step 6: Commitar**

```bash
python -m pytest tests/ -q
git add dbqm/ui/widgets dbqm/ui/modals tests/
git commit -m "refactor(ui): widgets e modais consomem tokens em vez de cor literal

Separa os dois eixos que estavam fundidos: conexao ativa passa a usar
\$identidade em vez de verde de sucesso, e o veredito de comparacao usa os
tokens do proprio eixo. Os valores dos tokens ainda sao os antigos, mas markup que usava nome ANSI
muda de tom: [green] e (0,128,0) e \$veredito-igual e #3fb950. A troca de
valores da paleta continua sendo tarefa separada."
```

---

### Task 5: Telas — literais para token

**Files:**
- Modify: `dbqm/ui/screens/history.py`, `settings.py`, `package_editor.py`, `group_run.py`, `group_manage.py`, `oracle_clients.py`, `query_manage.py`, `exec_routine.py`, `template_manage.py`, `query_exec.py`, `browser.py`, `adhoc.py`, `config_port.py`, `connections.py`, `ferramentas.py`, `group_exec.py`
- Modify: `tests/design/test_sem_cor_literal.py` (baixar `TETO`)

**Interfaces:**
- Consumes: os mesmos tokens `$nome`.
- Produces: nada de novo.

- [ ] **Step 1: Escrever o teste (falha)**

Acrescentar a `tests/ui/test_screens.py`:

```python
@pytest.mark.asyncio
async def test_settings_nao_usa_cor_literal_no_status_do_client(tmp_config_dir):
    """O estado 'nenhum encontrado' e informativo, nao um aviso amarelo."""
    from textual.widgets import Static

    app = SettingsTestApp()
    async with app.run_test():
        rotulo = app.query_one(SettingsScreen).query_one(
            "#settings-oracle-client-current", Static
        )
        bruto = rotulo.renderable if isinstance(rotulo.renderable, str) else str(rotulo.renderable)
        assert "[yellow]" not in bruto
        assert "[green]" not in bruto
        assert "[red]" not in bruto
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/ui/test_screens.py -k nao_usa_cor_literal -q`
Expected: FAIL — `settings.py:200` ainda tem `[yellow]nenhum encontrado[/]`.

- [ ] **Step 3: Aplicar o mesmo mapa da Task 4**

Casos que precisam de julgamento, decididos aqui para não sobrar dúvida:

- `settings.py:200` `[yellow]nenhum encontrado[/]` → `[$texto-apoio]nenhum encontrado[/]`
- `settings.py:212` `[green]Presente[/green]` → `Presente` (sem tinta: sucesso é a ausência de alarme) e `[yellow]Sera gerada…[/]` → `[$texto-apoio]Sera gerada…[/]`
- `settings.py` — o `[red]` do erro de client configurado → `[$op-falha]`
- `oracle_clients.py:160` `_set_status` — o mapa `{"info": "$text-muted", "ok": "green", "err": "red"}` vira `{"info": "$texto-apoio", "ok": "$texto-apoio", "err": "$op-falha"}`
- `history.py` — status de execução: sucesso sem tinta, falha em `$op-falha`
- `group_run.py` `#e3b341` → `$identidade`

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/ui/ -q`
Expected: PASS

- [ ] **Step 5: Baixar o teto**

Run: `python -m pytest tests/design/test_sem_cor_literal.py -q` e ajustar `TETO`.

- [ ] **Step 6: Commitar**

```bash
python -m pytest tests/ -q
git add dbqm/ui/screens tests/
git commit -m "refactor(ui): telas consomem tokens em vez de cor literal

Sucesso de operacao perde a tinta verde: 'Presente' e 'OK' saem como texto.
Estados pendentes deixam de ser amarelo de aviso e viram texto de apoio."
```

---

### Task 6: CLI — tema do Rich a partir dos tokens

**Files:**
- Modify: `dbqm/cli.py` (104 markups + criação do `Console`)
- Create: nada
- Modify: `tests/design/test_sem_cor_literal.py` (baixar `TETO`)

**Interfaces:**
- Consumes: `dbqm.design.tokens.TOKENS_ESCURO`.
- Produces: `dbqm.cli.tema_rich() -> rich.theme.Theme` e o `Console` global já construído com ele.

- [ ] **Step 1: Escrever o teste (falha)**

Criar `tests/test_cli_tema.py`:

```python
"""O CLI e o terceiro consumidor dos tokens, ao lado da TUI e do relatorio."""
import io

from rich.console import Console

from dbqm.cli import tema_rich
from dbqm.design.tokens import TOKENS_ESCURO


def test_tema_rich_expoe_um_estilo_por_token():
    estilos = tema_rich().styles
    for chave in TOKENS_ESCURO:
        assert chave.replace("-", ".") in estilos, f"token {chave} nao chega ao CLI"


def test_estilo_de_veredito_renderiza_a_cor_do_token():
    console = Console(
        theme=tema_rich(), file=io.StringIO(),
        force_terminal=True, color_system="truecolor", width=40,
    )
    console.print("[veredito.difere]DIFERE[/]")
    esperado = TOKENS_ESCURO["veredito-difere"].lstrip("#")
    rgb = ";".join(str(int(esperado[i:i + 2], 16)) for i in (0, 2, 4))
    assert rgb in console.file.getvalue()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_cli_tema.py -q`
Expected: FAIL com `ImportError: cannot import name 'tema_rich'`

- [ ] **Step 3: Implementar no `cli.py`**

Perto do topo, onde hoje o `Console` é criado:

```python
from rich.theme import Theme as _TemaRich

from dbqm.design.tokens import TOKENS_ESCURO


def tema_rich() -> _TemaRich:
    """Tema do Rich construido a partir dos design tokens.

    O CLI roda em terminal de fundo desconhecido, entao usa sempre a variante
    escura: ela e a unica cuja legibilidade nao depende de o terminal ser claro.
    Os nomes trocam '-' por '.' para seguir a convencao de estilo do Rich.
    """
    return _TemaRich(
        {chave.replace("-", "."): valor for chave, valor in TOKENS_ESCURO.items()}
    )


console = Console(theme=tema_rich())
```

Substituir os 104 markups pelo mapa da Task 4, com os nomes na forma do Rich
(`[veredito.difere]`, `[identidade]`, `[op.falha]`, `[texto.apoio]`).

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_cli_tema.py tests/test_cli.py -q`
Expected: PASS

- [ ] **Step 5: Conferir a saída real**

Run: `python -m dbqm list connections`
Expected: as cores continuam parecidas com antes (os tokens ainda têm os valores GitHub) e nada aparece sem cor por engano.

- [ ] **Step 6: Baixar o teto e commitar**

```bash
python -m pytest tests/ -q
git add dbqm/cli.py tests/
git commit -m "refactor(cli): tema do Rich construido a partir dos design tokens

O CLI passa a ser o terceiro consumidor da mesma fonte de cor, ao lado da TUI.
Usa sempre a variante escura: o fundo do terminal e desconhecido."
```

---

### Task 7: Relatório HTML a partir dos tokens

**Files:**
- Modify: `dbqm/core/html_report.py` (os 14 hex e o bloco `<style>`)
- Modify: `tests/design/test_sem_cor_literal.py` (baixar `TETO`)

**Interfaces:**
- Consumes: `dbqm.design.tokens.TOKENS_ESCURO`.
- Produces: `dbqm.core.html_report.css_variaveis(tokens: dict[str, str]) -> str`.

- [ ] **Step 1: Escrever o teste (falha)**

Acrescentar a `tests/core/test_html_report.py` (criar se não existir):

```python
def test_relatorio_usa_as_cores_do_design_system():
    """O relatorio tinha paleta propria so porque core/ nao podia importar ui/."""
    from dbqm.core.html_report import css_variaveis
    from dbqm.design.tokens import TOKENS_ESCURO

    css = css_variaveis(TOKENS_ESCURO)
    for chave, valor in TOKENS_ESCURO.items():
        assert f"--{chave}: {valor}" in css


def test_relatorio_nao_carrega_mais_a_paleta_antiga():
    from pathlib import Path

    fonte = Path("dbqm/core/html_report.py").read_text(encoding="utf-8")
    for orfa in ("#00d4ff", "#16213e", "#4caf50", "#ff9800", "#f44336"):
        assert orfa not in fonte, f"{orfa} sobrou da paleta paralela"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/core/test_html_report.py -q`
Expected: FAIL com `ImportError: cannot import name 'css_variaveis'`

- [ ] **Step 3: Implementar**

```python
from dbqm.design.tokens import TOKENS_ESCURO


def css_variaveis(tokens: dict[str, str]) -> str:
    """Emite os design tokens como custom properties, para o <style> do relatorio."""
    linhas = "\n".join(f"  --{chave}: {valor};" for chave, valor in sorted(tokens.items()))
    return f":root {{\n{linhas}\n}}"
```

No `<style>` do relatório, trocar cada hex pela variável correspondente:
`#16213e` → `var(--painel)`, `#00d4ff` → `var(--identidade)`, `#4caf50` → `var(--veredito-igual)`, `#ff9800` → `var(--veredito-difere)`, `#f44336` → `var(--veredito-ausente)`, `#e0e0e0` → `var(--texto)`. Injetar `css_variaveis(TOKENS_ESCURO)` no início do bloco.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/core/ -q`
Expected: PASS

- [ ] **Step 5: Conferir um relatório de verdade**

Gerar um relatório e abrir no navegador. As cores mudam aqui — é o único ponto da migração em que isso acontece antes da Task 8, porque a paleta paralela do relatório **já era** divergente. Confirmar que continua legível.

- [ ] **Step 6: Baixar o teto e commitar**

```bash
python -m pytest tests/ -q
git add dbqm/core/html_report.py tests/
git commit -m "refactor(core): relatorio HTML consome os design tokens

Elimina a paleta paralela de 14 hex que existia so porque core/ nao podia
importar ui/. Agora TUI, CLI e relatorio leem a mesma fonte."
```

---

### Task 8: A repintura — paleta Plano

**O único passo que muda a aparência do produto.** Um arquivo, reversível.

**Files:**
- Modify: `dbqm/design/tokens.py` (só os valores dos dois dicionários)
- Modify: `tests/design/test_contraste.py` (esvaziar `DIVIDA_CONHECIDA`)
- Modify: `dbqm/_version.py`, `README.md`

**Interfaces:**
- Consumes: nada novo.
- Produces: nada novo. **Nenhuma chave muda** — só valores.

- [ ] **Step 1: Esvaziar a dívida no teste (falha)**

Em `tests/design/test_contraste.py`, trocar o conteúdo de `DIVIDA_CONHECIDA` por `set()`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/design/test_contraste.py -q`
Expected: FAIL com 16 entradas em "divida quitada — remova de DIVIDA_CONHECIDA"… ao contrário: as 16 ainda são falhas reais, então falha com "contraste novo abaixo do piso". Qualquer das duas mensagens confirma que o teste está vendo o estado antigo.

- [ ] **Step 3: Trocar os valores para a paleta Plano**

Em `dbqm/design/tokens.py`, substituir os dois dicionários. As chaves são idênticas; só os valores mudam. Acrescentar as primitivas como comentário de origem.

```python
# --------------------------------------------------------------- camada 1
# Primitivas ordenadas por luminancia: numero maior e sempre mais escuro.
# ardosia (escuro): 950 #0b0e14 · 900 #0f131b · 850 #151a24 · 800 #1e2531
#                   700 #2b3342 · 500 #606e86 · 450 #6b7688 · 300 #9aa4b5
#                   100 #d5dae4 · 050 #f2f5fa
# neve (claro):     000 #ffffff · 050 #f4f6f9 · 100 #f2f5f8 · 150 #eaeef3
#                   300 #d3dae3 · 500 #8a94a3 · 600 #7b8798 · 700 #5b6577
#                   900 #1c2230 · 950 #0a0e16
# tintas:  ambar 400 #e3b341 / 800 #7d5600   (identidade, linhagem SQL*Plus)
#          persimmon 400 #ff8a5c / 800 #a83a0c   (discorda)
#          indigo 400 #8b9bff / 800 #3f49c4   (ausente)
#          carmim 400 #ff6b72 / 800 #c02434   (falha)

TOKENS_ESCURO: Final[dict[str, str]] = {
    "fundo": "#0b0e14",
    "superficie": "#0f131b",
    "painel": "#151a24",
    "superficie-elevada": "#1e2531",
    "borda": "#2b3342",
    "borda-forte": "#606e86",
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
    "texto-desabilitado": "#8a94a3",
    "identidade": "#7d5600",
    "veredito-igual": "#5b6577",
    "veredito-difere": "#a83a0c",
    "veredito-ausente": "#3f49c4",
    "op-falha": "#c02434",
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/design/ -q`
Expected: PASS — zero falhas de contraste nos dois temas, `DIVIDA_CONHECIDA` vazia.

- [ ] **Step 5: Olhar o resultado**

Run: `python -m dbqm` — abrir uma comparação de grupo e conferir os dois temas.
Expected: chrome cinza sem cor; `OK` sem tinta; `DIFERE` em persimmon; `AUSENTE` em índigo; conexão em âmbar.

- [ ] **Step 6: Rodar tudo, versionar e publicar**

```bash
python -m pytest tests/ -q
# bump minor em dbqm/_version.py (1.18.0 -> 1.19.0)
# README.md: acrescentar o design system a lista de features
python -m build
git add dbqm/design/tokens.py tests/design dbqm/_version.py README.md
git commit -m "feat(ui): paleta Plano — repintura sobre os design tokens

Troca so os valores dos tokens, num arquivo. Chrome sem cor; a tinta fica
reservada ao dado que discorda. O produto perde o verde: OK sai como texto de
apoio, porque num run em que quase tudo bate, pintar os iguais e ruido.

Contraste calculado sem nenhuma falha nos dois temas, o que quita as 16
pendencias herdadas do tema GitHub."
git push
PYPI_TOKEN=$(cat .env | tr -d '\r\n')
python -m twine upload dist/dbqm-1.19.0* -u __token__ -p "$PYPI_TOKEN"
```

---

### Task 9: Componente `Dialog`

**Files:**
- Create: `dbqm/ui/widgets/dialog.py`
- Modify: `dbqm/ui/modals/*.py` (8 arquivos), `dbqm/ui/screens/query_manage.py`, `group_manage.py`, `package_editor.py`, `group_run.py`, `template_manage.py`
- Modify: `dbqm/ui/widgets/__init__.py`
- Test: `tests/ui/test_widgets.py`

**Interfaces:**
- Consumes: tokens `$painel`, `$borda-forte`, `$texto`, `$op-falha`.
- Produces: `Dialog(titulo: str, *, largura: str = "md", tom: str = "neutro", id: str | None = None)`, um `Vertical` com `LARGURAS = {"sm": 50, "md": 70, "lg": 90}` e `TONS = ("neutro", "destrutivo")`.

- [ ] **Step 1: Escrever o teste (falha)**

```python
def test_dialog_rejeita_variante_desconhecida():
    """Variantes fechadas: sem porta dos fundos para estilo arbitrario."""
    from dbqm.ui.widgets.dialog import Dialog

    with pytest.raises(ValueError, match="tom"):
        Dialog("Titulo", tom="roxo")
    with pytest.raises(ValueError, match="largura"):
        Dialog("Titulo", largura="xxl")


@pytest.mark.asyncio
async def test_dialog_renderiza_o_titulo():
    from textual.widgets import Static
    from dbqm.ui.widgets.dialog import Dialog

    class App_(App):
        def compose(self) -> ComposeResult:
            with Dialog("Confirmar exclusao", id="d"):
                yield Static("corpo")

    app = App_()
    async with app.run_test():
        titulo = app.query_one("#d-titulo", Static)
        assert "Confirmar exclusao" in titulo.render().plain
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/ui/test_widgets.py -k dialog -q`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
"""Dialog: a camada que flutua sobre o conteudo.

Existe porque o mesmo bloco `border: thick $accent` estava copiado 29 vezes em
13 arquivos. Regra de uso: se flutua sobre o conteudo, e Dialog; se nao flutua,
e Panel.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

LARGURAS: dict[str, int] = {"sm": 50, "md": 70, "lg": 90}
TONS: tuple[str, ...] = ("neutro", "destrutivo")


class Dialog(Vertical):
    """Chrome de uma camada flutuante: moldura, titulo e area de conteudo."""

    DEFAULT_CSS = """
    Dialog {
        width: auto;
        height: auto;
        max-height: 90%;
        background: $painel;
        border: thick $borda-forte;
        padding: 1 2;
    }
    Dialog.-destrutivo { border: thick $op-falha; }
    Dialog .dialog-titulo {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        titulo: str,
        *,
        largura: str = "md",
        tom: str = "neutro",
        id: str | None = None,
    ) -> None:
        if largura not in LARGURAS:
            raise ValueError(f"largura desconhecida: {largura!r}; use {sorted(LARGURAS)}")
        if tom not in TONS:
            raise ValueError(f"tom desconhecido: {tom!r}; use {list(TONS)}")
        super().__init__(id=id, classes=f"-{tom}")
        self._titulo = titulo
        self.styles.width = LARGURAS[largura]

    def compose(self) -> ComposeResult:
        # Verificado nesta versao do Textual: o compose do proprio widget e os
        # filhos passados por `with Dialog(...)` coexistem, nesta ordem.
        yield Static(self._titulo, classes="dialog-titulo", id=f"{self.id}-titulo")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/ui/test_widgets.py -k dialog -q`
Expected: PASS

- [ ] **Step 5: Migrar os 13 arquivos**

Em cada modal, trocar o `Vertical(id="dialog")` mais o bloco CSS de moldura por
`Dialog(titulo, largura=...)`. Apagar do `DEFAULT_CSS` local as regras de
`#dialog` e `#title` que o `Dialog` agora entrega. Manter os ids dos controles
internos (`#save`, `#cancel`, …) — há testes que os consultam.

- [ ] **Step 6: Rodar tudo e commitar**

```bash
python -m pytest tests/ -q
git add dbqm/ui tests/ui
git commit -m "refactor(ui): componente Dialog no lugar de 29 molduras copiadas

Chrome de camada flutuante em um lugar so, com variantes fechadas de largura e
tom. A borda passa a ser \$borda-forte: o accent saturado nao carregava
informacao nenhuma."
```

---

### Task 10: Componente `EmptyState`

**Files:**
- Create: `dbqm/ui/widgets/empty_state.py`
- Modify: os pontos que hoje escrevem "Nenhum…" (`query_manage.py`, `group_manage.py`, `template_manage.py`, `history.py`, `connections.py`, `oracle_clients.py`, `browser.py`, `exec_routine.py`, `templates_sidebar.py`)
- Test: `tests/ui/test_widgets.py`

**Interfaces:**
- Consumes: tokens `$texto`, `$texto-apoio`.
- Produces: `EmptyState(o_que: str, porque: str, acao_rotulo: str, acao_id: str)`.

- [ ] **Step 1: Escrever o teste (falha)**

```python
def test_empty_state_exige_uma_acao():
    """Um vazio que so informa que esta vazio e um defeito, nao um estado."""
    from dbqm.ui.widgets.empty_state import EmptyState

    with pytest.raises(TypeError):
        EmptyState("Consultas", "Voce ainda nao salvou nenhuma")  # sem acao


@pytest.mark.asyncio
async def test_empty_state_oferece_a_primeira_acao():
    from textual.widgets import Button
    from dbqm.ui.widgets.empty_state import EmptyState

    class App_(App):
        def compose(self) -> ComposeResult:
            yield EmptyState(
                o_que="Consultas",
                porque="Voce ainda nao salvou nenhuma consulta",
                acao_rotulo="Criar consulta",
                acao_id="criar-consulta",
            )

    app = App_()
    async with app.run_test():
        botao = app.query_one("#criar-consulta", Button)
        assert botao.label.plain == "Criar consulta"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/ui/test_widgets.py -k empty_state -q`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
"""EmptyState: a primeira tela de todo usuario novo, em todo modulo.

Os quatro parametros sao obrigatorios de proposito. E o que impede repetir
"Nenhuma consulta configurada" sem oferecer a saida — o antipadrao que estava
em 22 dos 23 estados vazios do dbqm.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Static


class EmptyState(Vertical):
    """Diz o que e aquilo, por que esta vazio, e oferece a primeira acao."""

    DEFAULT_CSS = """
    EmptyState {
        height: auto;
        width: 100%;
        padding: 2;
        content-align: center middle;
    }
    EmptyState .empty-o-que {
        text-style: bold;
        color: $texto;
        width: 100%;
        content-align: center middle;
    }
    EmptyState .empty-porque {
        color: $texto-apoio;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        o_que: str,
        porque: str,
        acao_rotulo: str,
        acao_id: str,
    ) -> None:
        super().__init__()
        self._o_que = o_que
        self._porque = porque
        self._acao_rotulo = acao_rotulo
        self._acao_id = acao_id

    def compose(self) -> ComposeResult:
        yield Static(self._o_que, classes="empty-o-que")
        yield Static(self._porque, classes="empty-porque")
        yield Button(self._acao_rotulo, variant="primary", id=self._acao_id)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/ui/test_widgets.py -k empty_state -q`
Expected: PASS

- [ ] **Step 5: Substituir os vazios mudos**

Um por um. Redação seguindo a regra do §10 do spec — o rótulo da ação no
imperativo e sem acento:

| Onde | o_que | porque | acao_rotulo |
|---|---|---|---|
| `query_manage` | `Consultas` | `Nenhuma consulta salva ainda` | `Criar consulta` |
| `group_manage` | `Grupos` | `Grupos comparam a mesma consulta em varias conexoes` | `Criar grupo` |
| `template_manage` | `Templates` | `Templates guardam consultas com parametros` | `Criar template` |
| `connections` | `Conexoes` | `O dbqm precisa de ao menos uma conexao para executar` | `Adicionar conexao` |
| `history` | `Historico` | `Execucoes aparecem aqui depois da primeira consulta` | `Executar consulta` |
| `oracle_clients` | `Clients instalados` | `Nenhum Oracle Instant Client em ~/.dbqm/clients` | `Instalar client` |
| `browser` | `Objetos` | `Selecione uma conexao para listar tabelas e views` | `Escolher conexao` |
| `exec_routine` | `Rotinas` | `Nenhuma rotina adicionada a execucao` | `Adicionar rotina` |
| `templates_sidebar` | `Templates` | `Crie templates na aba Ferramentas para reutiliza-los aqui` | `Abrir Ferramentas` |

Ligar cada `acao_id` ao handler que já existe na tela.

- [ ] **Step 6: Rodar tudo e commitar**

```bash
python -m pytest tests/ -q
git add dbqm/ui tests/ui
git commit -m "feat(ui): componente EmptyState com acao obrigatoria

22 dos 23 estados vazios so informavam que estavam vazios. Os quatro
parametros obrigatorios tornam isso impossivel de repetir."
```

---

### Task 11: Componentes `Veredito` e `StatusOperacao`

**Files:**
- Create: `dbqm/ui/widgets/veredito.py`
- Modify: `dbqm/ui/widgets/group_result.py`, `dbqm/ui/widgets/status_bar.py`, `dbqm/ui/screens/group_run.py`, `dbqm/ui/screens/history.py`
- Test: `tests/ui/test_widgets.py`

**Interfaces:**
- Consumes: tokens do eixo de veredito e de operação.
- Produces: `marcar_veredito(status: str) -> str` e `marcar_operacao(estado: str) -> str`, ambas devolvendo markup do Textual. `VEREDITOS = ("igual", "igual-normalizado", "difere", "ausente")`, `OPERACOES = ("ok", "falha", "executando")`.

- [ ] **Step 1: Escrever o teste (falha)**

```python
def test_veredito_comunica_estado_alem_da_cor():
    """Piso de acessibilidade: cor sozinha nao comunica estado."""
    from dbqm.ui.widgets.veredito import marcar_veredito

    glifos = {marcar_veredito(v).split("]")[1].split("[")[0] for v in
              ("igual", "igual-normalizado", "difere", "ausente")}
    assert len(glifos) == 4, f"glifos repetidos: {glifos}"


def test_veredito_igual_usa_o_token_do_proprio_eixo():
    from dbqm.ui.widgets.veredito import marcar_veredito

    assert "$veredito-igual" in marcar_veredito("igual")


def test_veredito_rejeita_status_desconhecido():
    from dbqm.ui.widgets.veredito import marcar_veredito

    with pytest.raises(ValueError, match="status"):
        marcar_veredito("talvez")


def test_operacao_bem_sucedida_nao_recebe_tinta():
    """Sucesso e a ausencia de alarme."""
    from dbqm.ui.widgets.veredito import marcar_operacao

    assert "$op-falha" not in marcar_operacao("ok")
    assert "$op-falha" in marcar_operacao("falha")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/ui/test_widgets.py -k "veredito or operacao" -q`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
"""Marcadores de veredito e de status de operacao.

Sao dois eixos diferentes e nao compartilham paleta: DIFERE nao e um aviso e
AUSENTE nao e um erro. Cada marcador leva glifo alem da cor, para que o estado
nao dependa de o leitor distinguir tons.
"""
from __future__ import annotations

VEREDITOS: dict[str, tuple[str, str]] = {
    # status -> (glifo, token)
    "igual": ("=", "$veredito-igual"),
    "igual-normalizado": ("~", "$veredito-igual"),
    "difere": ("!", "$veredito-difere"),
    "ausente": ("-", "$veredito-ausente"),
}

OPERACOES: dict[str, tuple[str, str]] = {
    "ok": ("", "$texto-apoio"),
    "falha": ("x", "$op-falha"),
    "executando": ("*", "$identidade"),
}


def marcar_veredito(status: str) -> str:
    """Markup do veredito de comparacao, com glifo e cor."""
    if status not in VEREDITOS:
        raise ValueError(f"status desconhecido: {status!r}; use {sorted(VEREDITOS)}")
    glifo, token = VEREDITOS[status]
    rotulo = {"igual": "OK", "igual-normalizado": "OK*",
              "difere": "DIFERE", "ausente": "AUSENTE"}[status]
    return f"[{token}]{glifo} {rotulo}[/]"


def marcar_operacao(estado: str) -> str:
    """Markup do status de uma operacao. `ok` sai sem tinta de alarme."""
    if estado not in OPERACOES:
        raise ValueError(f"estado desconhecido: {estado!r}; use {sorted(OPERACOES)}")
    glifo, token = OPERACOES[estado]
    rotulo = {"ok": "OK", "falha": "FALHA", "executando": "executando"}[estado]
    return f"[{token}]{(glifo + ' ') if glifo else ''}{rotulo}[/]"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/ui/test_widgets.py -k "veredito or operacao" -q`
Expected: PASS

- [ ] **Step 5: Substituir os pontos de uso**

**Correcao de premissa (descoberta durante a Task 5).** O plano dizia que
`group_result.py:_status_markup` passaria a delegar para `marcar_veredito`.
`_status_markup` e **codigo morto**: definido e chamado em lugar nenhum, nem em
teste. Ligar o componente novo a ele entregaria zero. Os caminhos reais sao:

- `_render_flat` e `_render_pivoted` alimentam as celulas de status com
  `str(row.status)` cru — **hoje a coluna de veredito da tabela de comparacao
  nao tem cor nenhuma**, apesar de ser a tela central do produto.
- `_render_summary` monta linhas que vao para `Static.update()`, e essas ja
  usam os tokens do eixo de veredito desde a Task 4.

Portanto o Step 5 e:

1. **Apagar `_status_markup`.** Codigo morto nao se migra, se remove.
2. **Fazer as celulas de status da DataTable usarem `marcar_veredito`**, passando
   o resultado por `Content.from_markup(...)`. Isto e obrigatorio: `add_row`
   parseia com Rich puro, que nao resolve `$token` e levanta
   `rich.errors.MarkupError`. O padrao ja esta aplicado em
   `dbqm/ui/screens/history.py` (Task 5) — copie de la.
   Este passo e o unico ganho visivel da tarefa: e quando o veredito finalmente
   ganha cor na tabela.
3. **Trocar as linhas de `_render_summary`** para chamarem `marcar_veredito` em
   vez de montarem o markup a mao.
4. `status_bar`, `group_run` e `history` passam a usar `marcar_operacao`.

Acrescente um teste que monte a tabela de comparacao com um `GroupResult`
contendo os quatro status e verifique a cor **resolvida** de cada celula — nao a
string de markup. Um teste que so cheque a string nao teria pego nada disso.

- [ ] **Step 6: Rodar tudo e commitar**

```bash
python -m pytest tests/ -q
git add dbqm/ui tests/ui
git commit -m "feat(ui): marcadores de veredito e de operacao como componentes

Separa de vez os dois eixos e acrescenta glifo a cada estado, para que o
estado nao dependa so da cor."
```

---

### Task 12: Os outros quatro estados

O §8 do spec exige cinco estados por componente. A Task 10 entregou o vazio;
esta entrega os outros quatro.

**Files:**
- Create: `dbqm/ui/widgets/esqueleto.py`
- Modify: `dbqm/ui/widgets/result_table.py`, `dbqm/ui/screens/query_exec.py`, `dbqm/ui/screens/group_exec.py`, `dbqm/ui/screens/browser.py`, `dbqm/ui/screens/package_editor.py`
- Test: `tests/ui/test_widgets.py`

**Interfaces:**
- Consumes: tokens `$superficie-elevada`, `$texto-desabilitado`, `$texto-apoio`.
- Produces: `Esqueleto(linhas: int = 5, colunas: int = 4)`; a classe CSS
  `-somente-leitura`, aplicável a qualquer container.

- [ ] **Step 1: Escrever o teste (falha)**

```python
@pytest.mark.asyncio
async def test_esqueleto_tem_a_forma_do_conteudo_que_vem():
    """Do formato do conteudo, nao um rodopio centralizado: evita o salto de layout."""
    from dbqm.ui.widgets.esqueleto import Esqueleto

    class App_(App):
        def compose(self) -> ComposeResult:
            yield Esqueleto(linhas=6, colunas=3, id="e")

    app = App_()
    async with app.run_test():
        esqueleto = app.query_one("#e", Esqueleto)
        assert len(esqueleto.query(".esqueleto-linha")) == 6


@pytest.mark.asyncio
async def test_somente_leitura_e_visualmente_distinto_de_desabilitado():
    """Somente leitura parece conteudo; desabilitado parece controle inerte."""
    from textual.widgets import Input

    class App_(App):
        CSS = "Input { width: 20; }"
        def compose(self) -> ComposeResult:
            yield Input(value="a", id="ro", classes="-somente-leitura")
            yield Input(value="b", id="off", disabled=True)

    app = App_()
    async with app.run_test():
        ro = app.query_one("#ro", Input)
        off = app.query_one("#off", Input)
        assert ro.styles.color != off.styles.color
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/ui/test_widgets.py -k "esqueleto or somente_leitura" -q`
Expected: FAIL com `ModuleNotFoundError: dbqm.ui.widgets.esqueleto`

- [ ] **Step 3: Implementar**

```python
"""Esqueleto de carregamento: a forma do conteudo que vem.

Um rodopio centralizado nao diz nada sobre o que esta chegando e deixa o
layout saltar quando o conteudo entra. O esqueleto reserva o espaco certo.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static


class Esqueleto(Vertical):
    """Placeholder com a forma de uma tabela de `linhas` x `colunas`."""

    DEFAULT_CSS = """
    Esqueleto { height: auto; width: 100%; }
    Esqueleto .esqueleto-linha { height: 1; width: 100%; }
    Esqueleto .esqueleto-celula {
        height: 1;
        width: 1fr;
        margin: 0 1 0 0;
        background: $superficie-elevada;
    }
    """

    def __init__(self, linhas: int = 5, colunas: int = 4, id: str | None = None) -> None:
        super().__init__(id=id)
        self._linhas = linhas
        self._colunas = colunas

    def compose(self) -> ComposeResult:
        for _ in range(self._linhas):
            with Horizontal(classes="esqueleto-linha"):
                for _ in range(self._colunas):
                    yield Static("", classes="esqueleto-celula")
```

Em `dbqm/ui/app.py`, acrescentar ao CSS global a distincao entre os dois estados
inertes:

```css
/* Desabilitado: controle inerte, o motivo fica na linha de apoio ao lado. */
*:disabled { color: $texto-desabilitado; }
/* Somente leitura: e conteudo, nao formulario quebrado. */
.-somente-leitura { color: $texto-apoio; border: none; background: $painel; }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/ui/test_widgets.py -k "esqueleto or somente_leitura" -q`
Expected: PASS

- [ ] **Step 5: Aplicar nos pontos de uso**

- `query_exec` e `group_exec`: trocar o indicador de progresso durante a
  execucao por `Esqueleto(linhas=8, colunas=4)` na area do resultado.
- `browser`: `Esqueleto(linhas=10, colunas=2)` enquanto lista objetos.
- `package_editor`: aplicar `-somente-leitura` ao viewer quando o pacote
  estiver aberto sem permissao de escrita.
- Onde houver botao desabilitado, garantir que o motivo esteja alcancavel num
  `Static` de apoio adjacente — um botao desabilitado sem explicacao e um beco.

- [ ] **Step 6: Rodar tudo e commitar**

```bash
python -m pytest tests/ -q
git add dbqm/ui tests/ui
git commit -m "feat(ui): esqueleto de carregamento e estados inertes distintos

Carregando passa a ter a forma do conteudo que vem, em vez de um rodopio que
deixa o layout saltar. Somente-leitura deixa de parecer formulario quebrado."
```

---

### Task 13: Inventário, teto zero e fechamento

**Files:**
- Create: `tests/design/test_inventario.py`
- Modify: `tests/design/test_sem_cor_literal.py` (`TETO = 0`)
- Modify: `AGENTS.md`, `README.md`, `dbqm/_version.py`

**Interfaces:**
- Consumes: os componentes das Tasks 9–12.
- Produces: nada.

- [ ] **Step 1: Escrever o teste de inventário (falha)**

```python
"""Teste 4 do design system: inventario de componentes.

Falha quando aparece um segundo componente com a mesma funcao, e quando o
chrome que o Dialog entrega volta a ser escrito a mao.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2] / "dbqm"


def test_moldura_de_dialog_existe_em_um_lugar_so():
    fora = []
    for arquivo in sorted(RAIZ.rglob("*.py")):
        if arquivo.name == "dialog.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "border: thick" in texto:
            fora.append(arquivo.relative_to(RAIZ.parent).as_posix())
    assert not fora, f"moldura de dialog escrita a mao em: {fora}"


def test_estado_vazio_nao_e_escrito_a_mao():
    """"Nenhum X" solto em Static e o antipadrao que o EmptyState resolve."""
    fora = []
    for arquivo in sorted((RAIZ / "ui").rglob("*.py")):
        if arquivo.name == "empty_state.py":
            continue
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if ("Nenhum" in linha or "Nenhuma" in linha) and "add_row" not in linha:
                fora.append(f"{arquivo.relative_to(RAIZ.parent).as_posix()}:{numero}")
    assert not fora, f"estado vazio escrito a mao em: {fora}"


def test_veredito_nao_e_montado_a_mao():
    fora = []
    for arquivo in sorted((RAIZ / "ui").rglob("*.py")):
        if arquivo.name == "veredito.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "$veredito-" in texto:
            fora.append(arquivo.relative_to(RAIZ.parent).as_posix())
    assert not fora, f"veredito montado a mao em: {fora}"
```

- [ ] **Step 2: Rodar, ver falhar e corrigir o que ele apontar**

Run: `python -m pytest tests/design/test_inventario.py -q`
Expected: FAIL listando o que escapou das Tasks 9–12. Corrigir cada ponto até passar. Se algum caso for legítimo, acrescentá-lo à lista de isenções **com um comentário dizendo por quê** — nunca em silêncio.

- [ ] **Step 3: Zerar o teto de cor literal**

Em `tests/design/test_sem_cor_literal.py`, `TETO = 0`.

Run: `python -m pytest tests/design/test_sem_cor_literal.py -q`
Corrigir o que sobrou até passar.

- [ ] **Step 4: Verificar que os quatro testes conseguem falhar**

Um de cada vez, reverter a regra que ele guarda e confirmar a falha, depois desfazer:

1. Cor literal: acrescentar `COR = "#123456"` em `dbqm/ui/utils.py`.
2. Paridade: remover uma chave de `TOKENS_CLARO`.
3. Contraste: mudar `TOKENS_ESCURO["texto"]` para `"#171b22"`.
4. Inventário: acrescentar `border: thick $borda-forte` em qualquer `DEFAULT_CSS`.

Um teste que passa nos dois casos é pior que teste nenhum.

- [ ] **Step 5: Documentação**

`AGENTS.md`: acrescentar `design/` à árvore de arquitetura e à regra de camadas —
"`design/` não importa nada do `dbqm`; `core/` e `ui/` podem importá-lo".

`README.md`: acrescentar o design system à lista de features, `dbqm/design/` e os
três widgets novos à árvore de estrutura, e atualizar a contagem de testes.

- [ ] **Step 6: Rodar tudo, versionar e publicar**

```bash
python -m pytest tests/ -q
# bump minor em dbqm/_version.py (1.19.0 -> 1.20.0)
python -m build
git add tests/design AGENTS.md README.md dbqm/_version.py
git commit -m "feat(ui): fechar o design system — inventario e teto zero

Os quatro testes de manutencao no lugar, cada um verificado revertendo a regra
que guarda. Zero cor literal fora dos tokens."
git push
PYPI_TOKEN=$(cat .env | tr -d '\r\n')
python -m twine upload dist/dbqm-1.20.0* -u __token__ -p "$PYPI_TOKEN"
```

---

## Cobertura do spec

| Seção do spec | Tarefa |
|---|---|
| §4 uma fonte, três consumidores | 1 (fonte), 2 (Textual), 6 (Rich), 7 (CSS) |
| §5 camada 1 — primitivas | 1 (comentário de origem), 8 (valores) |
| §6 camada 2 — tokens semânticos | 1, 8 |
| §6 contraste verificado | 1 (teste), 8 (zerado) |
| §7 `Dialog` | 9 |
| §7 `EmptyState` | 10 |
| §7 `Veredito` / `StatusOperacao` | 11 |
| §7 `Panel` passa a consumir `$painel`/`$borda` | 4 |
| §8 estados obrigatórios — vazio | 10 |
| §8 carregando / desabilitado / somente-leitura | 12 |
| §9 escrita da interface | 5 (sucesso sem tinta), 10 (redação dos vazios) |
| §10 foco visível | 2 (anel definido no tema, uma vez) |
| §11 os quatro testes | 1 (paridade, contraste), 3 (cor literal), 13 (inventário) |
| §12 ordem de migração | 1–3 tokens, 4–7 substituição, 8 valores, 9–12 componentes, 13 trava |

**Fora de escopo**, exatamente como o spec declara: tema claro alternativo além
do par Plano, redesenho de layout, e componentes novos para o CLI. O estado de
**erro** do §8 não tem tarefa própria porque já existe: `ErrorModal` mais o
padrão de mensagem adotado em `db_manager` (causa + saída) o cobrem; a Task 5
apenas troca sua cor por `$op-falha`.
