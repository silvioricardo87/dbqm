# Gramática de Layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao dbqm uma gramática de estrutura — uma moldura de seção, um mecanismo de navegação por cardinalidade, uma densidade de tabela que não trunca, e ações ancoradas ao que operam — aplicada às 16 telas e travada por guardas.

**Architecture:** A fase 1 (cor) já estabeleceu o padrão: componente com variantes fechadas, guarda repo-wide por regra, cada guarda verificado quebrando a regra que protege. Esta fase segue o mesmo molde. Nenhum token novo é criado — a gramática usa os 15 existentes.

**Tech Stack:** Python ≥3.10, Textual 8.2.7, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-08-22-gramatica-layout-design.md`

## Global Constraints

- **Rótulos de UI e comentários omitem acentos** (`Historico`, `conexao`, `Nao`). Convenção do projeto. Não "corrigir". Docs em `docs/` usam acentos normalmente.
- **Nenhum token novo.** A gramática consome os 15 de `dbqm/design/tokens.py`. Se algo parecer precisar de token novo, é sinal de erro de análise — reporte antes de criar.
- **Sete guardas da fase 1 continuam valendo** e não podem regredir: cor literal (`TETO = 0`), paridade de tokens, contraste calculado, `$var` resolvível em CSS, markup do CLI, override de `Dialog`, markup de veredito montado à mão.
- **Conventional Commits**, `<type>(<scope>)` com **as duas partes**; scopes `ui|core|models|config|web`. Um subject sem tipo é malformado e já precisou de amend uma vez. **Nunca** linha de atribuição a IA.
- **Suíte verde em todo commit.** `python -m pytest tests/ -q` rodado em **foreground** (~110s). Baseline: **845 testes**.
- **Ciclo por tarefa:** testes → commit. **Sem push, sem publicação, sem build, sem bump de versão** até o fim; a branch é `feature/design-system-plano`, não publicada, e o mantenedor decide o merge.
- **Verificado empiricamente e disponível:** `DataTable` aceita `fixed_columns` e `zebra_stripes`; `compose()` do widget e filhos por `with` coexistem; `Content.from_markup` é obrigatório para markup com `$token` em célula de `DataTable` (Rich puro levanta `MarkupError`).

---

## File Structure

**Criar:**
- `dbqm/ui/widgets/lista_hierarquica.py` — helper que monta item de lista em 2–3 linhas
- `tests/design/test_inventario_layout.py` — os cinco guardas de layout

**Modificar (produto):**
- `dbqm/ui/widgets/result_table.py` — chave fixa, zebra, rolagem (o modo registro ja existe)
- `dbqm/ui/screens/connections.py`, `dbqm/ui/widgets/query_list.py`, `dbqm/ui/screens/browser.py` — hierarquia de item
- `dbqm/ui/screens/query_exec.py`, `dbqm/ui/screens/group_run.py` — abas → `Select`; remoção de `ListView`
- `dbqm/ui/screens/settings.py` — um painel por assunto, caminho elidido, rolagem vertical
- `dbqm/ui/screens/ferramentas.py`, `dbqm/ui/screens/config_port.py` — botão-menu → lista; painel e contexto
- `dbqm/ui/screens/oracle_clients.py` — bordas cruas → `Panel`
- `dbqm/ui/screens/{exec_routine,template_manage,group_exec,group_manage,query_manage,package_editor,adhoc,history}.py` — moldura e ancoragem

**Modificar (docs):** `AGENTS.md`, `README.md`, `dbqm/_version.py`

---

### Task 1: `ResultTable` — chave fixa, zebra, rolagem

O primeiro passo porque libera a altura que a moldura vai consumir, e porque é o defeito mais medido: ilegível já a 7 colunas, com mediana de 9 e máximo de 36.

**Files:**
- Modify: `dbqm/ui/widgets/result_table.py`
- Test: `tests/ui/test_widgets.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: `ResultTable` com `fixed_columns=1` e `zebra_stripes=True` quando há ao menos 2 colunas.

- [ ] **Step 1: Escrever o teste (falha)**

`ResultTable` recebe um `QueryResult` via `load_result(result)` — **não** um par
`colunas`/`linhas`. Verificado no código; o plano supunha errado.

```python
from dbqm.core.query_engine import QueryResult


def _resultado(colunas, linhas):
    return QueryResult(
        query_name="t", connection_name="c",
        columns=colunas, rows=linhas, row_count=len(linhas), elapsed=0.01,
    )


@pytest.mark.asyncio
async def test_result_table_fixa_a_coluna_chave_e_lista_zebra():
    """A primeira coluna nunca sai de vista ao rolar lateralmente.

    O dbqm existe para comparar: sem saber de qual registro e a linha, as
    demais colunas nao significam nada.
    """
    from textual.widgets import DataTable
    from dbqm.ui.widgets.result_table import ResultTable
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield ResultTable(id="rt")

    app = App_()
    async with app.run_test() as pilot:
        rt = app.query_one("#rt", ResultTable)
        rt.load_result(_resultado(
            ["NUM_APOLICE", "SITUACAO", "VLR_PREMIO"],
            [["8801194920", "ATIVA", "3.482,90"]],
        ))
        await pilot.pause()
        dt = rt.query_one(DataTable)
        assert dt.fixed_columns == 1
        assert dt.zebra_stripes is True


@pytest.mark.asyncio
async def test_result_table_nao_fixa_coluna_quando_ha_uma_so():
    """Fixar a unica coluna nao protege nada e rouba largura."""
    from textual.widgets import DataTable
    from dbqm.ui.widgets.result_table import ResultTable
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield ResultTable(id="rt")

    app = App_()
    async with app.run_test() as pilot:
        rt = app.query_one("#rt", ResultTable)
        rt.load_result(_resultado(["TOTAL"], [["42"]]))
        await pilot.pause()
        assert app.query_one(DataTable).fixed_columns == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/ui/test_widgets.py -k result_table_fixa -q`
Expected: FAIL — `fixed_columns` é 0 hoje.

- [ ] **Step 3: Implementar**

Em `result_table.py`, ao construir a `DataTable`, passar `zebra_stripes=True` e definir `fixed_columns = 1 if len(colunas) > 1 else 0`. Comentar por que:

```python
# A chave fixa e o que torna a rolagem lateral utilizavel: sem ela, ao rolar
# para a direita voce perde de vista de qual registro e a linha, e as colunas
# restantes deixam de significar alguma coisa. Com uma coluna so, fixar nao
# protege nada e rouba largura.
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/ui/ -q`

- [ ] **Step 5: Olhar com dados reais**

Execute uma consulta de verdade e confira que a chave permanece visível ao rolar:

```bash
python -m dbqm sql "select table_name, num_rows, last_analyzed, tablespace_name, partitioned, temporary, status from all_tables where owner='SYS' and rownum <= 5" "MGORA7ORA9"
```

O CLI não usa `ResultTable` (renderiza com Rich), então isto valida o **dado**, não o widget. Para o widget, monte a TUI e navegue. Registre o que observou.

- [ ] **Step 6: Commitar**

```bash
python -m pytest tests/ -q
git add dbqm/ui/widgets/result_table.py tests/ui/test_widgets.py
git commit -m "feat(ui): coluna-chave fixa e zebra na tabela de resultado

A tabela ficava ilegivel ja a 7 colunas, abaixo da mediana medida de 9 (maximo
36). Passa a manter as colunas na largura real e rolar lateralmente, com a
primeira coluna fixa: sem ela, ao rolar perde-se de vista de qual registro e a
linha. Textual ja oferecia fixed_columns e zebra_stripes; o produto nao usava."
```

---

### Task 2: Esqueleto com a forma real, e alinhar o modo registro

O modo registro **não é construído aqui** — `toggle_vertical()` já existe, com tecla
`V`, e construir outro criaria o componente duplicado que o inventário reprova.
Esta tarefa corrige o que de fato está errado.

**Files:**
- Modify: `dbqm/ui/screens/query_exec.py:118`, `dbqm/ui/screens/group_exec.py:102`
- Modify: `dbqm/ui/widgets/result_table.py` (`_show_vertical`)
- Test: `tests/ui/test_screens.py`

- [ ] **Step 1: Escrever o teste (falha)**

```python
@pytest.mark.asyncio
async def test_esqueleto_de_resultado_tem_a_forma_mediana(tmp_config_dir):
    """A mediana medida das 68 consultas salvas e 9 colunas, nao 4.

    Um esqueleto com a forma errada produz o salto de layout que ele existe
    para impedir — foi o defeito encontrado em browser.py na fase 1.
    """
    from dbqm.ui.widgets.esqueleto import Esqueleto
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield QueryExecScreen()

    app = App_()
    async with app.run_test():
        esq = app.query_one("#result-skeleton", Esqueleto)
        assert len(esq.query(".esqueleto-linha")) == 8
        primeira = esq.query(".esqueleto-linha").first()
        assert len(primeira.query(".esqueleto-celula")) == 9
```

- [ ] **Step 2: Rodar e ver falhar**

Expected: FAIL — 4 celulas, nao 9.

- [ ] **Step 3: Corrigir os dois call sites**

`query_exec.py:118` e `group_exec.py:102` passam a `colunas=9`. Comente a origem
do numero, para que ele nao vire folclore:

```python
# 9 e a mediana medida das consultas salvas (min 1, max 36). Um esqueleto com a
# forma errada causa o salto de layout que ele existe para impedir.
```

- [ ] **Step 4: Alinhar `_show_vertical` a tipografia da gramatica**

Hoje ele usa `*** Registro N ***` e texto plano. Passa a usar os tokens:
identificacao do registro em `$texto-forte`, rotulo do campo em `$texto-apoio`,
valor em `$texto`. Mantem o alinhamento a direita dos rotulos, que ja esta certo.
**Nao mude a tecla nem a assinatura** — o modo ja e conhecido pelos usuarios.

- [ ] **Step 5: Rodar e commitar**

```bash
python -m pytest tests/ -q
git add dbqm/ui/screens/query_exec.py dbqm/ui/screens/group_exec.py dbqm/ui/widgets/result_table.py tests/ui/test_screens.py
git commit -m "fix(ui): esqueleto de resultado com a forma mediana real

Estava em 4 colunas; a mediana medida das 68 consultas salvas e 9, com maximo de
36. Esqueleto com forma errada causa o salto de layout que ele existe para
impedir. Alinha tambem o modo registro ja existente a tipografia da gramatica."
```

---

### Task 3: Componente de item de lista hierárquico

**Files:**
- Create: `dbqm/ui/widgets/lista_hierarquica.py`
- Test: `tests/ui/test_widgets.py`

**Interfaces:**
- Produces: `item_hierarquico(identidade: str, desambiguacao: str = "", contexto: str = "") -> Content`

- [ ] **Step 1: Escrever o teste (falha)**

```python
def test_item_hierarquico_poe_identidade_sozinha_na_primeira_linha():
    from dbqm.ui.widgets.lista_hierarquica import item_hierarquico

    c = item_hierarquico("MGORA7ORA9", "Oracle/TNS · MGORA7ORA9", "Producao prod-day")
    linhas = str(c).split("\n")
    assert linhas[0].strip() == "MGORA7ORA9"
    assert "Oracle/TNS" in linhas[1]
    assert "Producao" in linhas[2]


def test_item_hierarquico_omite_linhas_vazias():
    from dbqm.ui.widgets.lista_hierarquica import item_hierarquico

    assert len(str(item_hierarquico("SO_NOME")).split("\n")) == 1


def test_item_hierarquico_escapa_o_conteudo():
    """Nome de conexao ou descricao vem de dado do usuario."""
    from dbqm.ui.widgets.lista_hierarquica import item_hierarquico

    c = item_hierarquico("[/]quebra", "x")
    assert "quebra" in str(c)
```

- [ ] **Step 2–4: Rodar, implementar, rodar**

A função devolve `Content`, não `str` — é o que `OptionList.add_option` e `DataTable` aceitam sem passar por Rich puro. Use os tokens `$texto-forte`, `$texto-apoio` e `$texto-desabilitado`, e escape cada campo.

- [ ] **Step 5: Commitar**

```bash
git commit -m "feat(ui): item de lista com hierarquia de tres linhas

Identidade sozinha na primeira linha, desambiguacao e contexto recuados. A
hierarquia faz o trabalho que um separador faria e diz, alem disso, o que e cada
coisa."
```

---

### Task 4: Aplicar hierarquia — conexões, consultas, objetos

**Files:**
- Modify: `dbqm/ui/screens/connections.py:280`, `dbqm/ui/widgets/query_list.py`, `dbqm/ui/screens/browser.py`
- Test: `tests/ui/test_screens.py`

- [ ] **Step 1: Teste que reprova a concatenação (falha)**

```python
@pytest.mark.asyncio
async def test_lista_de_conexoes_tem_hierarquia_e_nao_concatena(tmp_config_dir):
    """O item tem hierarquia de linhas; nao e uma string concatenada."""
    from textual.widgets import OptionList
    from dbqm.models.connection import Connection, save_connections
    from dbqm.ui.screens.connections import ConnectionsScreen
    from tests.ui._helpers import ThemedTestApp

    save_connections([
        Connection(name="MGORA7ORA9", db_type="oracle", user="u", password="p",
                   mode="tns", tns_name="MGORA7ORA9",
                   description="Producao prod-day, somente leitura via dblink"),
        Connection(name="ASDADM", db_type="oracle", user="u", password="p",
                   mode="tns", tns_name="ATSSUS", description="Sustentacao"),
    ])

    class App_(ThemedTestApp):
        def compose(self):
            yield ConnectionsScreen()

    app = App_()
    async with app.run_test():
        lista = app.query_one("#conn-list", OptionList)
        prompt = str(lista.get_option_at_index(0).prompt)
        assert chr(10) in prompt, "item deve ocupar mais de uma linha"
        assert " | " not in prompt, "descricao nao entra concatenada"
        assert prompt.splitlines()[0].strip().startswith("MGORA7ORA9")


def test_query_list_nao_trunca_mais_a_descricao():
    """A truncagem em 35 caracteres existia para caber numa linha so."""
    from pathlib import Path

    fonte = Path("dbqm/ui/widgets/query_list.py").read_text(encoding="utf-8")
    assert "[:32]" not in fonte, "a truncagem deixou de ser necessaria"
```

- [ ] **Step 2–4:** rodar, aplicar `item_hierarquico` nos três pontos, rodar.

**Remova a truncagem de 35 caracteres do `query_list.py`** — ela existia para caber numa linha só, e a hierarquia torna-a desnecessária. Diga no report o que aconteceu com descrições longas depois de removê-la; se ainda houver corte, ele agora é do terminal, não do produto.

- [ ] **Step 5: Commitar**

---

### Task 5: Navegação por cardinalidade

**Files:**
- Modify: `dbqm/ui/screens/query_exec.py`, `dbqm/ui/screens/group_run.py`
- Test: `tests/ui/test_screens.py`

- [ ] **Step 1: Teste (falha)**

```python
@pytest.mark.asyncio
async def test_pastas_viram_select_com_contagem(tmp_config_dir):
    """16 pastas nao cabem em aba nenhuma; a barra de botoes rolava lateral."""
    from textual.widgets import Select
    from dbqm.models.query import Query, save_queries
    from dbqm.ui.screens.query_exec import QueryExecScreen
    from tests.ui._helpers import ThemedTestApp

    save_queries([
        Query(name="q%d" % i, sql="select 1 from dual", connection="c",
              folder="Pasta%d" % (i % 3))
        for i in range(9)
    ])

    class App_(ThemedTestApp):
        def compose(self):
            yield QueryExecScreen()

    app = App_()
    async with app.run_test():
        seletor = app.query_one("#folder-select", Select)
        rotulos = [str(r) for r, _ in seletor._options]
        assert any("(3)" in r for r in rotulos), "cada pasta mostra a contagem"
        assert not app.query("#folder-bar"), "a barra de botoes some"


def test_listview_saiu_do_vocabulario():
    """ListView fazia o mesmo que OptionList em dois lugares."""
    from pathlib import Path

    achados = [
        p.as_posix()
        for p in Path("dbqm/ui").rglob("*.py")
        if "ListView(" in p.read_text(encoding="utf-8")
    ]
    assert not achados, "ListView ainda usado em: %s" % achados
```

> `_options` e interno do `Select`. Se esta versao do Textual nao o expuser, leia
> os rotulos pelo caminho publico que ela oferecer e **diga no report** qual usou.

- [ ] **Step 2–4:** rodar, substituir a barra de botões por `Select` com contagem, remover `ListView` onde `OptionList` já faz o mesmo, rodar.

**Prefixo comum:** as 16 pastas começam com `Mapfre Sustentacao/`. Decida se o `Select` mostra o prefixo ou o elide, e **justifique no report** — eliminar prefixo redundante ganha largura, mas some com informação se um dia houver dois prefixos.

- [ ] **Step 5: Commitar**

---

### Task 6: `Panel` como única moldura, e rolagem vertical

**Files:**
- Modify — **borda crua → `Panel`** (medido: só 3 telas): `dbqm/ui/screens/adhoc.py`, `config_port.py`, `oracle_clients.py`
- Modify — **telas sem moldura nenhuma ganham `Panel`**: `exec_routine.py`, `template_manage.py`, `group_exec.py`, `group_manage.py`, `query_manage.py`, `package_editor.py`, `query_exec.py`, `group_run.py`, `ferramentas.py`, `config_port.py`

> São duas listas diferentes, e a primeira redação as confundiu: ter borda crua
> não é o mesmo que não ter moldura. Só `adhoc`, `config_port` e `oracle_clients`
> desenham borda a mão.
- Test: `tests/design/test_inventario_layout.py`

- [ ] **Step 1: Guarda `sem_borda_crua` (falha)**

```python
import re
from pathlib import Path

# Panel e Dialog sao as molduras; o resto nao desenha borda.
MOLDURAS = {"dbqm/ui/widgets/panel.py", "dbqm/ui/widgets/dialog.py"}
BORDA = re.compile(r"border(?:-top|-bottom|-left|-right)?\s*:")


def test_sem_borda_crua_fora_de_componente_de_moldura():
    """Um terceiro vocabulario de moldura foi como se chegou a tres."""
    fora = []
    for arquivo in sorted(Path("dbqm/ui").rglob("*.py")):
        rel = arquivo.as_posix()
        if rel in MOLDURAS:
            continue
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if BORDA.search(linha) and "none" not in linha:
                fora.append("%s:%d" % (rel, n))
    assert not fora, "borda fora de um componente de moldura: %s" % fora


@pytest.mark.asyncio
async def test_configuracoes_nao_esconde_a_secao_oracle(tmp_config_dir):
    """A secao existia no codigo e nao renderizava — cortada abaixo da dobra."""
    from textual.widgets import Static
    from dbqm.ui.screens.settings import SettingsScreen
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield SettingsScreen()

    app = App_()
    async with app.run_test(size=(120, 34)):
        alvo = app.query_one("#settings-oracle-client-current", Static)
        assert alvo.region.height > 0, "a secao Oracle precisa ser alcancavel"
```

- [ ] **Step 2–4:** rodar (deve falhar apontando 6 ocorrências), migrar para `Panel`, rodar.

- [ ] **Step 5: Rolagem vertical**

Toda tela cujo conteúdo pode exceder a viewport rola verticalmente. Verifique especificamente que a seção Oracle de `settings` fica alcançável — hoje ela é cortada em silêncio. Teste que a afirme.

- [ ] **Step 6: Commitar**

---

### Task 7: Configurações — um painel por assunto

**Files:**
- Modify: `dbqm/ui/screens/settings.py`
- Test: `tests/ui/test_screens.py`

- [ ] **Step 1: Teste (falha)**

```python
@pytest.mark.asyncio
async def test_cada_assunto_de_configuracoes_tem_seu_painel(tmp_config_dir):
    from dbqm.ui.screens.settings import SettingsScreen
    from dbqm.ui.widgets.panel import Panel
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield SettingsScreen()

    app = App_()
    async with app.run_test(size=(120, 40)):
        titulos = " ".join(str(p.render()) for p in app.query(Panel)).lower()
        for assunto in ("tema", "auditoria", "exporta", "oracle"):
            assert assunto in titulos, "%s sem painel proprio" % assunto


def test_caminho_longo_e_elidido_no_meio():
    """O inicio e o fim identificam um caminho; o meio e o descartavel."""
    from dbqm.ui.screens.settings import elidir_caminho

    longo = "C:/Users/ricar/AppData/Local/Temp/claude/muito/fundo/exports"
    curto = elidir_caminho(longo, 40)
    assert len(curto) <= 40
    assert curto.startswith("C:/Users")
    assert curto.endswith("exports")
    assert "..." in curto or chr(8230) in curto
```

> O teste le o titulo do painel via `render()`. Leia `dbqm/ui/widgets/panel.py` e
> use o caminho real de acesso ao titulo; se divergir, ajuste e **diga no report**.

- [ ] **Step 2–4:** rodar, reestruturar, rodar.

- [ ] **Step 5: Commitar**

---

### Task 8: Botão-menu vira lista; ações reancoradas

**Files:**
- Modify — **botão-menu vira lista**: `dbqm/ui/screens/ferramentas.py`, `config_port.py`
- Modify — **as 5 centralizações reais** (medido): `adhoc.py` (`#adhoc-btn-bar`, `#adhoc-dml-result`), `browser.py` (`#obj-preview-buttons`), `connections.py` (`#conn-form-buttons`), `package_editor.py` (`#pe-empty`)

> **Não toque nos modais.** 38 das 43 centralizações estão dentro de `*Modal`, e
> ali centralizar é exatamente o que o §7 do spec manda: o cluster **é** a tela.
> A primeira redação deste plano mandava reancorar `query_manage` (11) e
> `group_manage` (10) — todas modais, todas corretas como estão.
- Test: `tests/design/test_inventario_layout.py`, `tests/ui/test_screens.py`

- [ ] **Step 1: Guarda `sem_cluster_centralizado` (falha)**

```python
import re
from pathlib import Path

CENTRO = re.compile(r"(?:content-)?align:\s*center")
GRUPO = re.compile(
    r"([#.][\w-]*(?:botoes|buttons|acoes|actions)[\w-]*\s*\{[^}]*\})"
)


def test_sem_cluster_de_botao_centralizado_fora_de_dialogo():
    """Centralizar so faz sentido quando o cluster E a tela — um dialogo.

    Numa tela de trabalho, centralizar desconecta a acao do que ela opera.
    """
    fora = []
    for arquivo in sorted(Path("dbqm/ui/screens").rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        for bloco in GRUPO.findall(texto):
            seletor = bloco.splitlines()[0].strip()
            # Num dialogo, o cluster E a tela: centralizar ali e a regra, nao a
            # excecao. 38 das 43 ocorrencias medidas sao modais legitimos.
            if "Modal" in seletor:
                continue
            if CENTRO.search(bloco):
                fora.append("%s: %s" % (arquivo.as_posix(), seletor))
    assert not fora, "cluster centralizado em tela de trabalho: %s" % fora


@pytest.mark.asyncio
async def test_ferramentas_e_lista_e_nao_botoes_de_largura_total(tmp_config_dir):
    """Quatro botoes de largura total sao quatro botoes fingindo ser um menu."""
    from textual.widgets import Button, OptionList
    from dbqm.ui.screens.ferramentas import FerramentasScreen
    from tests.ui._helpers import ThemedTestApp

    class App_(ThemedTestApp):
        def compose(self):
            yield FerramentasScreen()

    app = App_()
    async with app.run_test():
        assert app.query(OptionList), "a navegacao de ferramentas e uma lista"
        assert not app.query(Button), "botao e acao, nunca navegacao"
```

> O guarda casa por **nome de seletor** (`#botoes`, `.acoes`…). Um cluster com
> outro nome escapa — nomeie esse limite no codigo do teste, como fazem os
> guardas da fase 1.

- [ ] **Step 2–4:** `Ferramentas` vira `OptionList` de ferramentas; `config_port` ganha `Panel` e contexto; os clusters centralizados são reancorados à esquerda do painel que operam; ação destrutiva separada.

- [ ] **Step 5: Commitar**

---

### Task 9: Travar e documentar

**Files:**
- Modify: `tests/design/test_inventario_layout.py`, `AGENTS.md`, `README.md`, `dbqm/_version.py`

- [ ] **Step 1: Completar os cinco guardas** — `sem_borda_crua`, `sem_listview`, `sem_cluster_centralizado`, `rotulo_nao_achatado`, `tabela_com_chave_fixa`.

- [ ] **Step 2: Verificar cada um quebrando a regra que protege.** Registre o que quebrou, a mensagem de falha e a reversão. **Um guarda que passa nos dois estados é pior que guarda nenhum.**

- [ ] **Step 3: Nomear os limites** de cada varredura textual no próprio código — o que ela não vê, e que isso foi escolha.

- [ ] **Step 4: Docs.** `AGENTS.md` registra a gramática; `README.md` atualiza features, árvore e contagem de testes medida.

- [ ] **Step 5: Bump** para `1.21.0`.

- [ ] **Step 6: Commitar.** Sem push, sem publicação.

---

## Cobertura do spec

| Seção do spec | Tarefa |
|---|---|
| §4 moldura única | 6 |
| §4 transbordo vertical | 6 |
| §5 navegação por cardinalidade | 5 |
| §5 hierarquia do item de lista | 3, 4 |
| §6 densidade — chave fixa, zebra, rolagem | 1 |
| §6 densidade — modo registro | 2 |
| §6 esqueleto com 9 colunas | 1 |
| §7 ações ancoradas, botão-menu | 8 |
| §8 as 16 telas | 4, 5, 6, 7, 8 |
| §10 os cinco guardas | 6, 8, 9 |

**Fora de escopo**, conforme §11 do spec: conversão de `$text-muted`/`[dim]`, a decisão sobre o conceito de "aviso", e redesenho de fluxo.
