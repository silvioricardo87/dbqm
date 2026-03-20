# DBQM UI Redesign — Textual TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the entire UI layer from Rich+InquirerPy (print-based) to Textual (fullscreen TUI) with sidebar navigation, theming, and modal dialogs.

**Architecture:** Fullscreen app with fixed sidebar (collapsible), breadcrumb, content area, action bar, and status bar. All DB operations run in Worker threads. Modal dialogs for params/confirmations. Two themes (GitHub Dark/Light).

**Tech Stack:** Python 3.12+, Textual 8.x, Rich (for legacy exports only), pytest + textual pilot for testing.

**Spec:** `docs/superpowers/specs/2026-03-20-ui-redesign-textual-design.md`

---

## File Map

### New Files (create)

| File | Responsibility |
|------|---------------|
| `dbqm/ui/app.py` | Main Textual App, routing, first-run detection |
| `dbqm/ui/theme.py` | GitHub Dark/Light theme definitions, CSS variables |
| `dbqm/ui/widgets/__init__.py` | Widget exports |
| `dbqm/ui/widgets/sidebar.py` | Collapsible sidebar with sections |
| `dbqm/ui/widgets/breadcrumb.py` | Clickable breadcrumb navigation |
| `dbqm/ui/widgets/result_table.py` | DataTable wrapper for QueryResult |
| `dbqm/ui/widgets/query_list.py` | ListView of queries as cards |
| `dbqm/ui/widgets/group_result.py` | Flat/pivoted comparison display |
| `dbqm/ui/widgets/sql_viewer.py` | Read-only SQL with syntax highlight |
| `dbqm/ui/widgets/status_bar.py` | Footer with connection status |
| `dbqm/ui/widgets/action_bar.py` | Contextual action buttons |
| `dbqm/ui/widgets/progress.py` | Progress indicator wrapper |
| `dbqm/ui/screens/__init__.py` | Screen exports |
| `dbqm/ui/screens/query_exec.py` | Execute saved query screen |
| `dbqm/ui/screens/query_manage.py` | Query CRUD screen |
| `dbqm/ui/screens/group_exec.py` | Execute group screen |
| `dbqm/ui/screens/group_manage.py` | Group CRUD screen |
| `dbqm/ui/screens/adhoc.py` | Ad-hoc SQL screen |
| `dbqm/ui/screens/ddl.py` | DDL extraction screen |
| `dbqm/ui/screens/browser_tables.py` | Table browser screen |
| `dbqm/ui/screens/browser_packages.py` | Package browser (Oracle) |
| `dbqm/ui/screens/browser_views.py` | View browser screen |
| `dbqm/ui/screens/browser_routines.py` | Routine browser (PG/MySQL) |
| `dbqm/ui/screens/history.py` | History screen |
| `dbqm/ui/screens/connections.py` | Connection CRUD screen |
| `dbqm/ui/screens/settings.py` | Settings screen (theme, audit) |
| `dbqm/ui/screens/config_port.py` | Export/Import config screen |
| `dbqm/ui/modals/__init__.py` | Modal exports |
| `dbqm/ui/modals/param_input.py` | Parameter input modal |
| `dbqm/ui/modals/confirm.py` | Confirmation dialog |
| `dbqm/ui/modals/export_picker.py` | Export format picker |
| `dbqm/ui/modals/text_input.py` | Generic text input modal |
| `dbqm/ui/modals/connection_form.py` | Connection form modal |
| `dbqm/ui/modals/column_maps.py` | DE-PARA mapping modal |
| `dbqm/ui/modals/help.py` | Help overlay with keybindings |
| `dbqm/ui/legacy/__init__.py` | Legacy module init |
| `dbqm/ui/legacy/display.py` | Rich renderables for PNG/TXT export |
| `tests/ui/__init__.py` | UI test package |
| `tests/ui/test_app.py` | App integration tests |
| `tests/ui/test_widgets.py` | Widget unit tests |
| `tests/ui/test_screens.py` | Screen tests |
| `tests/ui/test_modals.py` | Modal tests |

### Files to Modify

| File | Change |
|------|--------|
| `main.py` | Change `menu.main_menu()` → `DBQMApp().run()` |
| `requirements.txt` | Add `textual`, remove `InquirerPy` |
| `dbqm/models/settings.py` | Add `theme` field |

### Files to Remove (after migration complete)

| File | Replaced by |
|------|------------|
| `dbqm/ui/menu.py` | `app.py` + `sidebar.py` |
| `dbqm/ui/prompts.py` | Textual widgets |
| `dbqm/ui/helpers.py` | `modals/` + `widgets/` |
| `dbqm/ui/config_wizard.py` | `screens/connections.py` |
| `dbqm/ui/query_wizard.py` | `screens/query_manage.py` |
| `dbqm/ui/group_wizard.py` | `screens/group_manage.py` |
| `dbqm/ui/display.py` | `widgets/` + `legacy/display.py` |
| `dbqm/ui/flows/*.py` | `screens/*.py` |

---

## Phase 1: Foundation (App Shell + Theme + Core Widgets)

### Task 1: Setup dependencies and theme system

**Files:**
- Modify: `requirements.txt`
- Create: `dbqm/ui/theme.py`
- Modify: `dbqm/models/settings.py`
- Test: `tests/ui/test_theme.py`

- [ ] **Step 1: Update requirements.txt**

Add `textual` to `requirements.txt`. Do NOT remove `InquirerPy` yet (old UI still works during migration).

```
textual>=0.80
```

Run: `python -m pip install -r requirements.txt`

- [ ] **Step 2: Add theme field to settings model**

Read `dbqm/models/settings.py` and add a `theme: str = "github-dark"` field to the Settings dataclass/model. Ensure `load_settings()` and `save_settings()` handle it with backward-compatible defaults.

- [ ] **Step 3: Write theme test**

Create `tests/ui/__init__.py` (empty) and `tests/ui/test_theme.py`:

```python
"""Tests for theme system."""
from dbqm.ui.theme import GITHUB_DARK, GITHUB_LIGHT, get_theme

def test_github_dark_has_required_vars():
    theme = GITHUB_DARK
    assert theme.name == "github-dark"
    # Verify key design tokens exist
    assert theme.primary is not None
    assert theme.background is not None

def test_github_light_has_required_vars():
    theme = GITHUB_LIGHT
    assert theme.name == "github-light"
    assert theme.primary is not None
    assert theme.background is not None

def test_get_theme_returns_dark_by_default():
    theme = get_theme("github-dark")
    assert theme.name == "github-dark"

def test_get_theme_returns_light():
    theme = get_theme("github-light")
    assert theme.name == "github-light"

def test_get_theme_unknown_falls_back_to_dark():
    theme = get_theme("nonexistent")
    assert theme.name == "github-dark"
```

Run: `python -m pytest tests/ui/test_theme.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement theme.py**

Create `dbqm/ui/theme.py` with Textual `Theme` objects for GitHub Dark and GitHub Light. Use the color values from the spec (Section 3.5). Define a `get_theme(name: str) -> Theme` function that returns the matching theme or falls back to dark.

Reference Textual's `Theme` class: `from textual.theme import Theme`. Create themes using `Theme(name=..., primary=..., secondary=..., background=..., surface=..., ...)`.

- [ ] **Step 5: Run tests, verify pass**

Run: `python -m pytest tests/ui/test_theme.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add dbqm/ui/theme.py dbqm/models/settings.py requirements.txt tests/ui/
git commit -m "feat(ui): add theme system with GitHub Dark/Light themes"
```

---

### Task 2: Sidebar widget

**Files:**
- Create: `dbqm/ui/widgets/__init__.py`
- Create: `dbqm/ui/widgets/sidebar.py`
- Test: `tests/ui/test_widgets.py`

- [ ] **Step 1: Write sidebar test**

```python
"""Tests for sidebar widget."""
import pytest
from textual.app import App, ComposeResult

from dbqm.ui.widgets.sidebar import Sidebar, SidebarItemSelected

class SidebarTestApp(App):
    def compose(self) -> ComposeResult:
        yield Sidebar()

@pytest.mark.asyncio
async def test_sidebar_renders():
    app = SidebarTestApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        assert sidebar is not None

@pytest.mark.asyncio
async def test_sidebar_has_all_sections():
    app = SidebarTestApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        # Should have section labels for Consultas, Grupos, Ferramentas, Sistema
        text = sidebar.render()  # or check children
        # Verify menu items exist
        items = sidebar.query(".sidebar-item")
        assert len(items) >= 11  # All menu items

@pytest.mark.asyncio
async def test_sidebar_collapse_toggle():
    app = SidebarTestApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one(Sidebar)
        assert not sidebar.collapsed
        sidebar.toggle_collapse()
        assert sidebar.collapsed
        sidebar.toggle_collapse()
        assert not sidebar.collapsed
```

Run: `python -m pytest tests/ui/test_widgets.py -v`
Expected: FAIL

- [ ] **Step 2: Implement Sidebar widget**

Create `dbqm/ui/widgets/__init__.py` and `dbqm/ui/widgets/sidebar.py`.

The Sidebar is a `Vertical` container with:
- Section labels (`Static` with uppercase text, dim color)
- Menu items (`Static` or `Button` with icon + text)
- Separators (`Rule` or `Static` with horizontal line)
- A `collapsed: reactive[bool]` property that toggles between full (width: 24) and mini (width: 5) mode
- A `toggle_collapse()` method
- CSS classes: `.sidebar`, `.sidebar-item`, `.sidebar-item--active`, `.sidebar--collapsed`
- Posts `SidebarItemSelected(action: str)` message when an item is clicked/selected

Menu items (from spec Section 3.3):
```python
MENU_ITEMS = [
    ("CONSULTAS", [
        ("exec_query", "🔍", "Executar"),
        ("adhoc_sql", "⌨", "SQL avulso"),
        ("config_query", "📝", "Gerenciar"),
    ]),
    ("GRUPOS", [
        ("exec_group", "📊", "Executar"),
        ("config_group", "📁", "Gerenciar"),
    ]),
    ("FERRAMENTAS", [
        ("extract_ddl", "🏗", "DDL"),
        ("browse", "🗂", "Objetos"),
        ("history", "📜", "Historico"),
    ]),
    ("SISTEMA", [
        ("config_conn", "🔌", "Conexoes"),
        ("portability", "📦", "Exportar"),
        ("settings", "⚙", "Config"),
        ("exit", "🚪", "Sair"),
    ]),
]
```

When collapsed, only show the icon. Use Textual CSS to handle the two states:

```css
Sidebar {
    width: 24;
    dock: left;
    background: $surface;
    border-right: solid $primary-darken-3;
}
Sidebar.collapsed {
    width: 5;
}
Sidebar.collapsed .sidebar-label { display: none; }
Sidebar.collapsed .sidebar-item-text { display: none; }
```

- [ ] **Step 3: Run tests, verify pass**

Run: `python -m pytest tests/ui/test_widgets.py -v`

- [ ] **Step 4: Commit**

```bash
git add dbqm/ui/widgets/
git commit -m "feat(ui): add collapsible sidebar widget"
```

---

### Task 3: Breadcrumb, StatusBar, ActionBar widgets

**Files:**
- Create: `dbqm/ui/widgets/breadcrumb.py`
- Create: `dbqm/ui/widgets/status_bar.py`
- Create: `dbqm/ui/widgets/action_bar.py`
- Update: `tests/ui/test_widgets.py`

- [ ] **Step 1: Write tests for all three widgets**

Add to `tests/ui/test_widgets.py`:

Breadcrumb tests:
- `test_breadcrumb_renders_path()` — set path to `["Consultas", "Executar", "saldo_cliente"]`, verify all segments render
- `test_breadcrumb_click_navigates_back()` — click on a non-terminal segment, verify `BreadcrumbNavigated` message is posted

StatusBar tests:
- `test_status_bar_shows_connection()` — set connection to "ORACLE-PRD", verify it renders
- `test_status_bar_shows_counts()` — set counts, verify display

ActionBar tests:
- `test_action_bar_renders_actions()` — add actions, verify buttons appear
- `test_action_bar_click_emits_message()` — click action, verify `ActionSelected` message

- [ ] **Step 2: Implement Breadcrumb**

`dbqm/ui/widgets/breadcrumb.py`:
- `Horizontal` container with `Static` labels
- `path: reactive[list[str]]` — list of breadcrumb segments
- Last segment rendered in bold/bright, others in primary color
- Separator: ` / ` in dim
- Click on non-terminal segment posts `BreadcrumbNavigated(index: int)`
- Method: `set_path(segments: list[str])`

- [ ] **Step 3: Implement StatusBar**

`dbqm/ui/widgets/status_bar.py`:
- Extends `Static` or `Horizontal` container (docked bottom, height: 1)
- Left side: connection indicator (● green when connected, ● dim when not)
- Right side: counters (N queries, N connections, N groups)
- Methods: `set_connection(name: str | None)`, `update_counts()`
- Loads counts from `models/` on `update_counts()`

- [ ] **Step 4: Implement ActionBar**

`dbqm/ui/widgets/action_bar.py`:
- `Horizontal` container (docked bottom above StatusBar, height: auto)
- Accepts a list of `Action(label: str, key: str, action_id: str)` tuples
- Renders as: `[key] label  [key] label  ...`
- Click or keyboard shortcut posts `ActionSelected(action_id: str)`
- Method: `set_actions(actions: list[Action])`

- [ ] **Step 5: Run tests, verify pass**

Run: `python -m pytest tests/ui/test_widgets.py -v`

- [ ] **Step 6: Commit**

```bash
git add dbqm/ui/widgets/breadcrumb.py dbqm/ui/widgets/status_bar.py dbqm/ui/widgets/action_bar.py tests/ui/test_widgets.py
git commit -m "feat(ui): add breadcrumb, status bar, and action bar widgets"
```

---

### Task 4: App shell with routing

**Files:**
- Create: `dbqm/ui/app.py`
- Create: `dbqm/ui/screens/__init__.py`
- Test: `tests/ui/test_app.py`

- [ ] **Step 1: Write app test**

```python
"""Tests for main app."""
import pytest
from dbqm.ui.app import DBQMApp

@pytest.mark.asyncio
async def test_app_starts_and_shows_sidebar():
    app = DBQMApp()
    async with app.run_test() as pilot:
        from dbqm.ui.widgets.sidebar import Sidebar
        sidebar = app.query_one(Sidebar)
        assert sidebar is not None

@pytest.mark.asyncio
async def test_app_has_status_bar():
    app = DBQMApp()
    async with app.run_test() as pilot:
        from dbqm.ui.widgets.status_bar import StatusBar
        bar = app.query_one(StatusBar)
        assert bar is not None

@pytest.mark.asyncio
async def test_ctrl_b_toggles_sidebar():
    app = DBQMApp()
    async with app.run_test() as pilot:
        from dbqm.ui.widgets.sidebar import Sidebar
        sidebar = app.query_one(Sidebar)
        assert not sidebar.collapsed
        await pilot.press("ctrl+b")
        assert sidebar.collapsed

@pytest.mark.asyncio
async def test_ctrl_q_exits():
    app = DBQMApp()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+q")
        # App should be exiting
```

Run: `python -m pytest tests/ui/test_app.py -v`
Expected: FAIL

- [ ] **Step 2: Implement app.py**

Create `dbqm/ui/app.py` — the main `DBQMApp(App)`:

```python
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Static

from dbqm.ui.theme import GITHUB_DARK, GITHUB_LIGHT, get_theme
from dbqm.ui.widgets.sidebar import Sidebar, SidebarItemSelected
from dbqm.ui.widgets.breadcrumb import Breadcrumb
from dbqm.ui.widgets.status_bar import StatusBar
from dbqm.models.settings import load_settings
```

Layout compose:
```
Header (title="DB Query Manager v1.0")
Horizontal:
  Sidebar
  Vertical#content:
    Breadcrumb
    ContentSwitcher or Container#screen-area (fr 1)
    ActionBar (initially empty)
StatusBar
```

Bindings:
- `Binding("ctrl+b", "toggle_sidebar", "Toggle sidebar")`
- `Binding("ctrl+q", "quit", "Quit")`
- `Binding("escape", "go_back", "Back")`
- `Binding("question_mark", "show_help", "Help")`

On mount:
1. Load settings, apply theme via `self.theme = settings.theme`
2. Register both themes: `self.register_theme(GITHUB_DARK)` and `GITHUB_LIGHT`
3. Detect first-run (no connections) → show welcome message
4. Update StatusBar counts

Handle `SidebarItemSelected`:
- Map action string to screen loading (initially just show a placeholder)
- Update breadcrumb
- If "exit" → `self.exit()`

Create `dbqm/ui/screens/__init__.py` (empty for now).

- [ ] **Step 3: Run tests, verify pass**

Run: `python -m pytest tests/ui/test_app.py -v`

- [ ] **Step 4: Wire up main.py**

Modify `main.py`: add a branch — if `--tui` flag or no args and new UI enabled, run `DBQMApp().run()`. For now, keep the old menu as fallback. The old `main_menu()` should still work for testing during migration.

```python
# In main.py, after argument parsing:
if not sys.argv[1:]:  # No CLI args → interactive mode
    from dbqm.ui.app import DBQMApp
    DBQMApp().run()
```

- [ ] **Step 5: Manual smoke test**

Run: `python -m dbqm` (or however the app starts)
Expected: Fullscreen app with sidebar, header, status bar. No content yet.

- [ ] **Step 6: Commit**

```bash
git add dbqm/ui/app.py dbqm/ui/screens/__init__.py main.py tests/ui/test_app.py
git commit -m "feat(ui): add main Textual app shell with sidebar routing"
```

---

## Phase 2: Core Data Widgets + Modals

### Task 5: ResultTable widget

**Files:**
- Create: `dbqm/ui/widgets/result_table.py`
- Update: `tests/ui/test_widgets.py`

- [ ] **Step 1: Write tests**

Test that `ResultTable` can:
- Accept a `QueryResult` and render columns/rows
- Handle empty result (no rows)
- Handle pagination (100 rows per page, next/prev)
- Toggle vertical view mode

- [ ] **Step 2: Implement ResultTable**

Extends or wraps `DataTable`. Key features:
- `load_result(result: QueryResult)` — clears table, adds columns, adds rows
- `page_size: int = 100`, `current_page: int = 0`
- Pagination methods: `next_page()`, `prev_page()`
- `toggle_vertical()` — switches between table and vertical display (vertical = `RichLog` or `Static` with column-per-line format)
- Column width adaptation based on data

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(ui): add ResultTable widget with pagination and vertical view"
```

---

### Task 6: ParamModal

**Files:**
- Create: `dbqm/ui/modals/__init__.py`
- Create: `dbqm/ui/modals/param_input.py`
- Test: `tests/ui/test_modals.py`

- [ ] **Step 1: Write tests**

```python
@pytest.mark.asyncio
async def test_param_modal_shows_fields():
    # Modal should show one Input per parameter
    params = [
        {"name": "apolice", "description": "Numero da apolice", "default": ""},
        {"name": "dt_ref", "description": "Data referencia", "default": "2024-01-15"},
    ]
    # Push modal, verify 2 Input widgets appear

@pytest.mark.asyncio
async def test_param_modal_returns_values():
    # Fill in values, press Enter, verify dict returned

@pytest.mark.asyncio
async def test_param_modal_esc_cancels():
    # Press ESC, verify None returned
```

- [ ] **Step 2: Implement ParamModal**

`ModalScreen` with:
- Title: query name
- Subtitle: query description
- One `Input` per param (label shows name + description, placeholder shows default)
- Pre-fill with last used values or defaults
- Focus on first empty input
- Enter on last field or click "Executar" → dismiss with `dict[str, str]`
- ESC → dismiss with `None`

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(ui): add parameter input modal"
```

---

### Task 7: ConfirmModal, TextInputModal, ExportPickerModal

**Files:**
- Create: `dbqm/ui/modals/confirm.py`
- Create: `dbqm/ui/modals/text_input.py`
- Create: `dbqm/ui/modals/export_picker.py`
- Update: `tests/ui/test_modals.py`

- [ ] **Step 1: Write tests for each modal**

ConfirmModal: show message, Y/N buttons, ESC = cancel
TextInputModal: show prompt, single Input, Enter = submit, ESC = cancel
ExportPickerModal: show format options (CSV/JSON/TXT/PNG), select one

- [ ] **Step 2: Implement all three modals**

Each is a simple `ModalScreen`:
- `ConfirmModal(message: str)` → dismisses with `True`/`False`
- `TextInputModal(title: str, default: str = "")` → dismisses with `str` or `None`
- `ExportPickerModal(include_png: bool = False)` → dismisses with format string or `None`

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(ui): add confirm, text input, and export picker modals"
```

---

### Task 8: Progress widget

**Files:**
- Create: `dbqm/ui/widgets/progress.py`
- Update: `tests/ui/test_widgets.py`

- [ ] **Step 1: Write test**

Test that progress widget shows/hides, updates message.

- [ ] **Step 2: Implement Progress**

Simple wrapper: `Vertical` with `Static` message + `ProgressBar` (or `LoadingIndicator`). Methods: `start(message)`, `stop()`, `update(message)`. Hidden by default, shown when `start()` called.

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(ui): add progress indicator widget"
```

---

## Phase 3: Query Execution Screen (First Complete Flow)

### Task 9: QueryList widget

**Files:**
- Create: `dbqm/ui/widgets/query_list.py`
- Update: `tests/ui/test_widgets.py`

- [ ] **Step 1: Write tests**

Test that QueryList:
- Loads queries from `load_queries()` and displays them
- Shows favorite star, name, description, connection badge, table
- Filters by folder
- Sorts favorites first
- Emits `QuerySelected(query_name: str)` on selection

- [ ] **Step 2: Implement QueryList**

`ListView` based widget. Each item is a `ListItem` with a `Horizontal` layout:
- Star icon (★ yellow if favorite, ☆ dim otherwise)
- Query name (bold)
- Description (dim, truncated)
- Connection badge (right-aligned, styled as tag)
- Table name (dim)

Has a `load_queries(queries: list, folder_filter: str | None = None)` method.

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(ui): add query list widget"
```

---

### Task 10: Query Execution screen

**Files:**
- Create: `dbqm/ui/screens/query_exec.py`
- Test: `tests/ui/test_screens.py`

This is the **first complete flow** — selecting a query, entering params, seeing results.

- [ ] **Step 1: Write tests**

```python
@pytest.mark.asyncio
async def test_query_exec_screen_shows_query_list(tmp_config_dir):
    # Setup: create test queries in config
    # Verify QueryList renders with those queries

@pytest.mark.asyncio
async def test_query_exec_screen_shows_folder_tabs(tmp_config_dir):
    # Setup: create queries with folders
    # Verify tabs appear for each folder
```

- [ ] **Step 2: Implement QueryExecScreen**

Screen layout:
```
Vertical:
  TabbedContent (folder tabs — only if folders exist):
    TabPane "Todas (N)": QueryList
    TabPane "Financeiro (N)": QueryList
    ...
  # OR just QueryList if no folders
```

On `QuerySelected`:
1. Find query in models
2. Find connection
3. If query has params → push `ParamModal`
4. On modal result → run query in Worker thread
5. Show `Progress` during execution
6. On result → populate `ResultTable`, update `ActionBar`
7. Update breadcrumb: `["Consultas", "Executar", query.name]`

ActionBar actions (when showing results):
- V: toggle vertical → `result_table.toggle_vertical()`
- E: export → push `ExportPickerModal`, then call `core.exporter`
- R: reexecute → push `ParamModal` with current values

Worker pattern for DB calls:
```python
@work(thread=True)
def _execute_query(self, query, conn, params):
    from dbqm.core.query_engine import execute_query
    result = execute_query(query, conn, params)
    self.call_from_thread(self._on_result, result)
```

- [ ] **Step 3: Wire screen into app.py routing**

In `app.py`, handle `SidebarItemSelected` for `exec_query`:
```python
if action == "exec_query":
    self.load_screen(QueryExecScreen())
```

- [ ] **Step 4: Run tests, manual smoke test**

Run: `python -m pytest tests/ui/ -v`
Then: `python -m dbqm` — navigate to Executar, select a query, enter params, see results.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(ui): add query execution screen with full flow"
```

---

## Phase 4: Management Screens

### Task 11: Connection management screen

**Files:**
- Create: `dbqm/ui/modals/connection_form.py`
- Create: `dbqm/ui/screens/connections.py`
- Update: `tests/ui/test_screens.py`

- [ ] **Step 1: Write tests**

Test that:
- ConnectionsScreen shows table of existing connections
- "New" action opens ConnectionFormModal
- ConnectionFormModal shows correct fields per db_type (Oracle TNS, Oracle Direct, SQL Server, PostgreSQL, MySQL)
- Test connection works (mock `test_connection`)
- Edit, rename, remove work

- [ ] **Step 2: Implement ConnectionFormModal**

A `ModalScreen` with:
- Name input
- DB type selector (Select widget: Oracle, SQL Server, PostgreSQL, MySQL)
- Dynamic fields based on db_type:
  - Oracle TNS: tns_path, tns_name, user, password
  - Oracle Direct: host, port, service_name, user, password
  - SQL Server/PostgreSQL/MySQL: host, port, database, user, password
- Password field uses `Input(password=True)`
- Test button (runs `test_connection` in Worker)
- Save / Cancel buttons
- For edit mode: pre-fill all fields from existing connection

- [ ] **Step 3: Implement ConnectionsScreen**

Screen layout:
- `DataTable` with columns: #, Name, Type, Target
- ActionBar: New, Test, Edit, Rename, Remove, Back

Actions:
- New → push `ConnectionFormModal` → save connection
- Test → run `test_connection` in Worker, show result
- Edit → push `ConnectionFormModal` in edit mode
- Rename → push `TextInputModal`
- Remove → push `ConfirmModal` → delete

- [ ] **Step 4: Wire into app routing, test, commit**

```bash
git commit -m "feat(ui): add connection management screen"
```

---

### Task 12: Query management screen

**Files:**
- Create: `dbqm/ui/modals/column_maps.py`
- Create: `dbqm/ui/screens/query_manage.py`
- Update: `tests/ui/test_screens.py`

- [ ] **Step 1: Write tests**

Test that:
- ColumnMapsModal shows column selector and mapping table
- QueryManageScreen renders DataTable with queries
- New query flow (paste mode) works via sequential modals
- View SQL displays query SQL in SqlViewer
- Rename, favorite toggle, folder move work
- DE-PARA modal allows adding/removing mappings

- [ ] **Step 2: Implement ColumnMapsModal**

Modal for configuring DE-PARA value mappings. Shows:
- Column selector
- Current mappings as a table (original → display)
- Add mapping: two inputs (original, display)
- Remove mapping button

- [ ] **Step 3: Implement QueryManageScreen**

Screen layout:
- `DataTable` with columns: #, Folder, Name, Description, Connection, Table, Params
- Sorted by folder then name

ActionBar: New, View SQL, Edit, DE-PARA, Rename, Favorite, Folder, Duplicate, Remove, Back

Actions:
- New → "Como configurar?" dialog → Paste mode or Wizard mode (both as sequential modals)
- View SQL → show `SqlViewer` widget with query SQL in content area
- Edit → series of modals for each field (description, connection, SQL, table, params)
- DE-PARA → push `ColumnMapsModal`
- Rename → `TextInputModal`
- Favorite → toggle, refresh table
- Folder → folder selection modal + new folder option
- Duplicate → `TextInputModal` for new name, optional connection change
- Remove → `ConfirmModal`

Paste mode flow (via modals):
1. TextArea modal for SQL input
2. Show parsed analysis
3. Name, description, connection inputs
4. Parameter detection and configuration
5. Test/Save confirmation

Wizard mode flow (via modals):
1. Name, description inputs
2. Connection selection
3. Table input
4. Column selection (fetch from DB or manual)
5. WHERE conditions
6. Parameter configuration
7. ORDER BY
8. Test/Save

- [ ] **Step 4: Create SqlViewer widget**

Create `dbqm/ui/widgets/sql_viewer.py` — a `Static` widget that renders SQL with Rich `Syntax` highlighting. Read-only display.

- [ ] **Step 5: Run tests, verify pass**

Run: `python -m pytest tests/ui/test_screens.py -v -k query_manage`

- [ ] **Step 6: Wire, commit**

```bash
git commit -m "feat(ui): add query management screen with create/edit/DE-PARA"
```

---

### Task 13: Group management screen

**Files:**
- Create: `dbqm/ui/screens/group_manage.py`
- Update: `tests/ui/test_screens.py`

- [ ] **Step 1: Write tests**

Test that:
- GroupManageScreen renders DataTable with groups
- Create wizard multi-step flow works
- Edit, rename, folder move work

- [ ] **Step 2: Implement GroupManageScreen**

Similar pattern to QueryManageScreen:
- `DataTable` with columns: Name, Queries, Description, Folder
- ActionBar: New, Edit, Rename, Folder, Remove, Back

Create wizard (multi-step modals):
1. Name, description
2. Select queries (minimum 2, checkbox selection)
3. Shared parameter detection and mapping
4. Join key selection
5. Compare column selection with mapping for mismatched names
6. Normalization rules
7. Validation rules

Edit: series of modals per field.

- [ ] **Step 3: Run tests, verify pass**

Run: `python -m pytest tests/ui/test_screens.py -v -k group_manage`

- [ ] **Step 4: Wire, commit**

```bash
git commit -m "feat(ui): add group management screen"
```

---

## Phase 5: Group Execution + Comparison Display

### Task 14: GroupResult widget

**Files:**
- Create: `dbqm/ui/widgets/group_result.py`
- Update: `tests/ui/test_widgets.py`

- [ ] **Step 1: Write tests**

Test that GroupResult widget:
- Loads a `GroupResult` and renders flat mode (one table per column)
- Toggles to pivoted mode (one table per key)
- Filters by status (DIFF, ABSENT)
- Shows summary counts correctly

- [ ] **Step 2: Implement GroupResult widget**

Two display modes controlled by a `mode: reactive[str]` ("flat" or "pivoted"):

**Flat mode:** One `DataTable` per compare column.
- Columns: key | query1_value | query2_value | ... | Status
- Status cells colored: OK (green), DIFF (yellow), ABSENT (red), OK* (green)
- Differing values highlighted in red

**Pivoted mode:** One `DataTable` per join key value.
- Columns: Consulta | col1 | col2 | ... | status
- One row per query
- Result row at bottom with per-column status

**Summary section:** Static text with counts per column (iguais, diferentes, ausentes, normalizados).

Methods: `load_result(group_result: GroupResult)`, `toggle_mode()`, `filter_status(statuses: set[str])`

- [ ] **Step 3: Run tests, verify pass**

Run: `python -m pytest tests/ui/test_widgets.py -v -k group_result`

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(ui): add group result widget with flat/pivoted modes"
```

---

### Task 15: Group execution screen

**Files:**
- Create: `dbqm/ui/screens/group_exec.py`
- Update: `tests/ui/test_screens.py`

- [ ] **Step 1: Write tests**

Test that GroupExecScreen:
- Shows group list
- Folder tabs render when groups have folders
- Selection triggers ParamModal

- [ ] **Step 2: Implement GroupExecScreen**

Flow:
1. Show group list (with folder tabs if applicable)
2. Select group → `ParamModal` for shared params
3. Execute all queries with Progress (show per-query progress)
4. Show `GroupResult` widget
5. ActionBar: Flat/Pivoted, Filter, Export, HTML Report, View Individual, Reexecute, Back

Worker runs all queries sequentially, posting progress updates.

"View Individual" → push a sub-screen with `ResultTable` for the selected query's raw result + SQL viewer.

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Wire, commit**

```bash
git commit -m "feat(ui): add group execution screen with comparison display"
```

---

## Phase 6: Tool Screens

### Task 16: Ad-hoc SQL screen

**Files:**
- Create: `dbqm/ui/screens/adhoc.py`

- [ ] **Step 1: Write tests**

Test that AdhocScreen:
- Renders TextArea and connection selector
- SELECT execution shows ResultTable
- DML execution shows affected rows and commit/rollback dialog

- [ ] **Step 2: Implement AdhocScreen**

Layout:
- Connection selector (Select widget at top)
- `TextArea` for SQL input (syntax highlighting)
- Action buttons: Execute, Generate SQL, Save as Query

Flow:
1. User types/pastes SQL in TextArea
2. Selects connection
3. Click Execute:
   - Classify SQL (SELECT/DML)
   - Detect params → `ParamModal` if needed
   - SELECT → run in Worker, show `ResultTable`
   - DML → run in Worker, show affected rows, `ConfirmModal` for COMMIT/ROLLBACK
4. Generate SQL → substitute params, show in viewer, option to export as .sql
5. Save as Query → `TextInputModal` for name, then save via models

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Wire, commit**

```bash
git commit -m "feat(ui): add ad-hoc SQL screen"
```

---

### Task 17: DDL extraction screen

**Files:**
- Create: `dbqm/ui/screens/ddl.py`

- [ ] **Step 1: Write tests**

Test that DDLScreen renders connection selector, object input, and progress bar.

- [ ] **Step 2: Implement DDLScreen**

Read current `flows/ddl_flow.py` and translate to Textual screen.

Layout:
- Connection selector
- Object name input
- Progress bar during extraction
- `SqlViewer` to show extracted DDL
- Option to extract dependencies
- Export button

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Wire, commit**

```bash
git commit -m "feat(ui): add DDL extraction screen"
```

---

### Task 18: Object browser screens

**Files:**
- Create: `dbqm/ui/screens/browser_tables.py`
- Create: `dbqm/ui/screens/browser_packages.py`
- Create: `dbqm/ui/screens/browser_views.py`
- Create: `dbqm/ui/screens/browser_routines.py`

- [ ] **Step 1: Write tests**

Test that each browser screen renders correctly:
- BrowserTablesScreen shows object list with filter, structure table
- BrowserPackagesScreen shows routine list
- BrowserViewsScreen shows SQL definition
- BrowserRoutinesScreen shows routine info

- [ ] **Step 2: Implement BrowserTablesScreen**

Flow:
1. Connection selector
2. Object type selector (Table/View/Package/Routine — varies by db_type)
3. Filter input + object list
4. Select table → show structure (DataTable with columns info, FK table, index table)
5. Actions: Query data (paginated ResultTable), Export structure

- [ ] **Step 3: Implement BrowserPackagesScreen (Oracle)**

Flow:
1. Package list with filter
2. Select package → show routines table
3. Actions: Execute routine (ParamModal for IN params, Worker, commit/rollback), View spec, View body, Export

- [ ] **Step 4: Implement BrowserViewsScreen**

1. View list with filter
2. Select view → show SQL definition (SqlViewer)
3. Actions: Query data (paginated), Export definition

- [ ] **Step 5: Implement BrowserRoutinesScreen (PG/MySQL)**

1. Routine list with filter
2. Select → show type, return type, source code

- [ ] **Step 6: Run tests, verify pass**

- [ ] **Step 7: Wire all into sidebar "Objetos", commit**

The sidebar "Objetos" action should first ask for connection, then object type, then route to the appropriate browser screen.

```bash
git commit -m "feat(ui): add object browser screens (tables, packages, views, routines)"
```

---

### Task 19: History screen

**Files:**
- Create: `dbqm/ui/screens/history.py`

- [ ] **Step 1: Write tests**

Test that HistoryScreen renders DataTable with history entries and detail view works.

- [ ] **Step 2: Implement HistoryScreen**

- `DataTable` with columns: #, Date/Time, Type, Name, Connection, Result, Time
- Load from `core.history.load_history()`, show last 50
- Select entry → show details in a panel/modal (params, row count, error, etc.)
- Actions: View Details, Clear History (with ConfirmModal)

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Wire, commit**

```bash
git commit -m "feat(ui): add history screen"
```

---

## Phase 7: Settings + Config + Cleanup

### Task 20: Settings screen

**Files:**
- Create: `dbqm/ui/screens/settings.py`

- [ ] **Step 1: Write tests**

Test that SettingsScreen renders theme selector and audit toggle, and changes persist.

- [ ] **Step 2: Implement SettingsScreen**

Layout:
- Theme selector: `Select` widget with "GitHub Dark" / "GitHub Light"
  - On change → `self.app.theme = selected_theme`, save to settings
- Audit log toggle: `Switch` widget
  - On change → save to settings

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Wire, commit**

```bash
git commit -m "feat(ui): add settings screen with theme selector"
```

---

### Task 21: Config portability screen

**Files:**
- Create: `dbqm/ui/screens/config_port.py`

- [ ] **Step 1: Write tests**

Test that ConfigPortScreen handles export (checkbox selection) and import (file path, password) flows.

- [ ] **Step 2: Implement ConfigPortScreen**

Translate `flows/config_flow.py`:
- Export: checkbox selection of connections/queries/groups → password input → create .dbqm bundle
- Import: file path input → password → show what will be imported → confirm

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Wire, commit**

```bash
git commit -m "feat(ui): add config export/import screen"
```

---

### Task 22: Legacy display module + export functions

**Files:**
- Create: `dbqm/ui/legacy/__init__.py`
- Create: `dbqm/ui/legacy/display.py`

- [ ] **Step 1: Extract export-only functions from display.py**

Copy from `dbqm/ui/display.py` to `dbqm/ui/legacy/display.py` ONLY the functions needed for PNG/TXT export:
- `build_query_renderables()`
- `build_individual_renderables()`
- `_build_params_table()`
- Any helper functions these depend on

These use Rich `Table`, `Panel`, `Syntax` etc. to build renderables for the screenshot exporter.

- [ ] **Step 2: Update import paths in exporter**

Check `dbqm/core/exporter.py` and any screens that call export functions — update imports to use `dbqm.ui.legacy.display` where needed.

- [ ] **Step 3: Test exports still work**

Run: `python -m pytest tests/core/test_exporter.py -v`

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(ui): extract legacy display functions for exports"
```

---

### Task 23: Remove old UI + cleanup

**Files:**
- Remove: `dbqm/ui/menu.py`
- Remove: `dbqm/ui/prompts.py`
- Remove: `dbqm/ui/helpers.py`
- Remove: `dbqm/ui/display.py`
- Remove: `dbqm/ui/config_wizard.py`
- Remove: `dbqm/ui/query_wizard.py`
- Remove: `dbqm/ui/group_wizard.py`
- Remove: `dbqm/ui/flows/` (entire directory)
- Modify: `requirements.txt` (remove InquirerPy)
- Modify: `main.py` (remove old menu import/fallback)

- [ ] **Step 1: Verify all features work in new UI**

Run through every flow manually:
1. Execute saved query (with params, pagination, vertical, export)
2. Ad-hoc SQL (SELECT + DML with commit/rollback)
3. Manage queries (create paste mode, wizard mode, edit, DE-PARA, rename, favorite, folder, duplicate, remove)
4. Execute group (flat, pivoted, filter, view individual, export, HTML)
5. Manage groups (create, edit, folder)
6. DDL extraction
7. Object browser (tables, packages/views per db_type)
8. History (view, details, clear)
9. Connections (new, test, edit, rename, remove)
10. Settings (theme toggle, audit toggle)
11. Export/Import config
12. First-run (no connections)
13. Sidebar collapse/expand
14. All keyboard shortcuts

- [ ] **Step 2: Remove old files**

Delete all old UI files listed above.

- [ ] **Step 3: Remove InquirerPy from requirements**

Edit `requirements.txt` — remove `InquirerPy>=0.3.4`.

- [ ] **Step 4: Clean up main.py**

Remove any fallback to old menu. Only launch `DBQMApp().run()`.

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: All existing tests pass (core/ and models/ tests should be unaffected). UI tests all pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(ui): remove old Rich+InquirerPy UI layer

Complete migration to Textual TUI. All screens and flows
reimplemented with fullscreen layout, sidebar navigation,
modal dialogs, and theme support."
```

---

### Task 24: Search/filter, help screen, worker cancellation, app.suspend

**Files:**
- Update: `dbqm/ui/widgets/query_list.py`
- Update: `dbqm/ui/app.py`
- Update: screens that use Workers

- [ ] **Step 1: Add text search/filter to QueryList and other list widgets**

Implement the `/` keybinding for lists. When pressed, show an `Input` widget at the top of the list that filters items as the user types. ESC dismisses the filter. Apply the same pattern to group lists and object lists in browser screens.

- [ ] **Step 2: Implement help overlay (`?` key)**

Create a help overlay (or `ModalScreen`) that shows all keybindings in a formatted table. Triggered by `?` globally. Content:
- All keybindings from spec Section 3.6
- Context-sensitive: show current screen's specific shortcuts

- [ ] **Step 3: Implement Worker cancellation via ESC**

In all screens that run `@work` threads (query execution, group execution, DDL extraction):
- Track the current `Worker` instance
- On ESC during execution: call `worker.cancel()` and hide progress
- Show "Operacao cancelada" message

- [ ] **Step 4: Implement app.suspend() for file opening**

In all screens that export files and offer to open them:
- Use `self.app.suspend()` context manager before calling `os.startfile()` / `subprocess.run()`
- After the external process, the TUI resumes automatically
- If suspension is not reliable on the platform, fall back to just showing the file path

- [ ] **Step 5: Test all features, commit**

```bash
git commit -m "feat(ui): add search filter, help screen, worker cancel, file open"
```

---

## Phase 8: Polish + Final Testing

### Task 25: End-to-end testing and polish

- [ ] **Step 1: Run app with real database**

Test with actual Oracle/PostgreSQL/MySQL connections if available. Verify:
- Query execution returns correct data
- Group comparisons work
- DDL extraction works
- Object browser connects and lists objects

- [ ] **Step 2: Test both themes**

Switch between GitHub Dark and GitHub Light in Settings. Verify all screens look correct in both themes.

- [ ] **Step 3: Test edge cases**

- Very wide result sets (many columns)
- Very long query names/descriptions
- Empty states (no queries, no groups, no history)
- Query execution errors
- Connection failures
- Large result sets (1000+ rows, pagination)

- [ ] **Step 4: Fix any visual issues found**

Adjust CSS, widget sizing, or layout as needed.

- [ ] **Step 5: Final commit**

```bash
git commit -m "polish(ui): fix visual issues and edge cases"
```
