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
    ├── app.py         # Main App: layout, routing, keybindings, #screen-area
    ├── theme.py  utils.py
    ├── screens/       # One Vertical-widget screen per feature (adhoc, query_exec,
    │                  #   group_exec, browser, ddl, connections, history, settings, ...)
    ├── widgets/       # Reusable components (sidebar, result_table, action_bar,
    │                  #   breadcrumb, sql_viewer, status_bar, progress, ...)
    └── modals/        # Dialog screens (confirm, param_input, export_picker,
                       #   connection_form, error, help, ...)
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
- Layout mirrors `dbqm/`: `tests/core/`, `tests/models/`, `tests/ui/`, `tests/api/`,
  plus `tests/test_cli.py` and shared fixtures in `tests/conftest.py`
- Run: `python -m pytest tests/ -x -q` (currently **846** tests)
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
