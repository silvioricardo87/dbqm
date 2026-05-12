# CLAUDE.md — Project Instructions for AI Agents

## Project Overview

**dbqm** (Database Query Manager) — Fullscreen TUI tool for managing and executing SQL queries across Oracle, SQL Server, PostgreSQL, and MySQL. Built with Python + Textual.

- Entry point: `dbqm/main.py`
- Version: `dbqm/_version.py` (read dynamically by `pyproject.toml`)
- Config directory: `~/.dbqm/` (overridable with `DBQM_HOME`)
- PyPI: https://pypi.org/project/dbqm/

## Architecture

```
dbqm/
├── core/          # Business logic (db_manager, query_engine, group_engine, exporter, etc.)
├── models/        # Data models with JSON persistence (connection, query, group, settings)
├── ui/
│   ├── app.py     # Main Textual App (layout, routing, keybindings)
│   ├── screens/   # Screen widgets (one per feature)
│   ├── widgets/   # Reusable UI components (sidebar, result_table, action_bar, etc.)
│   └── modals/    # Dialog screens (confirm, param_input, export_picker, etc.)
└── cli.py         # Non-interactive CLI
```

## Development Workflow (MANDATORY)

After **every** feature, bugfix, or refactor, follow this exact sequence:

1. **Build** the project
2. **Create/update tests** for the changed functionality
3. **Run all tests** (`python -m pytest tests/ -x -q`)
4. **Bump version** following Semantic Versioning (see "Versioning" below)
5. **Commit** following Conventional Commits (see "Commit Convention" below)
6. **Push** to remote
7. **Publish to PyPI** (`python -m build && twine upload` using token from `.env`)

Never skip steps. Never commit without tests passing. Always publish after push.

## Commit Convention

Use Conventional Commits format:

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `refactor`, `perf`, `style`, `docs`, `test`, `build`, `ci`, `chore`
Scopes: `ui`, `core`, `models`, `config`, `web`

**NEVER include AI Co-Authored-By lines in commits.**

## Versioning

Use Semantic Versioning:

- **MAJOR**: breaking changes
- **MINOR**: new features
- **PATCH**: bug fixes, small UI adjustments

## Testing

- Framework: pytest + pytest-asyncio
- Test directory: `tests/` (mirrors `dbqm/` structure)
- Run: `python -m pytest tests/ -x -q`
- All UI tests use `async with app.run_test() as pilot` pattern
- Fixture `tmp_config_dir` redirects all paths to temp directory

## Key Patterns

### Textual TUI

- Screens are `Vertical` widgets loaded into `#screen-area`
- Arrow key handling: use `on_key` with `event.prevent_default()`/`event.stop()` (not `key_*` methods which mark events as handled even when not acting)
- Modal focus: `app.check_action()` returns `False` when `screen_stack > 1` to avoid intercepting modal keys
- DataTable selection: use `cursor_type="row"` for `RowSelected` events
- Keyboard shortcuts in TextArea: use `on_key` handler, not `BINDINGS` (TextArea consumes bindings)

### Select Widget

- `Select.value` is `Select.NULL` (a `NoSelection` instance) when nothing selected, `Select.BLANK` is `False`
- Check with `isinstance(val, str)` to determine if a real value is selected

### Database

- Oracle: thick mode via `oracledb.init_oracle_client()`, DSN via `oracledb.makedsn()` (SID vs service_name)
- Connection passwords encrypted with Fernet (`core/crypto.py`)

### Exports

- Default to `Path.cwd() / "exports"`, not `~/.dbqm/exports`

## Git Policy

- **NEVER commit AI plans, PRDs, or AI-generated planning docs**
- `docs/plans/`, `PRD.md`, `.claude/` are in `.gitignore`
- Only AI-related files allowed: `CLAUDE.md`, agent configs

## README

- **Always update `README.md`** when features are added or removed
- Keep in sync: Features list, Keyboard Navigation table, Sidebar table, Project Structure tree, test count

## PyPI Publishing

```bash
PYPI_TOKEN=$(cat .env | tr -d '\r\n')
python -m build
python -m twine upload dist/dbqm-<version>* -u __token__ -p "$PYPI_TOKEN"
```

The `.env` file contains the raw PyPI API token (no variable assignment).
