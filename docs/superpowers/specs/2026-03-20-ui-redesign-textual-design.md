# DBQM UI Redesign: Migração para Textual TUI

**Data:** 2026-03-20
**Status:** Aprovado
**Escopo:** Reescrita completa da camada UI (dbqm/ui/) usando Textual framework

---

## 1. Contexto e Problema

A UI atual do DBQM usa Rich (output formatado) + InquirerPy (prompts inline). Isso resulta em:

- **Sem layout fixo** — menus e conteúdo rolam no terminal, sem header/footer/sidebar persistentes
- **Altura variável** — cada menu tem tamanho diferente, causando "saltos" visuais
- **Sem navegação visível** — não há indicação de "onde estou" na hierarquia
- **Descrições ilegíveis** — tudo comprimido numa linha: `* nome (conexão -> tabela) - descrição`
- **Paradigma print-based** — incompatível com layout fixo de aplicação

O problema fundamental é arquitetural: a aplicação precisa de um paradigma **application-based** (tela fixa com regiões) em vez de **print-based** (imprime e rola).

## 2. Decisões de Design

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| Framework | Textual (fullscreen TUI) | Único que resolve layout fixo com sidebar/header/footer |
| Layout principal | Sidebar permanente + conteúdo | Toda navegação visível o tempo todo |
| Sidebar | Colapsável (Ctrl+B) | Ganhar espaço para tabelas largas quando necessário |
| Sidebar behavior | Fixa (não expande sub-itens) | Mais simples e previsível; breadcrumb mostra contexto |
| Tema padrão | GitHub Dark | Aprovado em mockups |
| Temas | Light + Dark, seletor nas configurações | Suporte a ambos contextos |
| Parâmetros | Modal dialog | Tanto para primeira execução quanto reexecução |
| Reexecução | Botão R abre modal com valores atuais | Params read-only no resultado, modal para editar |

## 3. Arquitetura

### 3.1 Princípio: Separação UI / Lógica

A lógica de negócio (core/, models/) permanece intocada. Apenas a camada UI (dbqm/ui/) é reescrita. A interface entre UI e lógica já está bem definida:

- `core/query_engine.py` → executa queries, retorna `QueryResult`
- `core/group_engine.py` → compara resultados, retorna `GroupResult`
- `core/db_manager.py` → gerencia conexões
- `core/exporter.py` → exporta resultados
- `models/` → CRUD de conexões, queries, grupos, settings

### 3.2 Estrutura de Arquivos

```
dbqm/ui/
├── app.py                  # DBQMApp(App) — ponto de entrada Textual, first-run detection
├── theme.py                # Definições de tema (github-dark, github-light)
├── screens/
│   ├── __init__.py
│   ├── query_exec.py       # Execução de consulta salva
│   ├── query_manage.py     # CRUD de consultas (criar, editar, duplicar, favoritar, pastas, DE-PARA, visualizar SQL)
│   ├── group_exec.py       # Execução de grupo comparativo
│   ├── group_manage.py     # CRUD de grupos (criar, editar, pastas, normalização)
│   ├── adhoc.py            # SQL avulso (input multiline, DML com commit/rollback, gerar SQL, salvar como query)
│   ├── ddl.py              # Extração DDL (com progress indicator)
│   ├── browser_tables.py   # Object browser: tabelas (estrutura, query, paginação)
│   ├── browser_packages.py # Object browser: packages Oracle (spec, body, rotinas, execução)
│   ├── browser_views.py    # Object browser: views (definição SQL, query dados)
│   ├── browser_routines.py # Object browser: routines PostgreSQL/MySQL
│   ├── history.py          # Histórico de execuções
│   ├── connections.py      # CRUD de conexões
│   ├── settings.py         # Configurações (tema, auditoria)
│   └── config_port.py      # Exportar/Importar configurações
├── widgets/
│   ├── __init__.py
│   ├── sidebar.py          # Sidebar colapsável com seções
│   ├── breadcrumb.py       # Breadcrumb navegável
│   ├── result_table.py     # DataTable para resultados de query
│   ├── query_list.py       # Lista de consultas estilo card
│   ├── group_result.py     # Visualização de resultado comparativo (flat + pivoted)
│   ├── sql_viewer.py       # Syntax highlight SQL (read-only)
│   ├── status_bar.py       # Footer com status de conexão
│   ├── action_bar.py       # Barra de ações contextuais
│   └── progress.py         # Progress indicator para operações longas (DDL, queries)
├── modals/
│   ├── __init__.py
│   ├── param_input.py      # Modal de parâmetros (com defaults e descrição)
│   ├── confirm.py          # Dialog de confirmação (remover, limpar, commit/rollback)
│   ├── export_picker.py    # Seleção de formato de export
│   ├── text_input.py       # Input de texto genérico (renomear, etc.)
│   ├── connection_form.py  # Formulário de conexão (tipo, host, user, etc.)
│   └── column_maps.py      # Configuração de mapeamento DE-PARA
└── legacy/
    └── display.py          # Funções Rich mantidas apenas para export PNG/TXT
```

**Nota:** `dbqm/cli.py` permanece no local original — não faz parte da reescrita.

### 3.3 Layout Principal

Dimensões em caracteres (Textual usa character-based sizing):

```
┌─────────────────────────────────────────────────────────┐
│ DB Query Manager v1.0          ESC voltar · Ctrl+B hide │  ← Header (height: 1)
├──────────┬──────────────────────────────────────────────┤
│ CONSULTAS│ Consultas / Executar / saldo_cliente         │  ← Breadcrumb
│ ▸Executar├──────────────────────────────────────────────┤
│  SQL     │                                              │
│  Gerenc. │                                              │
│──────────│         Área de Conteúdo                     │  ← Conteúdo (fr 1)
│ GRUPOS   │         (screens/)                           │
│  Executar│                                              │
│  Gerenc. │                                              │
│──────────│                                              │
│ FERRAM.  │                                              │
│  DDL     ├──────────────────────────────────────────────┤
│  Objetos │ V Vertical  E Exportar  R Reexecutar  Pag 1/1│  ← ActionBar
│  Histor. │                                              │
│──────────│                                              │
│ SISTEMA  │                                              │
│  Conexoes│                                              │
│  Export  │                                              │
│  Config  │                                              │
│  Sair    │                                              │
├──────────┴──────────────────────────────────────────────┤
│ ● ORACLE-PRD conectado      6 queries · 3 conn · 2 grp │  ← StatusBar (height: 1)
└─────────────────────────────────────────────────────────┘
```

- Sidebar expandida: `width: 24` (caracteres)
- Sidebar colapsada: `width: 5` (só ícones)
- Conteúdo: `fr 1` (ocupa todo espaço restante)

Sidebar colapsada (Ctrl+B):
```
┌─────────────────────────────────────────────────────────┐
│ DB Query Manager v1.0                     Ctrl+B expand │
├────┬────────────────────────────────────────────────────┤
│ 🔍 │ Consultas / Executar / saldo_cliente               │
│ ⌨  ├────────────────────────────────────────────────────┤
│ 📝 │                                                    │
│────│            Área de Conteúdo (~95% largura)         │
│ 📊 │                                                    │
│ 📁 │                                                    │
│────│                                                    │
│ 🏗  │                                                    │
│ 🗂  │                                                    │
│ 📜 │                                                    │
│────│                                                    │
│ 🔌 │                                                    │
│ 📦 │                                                    │
│ ⚙  │                                                    │
│ 🚪 │                                                    │
├────┴────────────────────────────────────────────────────┤
│ ● ORACLE-PRD                                            │
└─────────────────────────────────────────────────────────┘
```

### 3.4 Componentes Detalhados

#### Sidebar (`widgets/sidebar.py`)

- `Vertical` container com `Static` labels e `ListView` items por seção
- Seções: Consultas (3 itens), Grupos (2), Ferramentas (3), Sistema (4 — incluindo Exportar/Importar e Sair)
- Item ativo: highlight com borda esquerda azul
- Labels de seção: uppercase cinza
- Modo expandido: ícone + texto (width: 24 chars)
- Modo colapsado: só ícone (width: 5 chars)
- Toggle: `Ctrl+B` via CSS class toggle
- Emite mensagem `SidebarItemSelected(action: str)`

#### Breadcrumb (`widgets/breadcrumb.py`)

- `Horizontal` container com `Static` labels clicáveis
- Separador: ` / ` em cinza
- Último item em branco bold (posição atual)
- Itens anteriores em azul, clicáveis para navegar de volta

#### ResultTable (`widgets/result_table.py`)

- Extends `DataTable` do Textual
- Aceita `QueryResult` e popula automaticamente
- Paginação: 100 linhas por página, controles Next/Prev
- Toggle vertical: muda para layout coluna-por-linha
- Adaptação automática de largura de coluna
- Truncamento com ellipsis para valores longos
- Header fixo durante scroll (nativo do DataTable)

#### ParamModal (`modals/param_input.py`)

- `ModalScreen` com formulário
- Um `Input` widget por parâmetro
- Label: nome do parâmetro + descrição
- Placeholder: valor default
- Pré-preenche com últimos valores usados (ou defaults)
- Botões: Executar (Enter) / Cancelar (ESC)
- Retorna `dict[str, str]` ou `None` se cancelado

#### QueryList (`widgets/query_list.py`)

- `ListView` com items customizados (rich renderables)
- Cada item mostra: estrela favorito, nome (bold), descrição (dim), badge conexão, tabela
- Filtro por pasta via tabs no topo
- Favoritos aparecem primeiro
- Busca/filter por texto (`/`)

#### GroupResult (`widgets/group_result.py`)

- Dois modos de exibição: flat (uma tabela por coluna) e pivoted (uma tabela por chave)
- Toggle entre modos via ActionBar
- Status cells com cores: OK (verde), DIFF (amarelo), ABSENT (vermelho), OK* (verde)
- Highlight de valores divergentes (minoria em vermelho)
- Resumo com contadores (iguais, diferentes, ausentes, normalizados)

#### ActionBar (`widgets/action_bar.py`)

- `Horizontal` container fixo abaixo do conteúdo
- Botões contextuais conforme a tela ativa:
  - Resultado de query: Vertical (V), Exportar (E), Reexecutar (R), Paginação
  - Resultado de grupo: Flat/Pivoted, Filtrar, Exportar, HTML, Ver individual, Reexecutar
  - Gerenciamento: Novo, Editar, Remover, etc.
  - Ad-hoc: Executar, Gerar SQL, Salvar como query
- Atalhos de teclado exibidos ao lado de cada ação

#### Progress (`widgets/progress.py`)

- Wrapper sobre `ProgressBar` do Textual
- Usado para DDL extraction, query execution longa
- Mensagem de status + barra de progresso + spinner

#### StatusBar (`widgets/status_bar.py`)

- `Footer` widget
- Lado esquerdo: indicador de conexão (● verde = conectado)
- Lado direito: contadores (N queries, N conexões, N grupos)

### 3.5 Temas

Dois temas built-in com possibilidade de extensão:

**GitHub Dark (padrão):**
- Background: `#0d1117`
- Surface: `#161b22`
- Border: `#30363d`
- Primary: `#58a6ff`
- Success: `#3fb950`
- Warning: `#e3b341`
- Error: `#f85149`
- Text: `#c9d1d9`
- Text bright: `#f0f6fc`
- Text dim: `#484f58`

**GitHub Light:**
- Background: `#ffffff`
- Surface: `#f6f8fa`
- Border: `#d0d7de`
- Primary: `#0969da`
- Success: `#1a7f37`
- Warning: `#9a6700`
- Error: `#cf222e`
- Text: `#1f2328`
- Text bright: `#000000`
- Text dim: `#656d76`

Implementado via Textual CSS variables + `Theme` class. Seletor em Settings permite trocar em runtime. Tema é persistido em `models/settings.py`.

### 3.6 Navegação e Keybindings

| Tecla | Ação | Contexto |
|-------|------|----------|
| ↑↓ | Navegar items | Sidebar, listas, tabelas |
| Enter | Selecionar/Confirmar | Global |
| ESC | Voltar (breadcrumb pop) | Global |
| Ctrl+B | Toggle sidebar | Global |
| Tab | Próximo widget/campo | Formulários |
| V | Toggle vertical view | Resultado de query |
| E | Exportar | Resultado de query/grupo |
| R | Reexecutar (abre modal) | Resultado de query/grupo |
| / | Buscar/filtrar | Listas |
| ? | Ajuda (keybindings) | Global |
| Ctrl+Q | Sair | Global |

### 3.7 Fluxos Principais

#### First-Run
1. `app.py` detecta que não existem conexões (`load_connections()` vazio)
2. Exibe mensagem de boas-vindas com botão para criar primeira conexão
3. Abre `ConnectionFormModal` diretamente

#### Executar Consulta Salva
1. Sidebar: "Executar" → screen `QueryExecScreen`
2. Se existem pastas: tabs de pasta no topo
3. `QueryList` mostra consultas (favoritos primeiro)
4. Seleciona consulta → se tem parâmetros, `ParamModal` abre
5. Executa (via `Worker` thread) → `ResultTable` mostra dados + `ActionBar`
6. Column maps (DE-PARA) aplicados automaticamente nos resultados
7. R para reexecutar → `ParamModal` com valores atuais

#### Executar Grupo Comparativo
1. Sidebar: "Executar grupo" → screen `GroupExecScreen`
2. Se existem pastas: tabs de pasta
3. Seleciona grupo → `ParamModal` para params compartilhados
4. Executa todas as queries com `Progress` indicator (via `Worker`)
5. `GroupResult` widget: flat ou pivoted, toggle via ActionBar
6. Filtrar por status (DIFF, ABSENT)
7. Ver resultado individual de cada query
8. Exportar (CSV/JSON/TXT) ou gerar relatório HTML

#### SQL Avulso
1. Screen com `TextArea` (syntax highlight SQL) + seletor de conexão
2. Classifica SQL (SELECT/INSERT/UPDATE/DELETE)
3. SELECT: resultado em `ResultTable`
4. DML: `ConfirmModal` para commit/rollback
5. Detecta parâmetros → oferece transformar literais em bind variables
6. "Gerar SQL" → substitui parâmetros e exporta como `.sql`
7. "Salvar como consulta" → abre formulário para nome/descrição

#### Gerenciar Consultas
1. Tabela com todas as consultas (pasta, nome, descrição, conexão, tabela, params)
2. ActionBar: Nova, Visualizar SQL, Editar, DE-PARA, Renomear, Favoritar, Pasta, Duplicar, Remover
3. Criar: modal de modo (colar SQL / wizard) → formulário step-by-step via modals
4. DE-PARA: `ColumnMapsModal` para configurar mapeamentos de valores

#### Gerenciar Grupos
1. Tabela com grupos existentes (nome, queries, descrição, pasta)
2. ActionBar: Novo, Editar, Renomear, Pasta, Remover
3. Criar: wizard multi-step (queries, params compartilhados, join key, colunas, normalização)

#### Object Browser
1. Sidebar: "Objetos" → seleciona conexão → seleciona tipo de objeto
2. Tabelas (`browser_tables.py`): estrutura (colunas, FKs, indexes), query com paginação, exportar
3. Packages (`browser_packages.py`): listar rotinas, ver spec/body, executar (com commit/rollback para procedures)
4. Views (`browser_views.py`): definição SQL com syntax highlight, query dados
5. Routines (`browser_routines.py`): listar, executar com params

#### Histórico
1. `DataTable` com últimas 50 execuções (data, tipo, nome, conexão, resultado, tempo)
2. Selecionar para ver detalhes (params, row count, erro)
3. Limpar histórico (com confirmação)

### 3.8 Async e Threading

Textual é async-first. As chamadas de banco são síncronas. Solução:

- **`@work` decorator** do Textual em todos os métodos que chamam `core/`:
  - `execute_query()`, `build_group_result()`, `test_connection()`
  - `fetch_table_columns()`, `extract_ddl()`
- Worker thread executa a operação; callback atualiza a UI
- Durante execução: `Progress` widget mostra spinner/barra
- Cancelamento: ESC durante execução cancela o Worker

Padrão:
```python
@work(thread=True)
def run_query(self, query, conn, params):
    result = execute_query(query, conn, params)
    self.call_from_thread(self.show_result, result)
```

### 3.9 Abertura de Arquivos Externos

Ao exportar e abrir arquivos (`os.startfile`, `subprocess.run`):
- O Textual app é temporariamente suspenso (`app.suspend()`) antes de abrir
- Após o processo externo, o app retoma automaticamente
- Alternativa: apenas mostrar o caminho do arquivo exportado sem abrir automaticamente

## 4. Mapeamento de Features: Atual → Nova UI

| Feature atual | Arquivo atual | Nova localização |
|--------------|--------------|-----------------|
| Menu principal | menu.py | app.py + sidebar.py |
| Executar consulta | flows/query_flow.py | screens/query_exec.py |
| SQL avulso | flows/adhoc_flow.py | screens/adhoc.py |
| Gerenciar consultas | query_wizard.py | screens/query_manage.py |
| Executar grupo | flows/group_flow.py | screens/group_exec.py |
| Gerenciar grupos | group_wizard.py | screens/group_manage.py |
| Extrair DDL | flows/ddl_flow.py | screens/ddl.py |
| Browser: tabelas | flows/object_browser_flow.py | screens/browser_tables.py |
| Browser: packages | flows/object_browser_flow.py | screens/browser_packages.py |
| Browser: views | flows/object_browser_flow.py | screens/browser_views.py |
| Browser: routines | flows/object_browser_flow.py | screens/browser_routines.py |
| Histórico | flows/history_flow.py | screens/history.py |
| Conexões | config_wizard.py | screens/connections.py |
| Configurações | flows/settings_flow.py | screens/settings.py |
| Export/Import config | flows/config_flow.py | screens/config_port.py |
| Prompts (select, text, etc.) | prompts.py | widgets Textual nativos |
| Display (tabelas, panels) | display.py | widgets/result_table.py, group_result.py, etc. |
| Display (export PNG/TXT) | display.py | legacy/display.py |
| Helpers (gather_params, etc.) | helpers.py | modals/param_input.py, etc. |
| Column maps (DE-PARA) | query_wizard.py | modals/column_maps.py |
| Folder management | query_wizard.py, group_wizard.py | modals via screens |

## 5. O Que NÃO Muda

- **`dbqm/core/`** — toda lógica de execução, parsing, exportação
- **`dbqm/models/`** — modelos de dados, persistência JSON (+ campo `theme` em settings)
- **`dbqm/cli.py`** — interface CLI não-interativa (permanece no local original)
- **`main.py`** — ponto de entrada (muda de `menu.main_menu()` para `DBQMApp().run()`)

## 6. O Que é Removido

- `dbqm/ui/prompts.py` — substituído por widgets Textual
- `dbqm/ui/menu.py` — substituído por Sidebar + routing na App
- `dbqm/ui/helpers.py` — funções migradas para widgets/modals
- `dbqm/ui/flows/` — todos os flows migrados para screens/
- `dbqm/ui/config_wizard.py` — migrado para screens/connections.py
- `dbqm/ui/query_wizard.py` — migrado para screens/query_manage.py
- `dbqm/ui/group_wizard.py` — migrado para screens/group_manage.py
- `dbqm/ui/display.py` — parcialmente mantido em `legacy/display.py` (só funções de export)
- Dependência `InquirerPy`

## 7. Dependências

**Adicionar:**
- `textual` — framework TUI principal (usar versão mais recente estável)

**Remover:**
- `InquirerPy` — substituído por widgets Textual
- `prompt_toolkit` — era dependência transitiva do InquirerPy (nota: Textual pode ter dependência indireta)

**Manter:**
- `rich` — usado pelo Textual internamente e por legacy/display.py para exports
