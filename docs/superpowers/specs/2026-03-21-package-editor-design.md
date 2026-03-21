# Editor de Packages Oracle

**Data:** 2026-03-21
**Status:** Aprovado
**Escopo:** Nova funcionalidade para criar e editar packages Oracle com compilação e feedback de erros inline

---

## 1. Contexto

O DBQM já permite visualizar packages Oracle no Object Browser (spec, body, rotinas), mas não permite edição nem compilação. Usuários precisam alternar entre o DBQM e ferramentas externas (SQL Developer, TOAD) para editar packages. Esta feature traz um editor de packages integrado ao DBQM.

## 2. Decisões de Design

| Decisão | Escolha |
|---------|---------|
| Escopo de bancos | Oracle exclusivo (packages são conceito Oracle) |
| Posição no menu | Ferramentas → Packages (entre DDL e Objetos) |
| Compilação | Executa `CREATE OR REPLACE PACKAGE [BODY]` diretamente no banco |
| Feedback de erros | Busca `ALL_ERRORS`, mostra inline com linha/coluna no editor |
| Criação | Opção "Em branco" (template) ou "Wizard" (assistente guiado) |
| Salvamento local | Exportar como `.sql` via botão Salvar |

## 3. Fluxo

### 3.1 Modal Inicial

Opções:
- **Editar package existente** → modal com conexão + nome do package
- **Criar novo package** → modal com conexão + nome + modo (branco/wizard)

### 3.2 Editar Existente

1. Seleciona conexão (dropdown, filtrado para Oracle)
2. Digita nome do package
3. Clica "Buscar" → Worker busca no banco
4. Se não encontrar: mensagem de erro no modal, usuário pode tentar outro nome (modal não fecha)
5. Se encontrar: carrega spec e body, abre o editor

### 3.3 Criar Novo

1. Seleciona conexão + digita nome
2. Escolhe modo:
   - **Em branco:** template com `CREATE OR REPLACE PACKAGE nome AS ... END nome;`
   - **Wizard:** pede nome de procedures/functions via modal sequencial, gera skeleton
3. Abre o editor com o código gerado

### 3.4 Tela do Editor

Layout:
```
Breadcrumb: Ferramentas / Packages / PKG_NOME (CONEXÃO)
┌─────────────────────────────────────────┐
│  [Spec]  [Body]       ← tabs           │
├─────────────────────────────────────────┤
│  TextArea editável (syntax highlight)   │
│  (conteúdo muda conforme tab ativo)     │
├─────────────────────────────────────────┤
│  Painel de erros (se houver):           │
│  ❌ 2 erros de compilação (PACKAGE BODY)│
│  Linha 15, Col 3: PLS-00103: ...        │
│  Linha 22, Col 5: PLS-00201: ...        │
├─────────────────────────────────────────┤
│  [C] Compilar Spec  [B] Compilar Body   │
│  [S] Salvar .sql                        │
└─────────────────────────────────────────┘
```

**Tabs Spec/Body:**
- Alternar com Tab ou clique
- Ao trocar, guarda o conteúdo atual do TextArea em memória
- Carrega o conteúdo do outro tab

**Compilar (C para Spec, B para Body):**
1. Pega o conteúdo atual do TextArea
2. Executa `CREATE OR REPLACE PACKAGE [BODY] ...` via Worker
3. Após execução, busca erros em `ALL_ERRORS`
4. Se sucesso: painel verde "✅ Spec/Body compilado com sucesso"
5. Se erros: painel vermelho com lista de erros (linha, coluna, mensagem)

**Salvar (S):**
- Exporta spec + body como arquivo `.sql` via `core.exporter.export_sql_file()`
- Mesmo padrão de export do resto da aplicação

**Atalhos:**
| Tecla | Ação |
|-------|------|
| C | Compilar Spec |
| B | Compilar Body |
| S | Salvar como .sql |
| Tab | Alternar Spec/Body (quando não em TextArea) |

## 4. Core (lógica de negócio)

Novo arquivo: `dbqm/core/package_editor.py`

### Funções

**`check_package_exists(db, pkg_name: str) -> bool`**
- Query: `SELECT COUNT(*) FROM ALL_OBJECTS WHERE OBJECT_NAME = :name AND OBJECT_TYPE = 'PACKAGE'`

**`fetch_package_source(db, pkg_name: str) -> tuple[str, str]`**
- Busca spec via `DBMS_METADATA.GET_DDL('PACKAGE', :name)` ou `ALL_SOURCE`
- Busca body via `DBMS_METADATA.GET_DDL('PACKAGE_BODY', :name)` ou `ALL_SOURCE`
- Retorna `(spec_sql, body_sql)`
- Se não encontrar: retorna `("", "")`

**`compile_package(db, sql: str) -> tuple[bool, str]`**
- Executa o SQL (CREATE OR REPLACE PACKAGE / PACKAGE BODY)
- Retorna `(success: bool, error_message: str)`
- Se exceção Oracle: retorna `(False, str(error))`

**`fetch_compilation_errors(db, pkg_name: str, obj_type: str) -> list[dict]`**
- Query: `SELECT LINE, POSITION, TEXT FROM ALL_ERRORS WHERE NAME = :name AND TYPE = :type ORDER BY SEQUENCE`
- `obj_type`: "PACKAGE" ou "PACKAGE BODY"
- Retorna lista de `{"line": int, "col": int, "message": str}`

**`generate_blank_template(pkg_name: str) -> tuple[str, str]`**
- Retorna `(spec_template, body_template)` com skeleton básico

**`generate_wizard_template(pkg_name: str, routines: list[dict]) -> tuple[str, str]`**
- `routines`: lista de `{"name": str, "type": "PROCEDURE"|"FUNCTION", "params": list[str], "return_type": str|None}`
- Gera spec e body com as assinaturas preenchidas

## 5. UI

### Novos arquivos
- `dbqm/ui/screens/package_editor.py` — tela do editor
- `dbqm/core/package_editor.py` — lógica Oracle

### Arquivos modificados
- `dbqm/ui/widgets/sidebar.py` — adicionar "Packages" na seção FERRAMENTAS
- `dbqm/ui/app.py` — adicionar routing para `package_editor` + binding `Binding("o", ...)`

### Modais (dentro de package_editor.py)
- `_PackageChoiceModal` — escolha Novo/Editar
- `_PackageSearchModal` — conexão + nome + buscar (para editar)
- `_PackageCreateModal` — conexão + nome + modo (para criar)
- `_WizardRoutineModal` — adicionar procedures/functions (para wizard)

### Screen: PackageEditorScreen

Widget `Vertical` com:
- Breadcrumb info (Static)
- Tab bar (Spec/Body) como Buttons
- TextArea para edição SQL
- Error/Success panel (Static, atualizado após compilação)
- ActionBar com C/B/S

Estado interno:
- `_spec_content: str` — conteúdo da spec
- `_body_content: str` — conteúdo do body
- `_active_tab: str` — "spec" ou "body"
- `_pkg_name: str`
- `_conn` — conexão ativa
- `_db` — conexão de banco aberta

Workers:
- `_fetch_package()` — busca spec/body do banco
- `_compile()` — compila e busca erros
- `_save_sql()` — exporta como .sql

## 6. Considerações

- A conexão de banco deve ser aberta uma vez e mantida durante a edição (mesmo padrão do object browser)
- Ao sair da tela (ESC/sidebar), fechar a conexão (`on_unmount`)
- Erros de compilação Oracle usam numeração de linha relativa ao `CREATE OR REPLACE`, que é a linha 1 do TextArea — não precisa de ajuste
- O TextArea do Textual suporta syntax highlighting para SQL
