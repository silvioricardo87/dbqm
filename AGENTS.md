# AGENTS.md — Instructions for AI Agents

> This is the **single source of truth** for AI agents working on dbqm.
> `CLAUDE.md` is a thin pointer to this file. These instructions OVERRIDE any
> default behavior — follow them exactly.

## Project Overview

**dbqm** (Database Query Manager) — Fullscreen TUI tool for managing and
executing SQL queries across **Oracle, SQL Server, PostgreSQL, and MySQL**.
Built with **Python + Textual**. Ships a non-interactive **CLI** for scripted
use (evidence collection, CI, ad-hoc execution).

- Entry point (console script): `dbqm.main:main` (declared in `pyproject.toml`)
- Module entry: `python -m dbqm` (`dbqm/__main__.py`) and `python -m dbqm <cmd>` for the CLI
- Version: `dbqm/_version.py` (read dynamically by `pyproject.toml` via `tool.setuptools.dynamic`)
- Python: **>= 3.10**
- Config directory: `~/.dbqm/` (overridable with `DBQM_HOME`)
- PyPI: https://pypi.org/project/dbqm/
- Repo: https://github.com/silvioricardo87/dbqm

## Dependencies

Core (always installed): `rich`, `textual`, `sqlparse`, `cryptography`, `PyMySQL`.

Database drivers are **conditionally installed** — no prebuilt wheels exist for
`oracledb` / `psycopg[binary]` / `pymssql` on **win-arm64**, so they are skipped
there (marker `sys_platform != 'win32' or platform_machine != 'ARM64'`) to keep
`pip install dbqm` working. On Windows ARM, use Python AMD64 under x64 emulation.

Opt-in extras: `oracle`, `postgres`, `sqlserver`, and `dev` (pytest + pytest-asyncio).
`requirements.txt` is intentionally empty — dependencies live in `pyproject.toml`.

## Architecture

```
dbqm/
├── main.py            # App bootstrap (console-script target: dbqm.main:main)
├── __main__.py        # `python -m dbqm` — routes to CLI or TUI
├── cli.py             # Non-interactive CLI (sql, run, group, list, history, ...)
├── _version.py        # __version__ (SemVer; read by pyproject.toml)
├── design/            # Design tokens (colors, contrast floors); imports nothing from dbqm
│   └── tokens.py       # TOKENS_CLARO / TOKENS_ESCURO / TEMAS, one source for TUI + CLI + HTML report
├── core/              # Business logic (no UI imports)
│   ├── db_manager.py          # Connection dispatcher for all 4 DBs; NLS_LANG=.AL32UTF8; Oracle thick mode
│   ├── query_engine.py        # SQL classification (classify_sql), execution (execute_adhoc/query/explain)
│   ├── group_engine.py        # Multi-connection comparison runs
│   ├── object_browser.py      # Metadata browsing (tables/views/routines) per DB
│   ├── table_browser.py       # Row browsing with FK label resolution + pagination
│   ├── ddl_extractor.py       # Oracle DDL extraction; ddl_pg.py / ddl_mysql.py for PG/MySQL
│   ├── package_editor.py      # PL/SQL package editing helpers
│   ├── template_engine.py     # Parameterized query templates
│   ├── exporter.py            # CSV/JSON/TXT exports + IDE-style DBMS execution evidence
│   ├── html_report.py         # HTML report generation
│   ├── history.py / audit.py  # Execution history and audit log
│   ├── crypto.py              # Fernet password encryption
│   ├── config_portability.py  # Import/export of config bundles
│   ├── oracle_client_installer.py  # Oracle Instant Client bootstrap
│   └── paths.py               # CONFIG_DIR / SETTINGS_FILE resolution (honors DBQM_HOME)
├── models/            # Data models with JSON persistence
│   ├── connection.py  # db_type ∈ {oracle, sqlserver, postgresql, mysql}
│   ├── query.py  group.py  settings.py  template.py
└── ui/                # Textual TUI (imports core; core never imports ui)
    ├── app.py         # Main App: single tabbed shell (TabbedContent), routing,
    │                  #   keybindings; `AbasPrincipais` keeps focus from switching tabs
    ├── theme.py  utils.py
    ├── screens/       # One Vertical-widget screen per feature (adhoc, query_exec,
    │                  #   group_exec, group_run, browser, connections, history,
    │                  #   ferramentas, exec_routine, package_editor, settings, ...)
    ├── widgets/       # Reusable components (panel, templates_sidebar, result_table,
    │                  #   action_bar, lista_hierarquica, sql_viewer, status_bar,
    │                  #   progress, dialog, empty_state, veredito, esqueleto, ...)
    └── modals/        # Dialog screens (confirm, param_input, export_picker,
                       #   export_dir_setup, column_maps, error, help, ...)
```

> Note: there is **no `ui/flows/`** — the old Rich/prompt "flow" layer was
> migrated to Textual `screens/`. Ignore any older doc that references flows.

**Layering rule:** `core/` is UI-agnostic and must never import from `ui/`.
Both the TUI (`ui/app.py`) and the CLI (`cli.py`) call into `core/`.
`design/` sits below both: it imports nothing from `dbqm`, and is imported by
the TUI (`ui/theme.py`), the CLI (`cli.py`), and the HTML report
(`core/html_report.py`) — one source of color/contrast truth for all three
consumers, none of them importing each other.

## Development Workflow (MANDATORY)

After **every** feature, bugfix, or refactor, follow this exact sequence — never
skip a step, never commit with failing tests, always publish after push:

1. **Build** the project (`python -m build`)
2. **Create/update tests** for the changed functionality
3. **Run all tests** (`python -m pytest tests/ -x -q`)
4. **Bump version** in `dbqm/_version.py` (SemVer — see below)
5. **Update README.md** if features/structure/test-count changed
6. **Commit** (Conventional Commits — see below)
7. **Push** to remote
8. **Publish to PyPI** (see below)

## Commit Convention

Conventional Commits: `<type>(<scope>): <description>`

- Types: `feat`, `fix`, `refactor`, `perf`, `style`, `docs`, `test`, `build`, `ci`, `chore`
- Scopes: `ui`, `core`, `models`, `config`, `web`
- **NEVER include AI `Co-Authored-By` lines (or any AI-attribution) in commits.**

## Versioning (SemVer)

- **MAJOR** — breaking changes
- **MINOR** — new features
- **PATCH** — bug fixes, small UI adjustments, hardening

## Testing

- Framework: **pytest + pytest-asyncio** (`pytest.ini_options` in `pyproject.toml`;
  `testpaths=["tests"]`, `pythonpath=["."]`)
- Layout mirrors `dbqm/`: `tests/core/`, `tests/models/`, `tests/ui/`,
  plus `tests/design/` (the design-system guards), `tests/test_cli.py` and shared
  fixtures in `tests/conftest.py`
- Run: `python -m pytest tests/ -x -q` (currently **940** tests, of which
  36 in `tests/design/` are the color and layout guards)
- UI tests use the `async with app.run_test() as pilot` pattern
- Fixture `tmp_config_dir` redirects all config/export paths to a temp directory
- Prefer pure, directly-testable functions in `core/` (e.g. `classify_sql`,
  `format_dbms_evidence`) so behavior is covered without a live DB

## Key Patterns

### SQL classification (`core/query_engine.py`)
- `classify_sql` returns `SELECT | INSERT | UPDATE | DELETE | DDL | PLSQL | EXPLAIN | UNKNOWN`.
- It classifies **DDL / PL/SQL / EXPLAIN by the leading keyword first**, before
  calling `sqlparse.parse` — this avoids tokenizing multi-thousand-line
  `PACKAGE BODY` sources (wasteful and historically fragile against sqlparse
  token caps). `sqlparse` is only used to disambiguate SELECT vs DML and to
  resolve `WITH` (CTE → SELECT).
- Leading `--` and `/* */` comments are stripped for *classification only*
  (`_strip_leading_comments`); the original text (comments + trailing `/`) is
  what actually runs.
- Anonymous PL/SQL blocks (`DECLARE`/`BEGIN`) and `EXEC`/`EXECUTE`/`CALL`
  shortcuts are supported; `DBMS_OUTPUT` is captured automatically on Oracle.
- DDL keeps its final `;` (stripping it would leave objects INVALID); after DDL,
  compilation errors are fetched and surfaced.

### Textual TUI
- Screens are `Vertical` widgets loaded into `#screen-area`.
- Arrow keys: use `on_key` with `event.prevent_default()`/`event.stop()` — not
  `key_*` methods (which mark events handled even when not acting).
- Modal focus: `app.check_action()` returns `False` when `screen_stack > 1` so
  modal keys aren't intercepted.
- `DataTable` selection: `cursor_type="row"` for `RowSelected` events.
- Keyboard shortcuts inside `TextArea`: use `on_key`, not `BINDINGS` (TextArea
  consumes bindings).

### Select widget
- `Select.value` is `Select.NULL` (a `NoSelection`) when empty; `Select.BLANK`
  is `False`. Check `isinstance(val, str)` to know a real value is selected.

### Database
- Oracle: thick mode via `oracledb.init_oracle_client()`; DSN via
  `oracledb.makedsn()` (SID vs service_name). `NLS_LANG` is forced to
  `.AL32UTF8` so Oracle error messages come back as UTF-8 (correct accents on
  Windows).
- Connection passwords encrypted with **Fernet** (`core/crypto.py`).
- Non-Oracle DBs share pyformat parameter binding.

### Exports & evidence
- Default export dir is `Path.cwd() / "exports"`, **not** `~/.dbqm/exports`.
- Saving/copying DBMS output produces an **IDE-style execution evidence** record
  (`format_dbms_evidence`): executed SQL + connection + date/time + DBMS_OUTPUT +
  outcome. Timestamp is captured in the UI and injected so the exporter stays pure.

### CLI (`cli.py`)
- Non-interactive commands: `sql`, `run`, `group`, `list`, `history`, etc.
- `-f/--format`: `table | json | csv | raw` (`raw` prints values without
  decoration — for extracting CLOB/LONG sources cleanly).
- Example: `python -m dbqm sql "<sql-or-file>" "<connection name>" -f raw`.

### UI conventions
- Interactive UI labels **intentionally omit accents** (e.g. `Historico`,
  `conexao`, `Nao`). This is deliberate — **do not "fix" them**.

### Language: English in code, Portuguese only on screen

This is not a style preference — it is the line between *what the program is
made of* and *what the user reads*.

**English** — everything that is code:
- identifiers: modules, classes, functions, constants, fixtures, test names
- design token names and the `$var` references to them
- comments and docstrings
- commit messages

**Portuguese, without accents** — everything the user sees:
- widget labels, panel titles, button text, tab names
- notifications, error and confirmation messages
- CLI output text

Assertion messages in tests are the one deliberate grey area: they are read by
whoever the test failed on, not by the user. Write them in English, like the
rest of the test.

**Why it is written down.** It was never written down before, and it held
anyway — until it didn't. A design-system series added ~370 Portuguese comments,
59 Portuguese docstrings, 34 Portuguese identifiers and 15 Portuguese design
tokens across ~70 commits, and every one of them passed review, because the rule
lived only in the code's own consistency. Before that series `main` had 5
Portuguese comments against 215 English and **zero** Portuguese docstrings
against 406. A convention that strong is easy to break precisely because nobody
ever has to state it.

If you are working in Portuguese with the maintainer, the conversation is not
the codebase. Write the code in English anyway.

## Layout grammar (read before touching `dbqm/ui`)

The TUI has a **grammar**, not a per-screen style. Phase 1 fixed color (15
semantic tokens); phase 2 fixed **structure**. Four questions each screen used
to answer on its own are now answered once, and each answer has a guard in
`tests/design/test_layout_inventory.py`.

**1. What is a section?** `Panel` is the *only* section frame (`Dialog` is its
modal twin). Nothing floats loose on the background, and no screen draws its own
box. A screen taller than the viewport **scrolls** — it never truncates in
silence, which is how the Oracle Instant Client section stayed invisible for
weeks (`tests/design/test_vertical_overflow.py`).

**2. How do you navigate a set?** By **cardinality**, not by taste: up to ~7
fixed items → tabs; a variable number → `Select` with counts; choosable things →
`OptionList` with a 2–3 line hierarchy; tabular data → `DataTable`. `ListView`
is out of the vocabulary — it did the same job as `OptionList`.
A list item is **never a concatenated string**: identity (bold, alone),
disambiguation (indented, `$texto-apoio`), context (indented,
`$texto-desabilitado`, optional). Build it with `item_hierarquico`
(`dbqm/ui/widgets/lista_hierarquica.py`).

**3. How dense is a row?** A **result** table never truncates to fit: key column
pinned (`fixed_columns=1` when there is more than one column), zebra stripes,
horizontal scrolling, and the record mode (`V`) that already existed. The reason
is the domain — dbqm exists to *compare*, and a row whose key scrolled out of
sight compares nothing.

**4. Where do actions live?** Anchored to the panel they operate, left-aligned
with its content; destructive actions separated from the rest. Centring a
cluster only makes sense when the cluster **is** the screen — a dialog. And a
**button is an action, never navigation or a menu**.

### The guards, and how far each one reaches

| Guard | Rejects | Enforcement |
|---|---|---|
| `sem_borda_crua` | `border:`/`outline:` outside `Panel`/`Dialog` | mechanical, 1 written exemption |
| `sem_listview` | any mention of `ListView` in `dbqm/ui` | mechanical, no exemptions |
| `sem_cluster_centralizado` | layout centring outside a dialog | mechanical, 5 written exemptions |
| `rotulo_nao_achatado` | list item built as one flat string | mechanical, 1 written exemption |
| `tabela_com_chave_fixa` | result table (columns built from data) without `fixed_columns` | mechanical, no exemptions |
| `botao_nao_navega` | button handler that switches tab or opens a tool | mechanical, **4 written exemptions** |

`botao_nao_navega` deserves a note, because it is the one whose exemption list is
the interesting part. `EmptyState` requires `acao_rotulo`/`acao_id` — the four
parameters are mandatory so that no empty list is ever a dead end. When the
honest way out of an empty screen lives in another tab, honouring that contract
means navigating. **Four** call-to-actions do it today (`history`, `query_exec`,
`group_run`, `templates_sidebar`); they are listed by button id in
`NAVEGACAO_ISENTA` with the reason. Making the action optional would touch 14
call sites and is a flow change, out of scope for the layout phase. The guard's
job until then is the **ceiling**: the fifth navigating button fails the suite,
and a stale exemption (a CTA that stops navigating) also fails it.

Every textual/AST scan **names its own limits in the code**, and those comments
are load-bearing: a false reason in a comment is worse than no comment, because
the next reader takes it for a verified fact. In short, the scans cannot see
markup built at runtime, values assembled in another layer, CSS declarations
split across two lines, or anything outside `dbqm/ui`. Read the limit block next
to each guard before concluding "the guard is green, so the rule holds".

### Two lessons this phase paid for

- **Assert what renders, not the attribute.** `fixed_columns == 1` can stay set
  while the pinned column stops painting; `_actions` was populated on every
  screen while the ActionBar painted on none (the StatusBar covered it). Tests
  that read attributes stayed green through both. Drive the app, read the
  rendered strips or the exported screenshot (`tests/ui/_helpers.py`:
  `texto_renderizado`, `linhas_renderizadas`, `recorte`).
- **Measure in the state where the defect happens.** A list description was
  sized against `content_region.width` measured on a list too short to scroll;
  the real list has a scrollbar and the fix was two columns off. A screen test
  gave `SettingsScreen` 24 rows when the real app gives it 20. Mount the real
  `DBQMApp`, at the real size, with the data that triggers the bug.

### Known debt, recorded on purpose (not fixed here)

> Struck-through entries were re-measured and either fixed or found not to
> reproduce; the note on each says which, and what was measured. They stay
> visible on purpose — a debt entry that quietly disappears teaches the next
> reader nothing about why it was there.

- ~~On startup (Coleta tab) the ActionBar paints **Conexoes'** actions.~~ **Does not
  reproduce.** Re-measured 9/9 (3 sizes x 3 repeats, config with one connection;
  same result with and without the tab-focus fix): on Coleta the bar is **empty**.
  `AdhocScreen` exposes neither `_set_actions` nor `_set_list_actions`, so
  `on_tabbed_content_tab_activated` clears the bar — which is what the code says.
  With an **empty** config the app opens on Conexoes and shows Conexoes' actions,
  which is right. What remains is a smaller, different thing: the tab that hosts
  the SQL editor announces no action at all until the first execution.
- ~~Every app mount fires a spurious `Subdiretorios por tipo: ativado` toast.~~
  **Fixed** — and there were three, not one. `on_switch_changed` /
  `on_select_changed` now return early when the incoming value already equals the
  stored one. The three: export subdirs on every launch; audit log on every launch
  for anyone with `audit_log_enabled` on; and `Tema alterado: plano-escuro` on the
  first launch after upgrading from 1.17.x — that one was the `github-dark` ->
  `plano-escuro` **rename** announcing itself as a user's choice. Each also
  rewrote `settings.json` (measured: 1 write with a fresh config, 2 with audit on).
- The two Oracle Instant Client tests in `tests/core/test_db_manager.py` read the
  **live user config** instead of `tmp_config_dir` — any user who actually sets
  `oracle_client_dir` breaks them on their own machine.
- `Breadcrumb` (`dbqm/ui/widgets/breadcrumb.py`) is **fully dead**: zero live
  instances, `package_editor.py:701-708` still queries it and every call raises
  into a bare `except`, and it is still exported from `widgets/__init__.py:3,15-16`.
- The connection checklist in `group_exec` is the one flat list label left.
  `SelectionList` paints **only the first line** of a prompt (measured), so
  applying `item_hierarquico` there would delete the target instead of
  clarifying it; the real fix is a different widget.
- ~~`test_f_keys_switch_tabs` / `test_clients_manager_opens_in_a_titled_panel`
  are timing-sensitive under load.~~ **Fixed at the root** — it was not a flaky
  test, it was stock `TabbedContent` treating FOCUS as NAVIGATION
  (`_on_tab_pane_focused` -> `self.active = pane.id`). Since every screen schedules
  its own initial focus, the previous screen's late focus undid the tab switch.
  `AbasPrincipais` (`ui/app.py`) kills the message with `prevent_default()` —
  `stop()` alone is not enough, because Textual dispatches the same message to the
  handler of EVERY class in the MRO (measured: `stop()` changed nothing). Covered
  by `test_focus_in_an_inactive_pane_does_not_switch_tabs` and
  `test_function_key_at_startup_reaches_the_requested_tab`, both of which fail
  deterministically without the fix with the flake's own message
  (`assert 'tab-conexoes' == 'tab-historico'`).
- Fixed-schema tables (`history`, `query_manage`, `template_manage`, …) are out
  of `tabela_com_chave_fixa` by design. The spec's line about giving `history`
  a pinned key and zebra was never implemented; zebra there would blend the
  `marcar_veredito` cells at runtime, invisible to the contrast guard.
- **`history` starves vertically, and that outweighs the line above.** At 80x24,
  `#hist-detail-panel { min-height: 8 }` (`history.py:35-38`) eats half the screen
  and leaves the table a **4-line** viewport: with 30 entries, **2 are visible**. A
  pinned key and zebra stripes do not fix a list that does not fit.
- **Downgrading the theme still breaks**, but now only after a user action. Rolling
  back to 1.17.x with `theme: plano-escuro` in `settings.json` raises
  `InvalidThemeError: Theme 'plano-escuro' has not been registered`. Data and the
  Fernet key stay readable; recovery is hand-editing one key. Until the false theme
  toast was fixed, 1.21's first launch rewrote that key by itself and the rollback
  broke with nobody having touched anything; now the file only changes when someone
  actually picks a theme.
- **Guard 6 (`test_button_does_not_navigate`) has an `elif`-chain hole.** `_ids_do_ramo`
  (`tests/design/test_layout_inventory.py:764-776`) gathers the literal ids from
  every enclosing `if` test and takes `sorted(ids)[0]`. In an `if/elif` chain the
  `elif` is an `If` nested in the previous one's `orelse`, so walking up the parents
  also picks up the sibling branch's id: a navigating branch whose id sorts AFTER an
  exempt id inherits the exemption and passes in silence. Break-tested: an `elif
  "zzz-..."` beside the exempt `"executar-consulta"` in `history.py` escapes;
  renamed to `"aaa-..."`, the same branch fails. Today's handlers are flat, so
  nothing escapes now. Also recorded in the guard's own "Limites conhecidos" block,
  which is where the next reader looks.
- **Guard 6 accepts the string literal `"action_switch_tab"` as proof of
  navigation.** That is the form the four real CTAs use
  (`getattr(self.app, "action_switch_tab", None)`), but it means gutting the call
  while keeping the `getattr` leaves the guard green with a silent CTA — it proves
  the NAME is written there, not that navigation happens.
- **The tab strip breaks decision 2 of the grammar** ("~7 fixed, fit the width"):
  there are **eight**. Measured at 80 columns on launch, the strip ends at
  `⚙️  Confi` — label cut mid-word, Consultas and Ferramentas invisible — and it
  scrolls with **no overflow indicator**, which breaks decision 1 as well.
- **Two vocabularies for the action row.** `adhoc` uses auto-width buttons anchored
  left; `connections` uses full-width buttons with centred labels — byte for byte
  the "full-width buttons pretending to be a menu" that §7 criticises. It escapes
  the guard because `text-align` is out of the guard's scope.

## Git Policy

- **NEVER commit AI plans, PRDs, or AI-generated planning docs.**
- `docs/plans/` (incl. `docs/plans/BACKLOG.md`), `PRD.md`, and `.claude/` are in
  `.gitignore`. `docs/plans/` is the sanctioned **local** planning area.
- Only AI-related files allowed in the repo: `AGENTS.md`, `CLAUDE.md`, agent configs.
- Other gitignored entries: `config/`, `.dbqm_key`, `tns/`, `*.ora`, `clients/`,
  `exports/`, plus standard Python ignores.

## README

Always keep `README.md` in sync when features are added/removed: Features list,
Keyboard Navigation table, Sidebar table, Project Structure tree, and test count.

## PyPI Publishing

```bash
PYPI_TOKEN=$(cat .env | tr -d '\r\n')   # .env holds the raw PyPI API token (no assignment)
python -m build
python -m twine upload dist/dbqm-<version>* -u __token__ -p "$PYPI_TOKEN"
```

## Environment

- Windows-first development. **No WSL** — always propose native Windows solutions.
- Primary shell is PowerShell; a POSIX Bash tool is also available (mind syntax).
