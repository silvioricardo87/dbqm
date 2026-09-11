# AGENTS.md — Instructions for AI Agents

> This is the **single source of truth** for AI agents working on dbqm.
> `CLAUDE.md` is a thin pointer to this file. These instructions OVERRIDE any
> default behavior — follow them exactly.

## Documents an agent must know

`AGENTS.md` is the canonical instruction file — the rules live here or in a file
this one names, never in two places. `CLAUDE.md` is a pointer stub.

| File | Read it when | Contains |
|---|---|---|
| **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** | **before any change under `dbqm/`** | Layout, layering, key patterns, the layout grammar and its six guards, and the measured known debt |
| **[`docs/ROADMAP.md`](docs/ROADMAP.md)** | choosing what to work on | Bugs (always first), pending items, and the feature backlog in priority order |
| [`docs/agents/AGENT-WORKFLOW.md`](docs/agents/AGENT-WORKFLOW.md) | starting a task | Planning, context management, edit safety, self-correction |
| [`docs/agents/TASK-COMPLETION.md`](docs/agents/TASK-COMPLETION.md) | finishing a change | The mandatory build → lint → test → docs → version → commit → merge cycle |
| [`docs/agents/BACKEND-PYTHON.md`](docs/agents/BACKEND-PYTHON.md) | writing Python here | House Python standards, plus the TUI/CLI/Windows-first sections that apply |
| [`docs/agents/VERSIONING.md`](docs/agents/VERSIONING.md) | bumping a version | Which level to bump, and the release flow |
| [`docs/agents/COMMITS.md`](docs/agents/COMMITS.md) | writing a commit | Message format, description style, language cascade |

**The five files under `docs/agents/` are copies** of shared guides from
`agents-defaults`, kept **byte-identical to their source up to a final
`## Deviations in this project` heading**. Everything dbqm does differently — and
every project fact those guides need — lives only under that heading. Never edit
a guide's body: a `diff` against the source up to that heading is the drift
check, and a guide edited in place is a guide nobody can trust.

**Read the deviations sections.** dbqm predates these guides: there is no linter,
no type checker and no lockfile, the layout is flat rather than `src/`, the CLI is
argparse rather than typer, and the Python floor is 3.10 because users install
this. `BACKEND-PYTHON.md` says which of those are deliberate and which are an
unstarted migration — they are not the same debt.

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

The file layout, the layering rule, the key patterns (SQL classification, the
Textual conventions, the `Select` widget trap, the database and export rules),
the **layout grammar** with its six repo-wide guards, and the **known debt** all
live in **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**.

**Read it before changing anything under `dbqm/`.** It is not optional context:
the layout grammar is enforced by tests that fail on a rule you did not know
existed, and the debt section records what was already measured so you do not
re-measure it or, worse, "fix" something that was found not to reproduce.

The one rule worth repeating here because it constrains every change:
**`core/` is UI-agnostic and must never import from `ui/`.** Both the TUI and
the CLI call into `core/`; `design/` imports nothing from `dbqm`.


## Development Workflow (MANDATORY)

The cycle is defined once, in **[`docs/agents/TASK-COMPLETION.md`](docs/agents/TASK-COMPLETION.md)**:
**build → lint → test → docs → version → commit → merge**. Any failure aborts
the cycle and it restarts from Step 1, because the code changed and the earlier
results no longer hold. Read that file's `## Deviations in this project` section
before the first run — it names what is different here.

The concrete commands, in dbqm's terms:

| Step | Command | Note |
|---|---|---|
| 1 Build | `python -m build` | `build` is not a declared dependency — `pip install build` on a fresh machine. |
| 2 Lint | *(none)* | **No linter exists.** Documented no-op; adopting ruff is a ROADMAP item. |
| 3 Test | `python -m pytest tests/ -x -q` | ~3m10s. Needs `pytest-asyncio` from the `dev` extra, or 327 async tests fail for an unrelated reason. Scope to the change; full run before a release. |
| 4 Docs | see [README](#readme), `docs/ARCHITECTURE.md`, `docs/ROADMAP.md` | The README is the PyPI page. |
| 5 Version | edit `dbqm/_version.py` | Manual, which `VERSIONING.md` forbids; the tag guard is the compensating control. |
| 6 Commit | Conventional Commits | See below. |
| 7 Merge | local `--no-ff` into `main` | Solo work needs no PR. |

**Publishing is not a step of this cycle.** It happens when a `v*` tag is pushed
— see [PyPI Publishing](#pypi-publishing). Pushing `main` publishes nothing.

## Commit Convention

Format, types, description style and the language cascade are in
**[`docs/agents/COMMITS.md`](docs/agents/COMMITS.md)**. Two project specifics:

- **Scopes are a closed set**: `ui`, `core`, `models`, `config`, `web`. A commit
  that fits none of them is usually two commits.
- **NEVER include an AI `Co-Authored-By` line, or any AI attribution**, in a
  commit message, a PR title, or a PR body.

## Versioning (SemVer)

Bump-level rules and the release flow are in
**[`docs/agents/VERSIONING.md`](docs/agents/VERSIONING.md)**. In short: MAJOR for
breaking changes, MINOR for features, PATCH for fixes and hardening. The version
lives in `dbqm/_version.py` and `pyproject.toml` reads it dynamically.

## Testing

- Framework: **pytest + pytest-asyncio** (`pytest.ini_options` in `pyproject.toml`;
  `testpaths=["tests"]`, `pythonpath=["."]`)
- Layout mirrors `dbqm/`: `tests/core/`, `tests/models/`, `tests/ui/`,
  plus `tests/design/` (the design-system guards), `tests/test_cli.py` and shared
  fixtures in `tests/conftest.py`
- Run: `python -m pytest tests/ -x -q` (currently **1038** tests, of which
  36 in `tests/design/` are the color and layout guards)
- UI tests use the `async with app.run_test() as pilot` pattern
- Fixture `tmp_config_dir` redirects all config/export paths to a temp directory
- Prefer pure, directly-testable functions in `core/` (e.g. `classify_sql`,
  `format_dbms_evidence`) so behavior is covered without a live DB

## Git Policy

- **NEVER commit AI plans, PRDs, or AI-generated planning docs.**
- `docs/plans/` (incl. `docs/plans/BACKLOG.md`), `PRD.md`, and `.claude/` are in
  `.gitignore`. `docs/plans/` is the sanctioned **local** planning area.
- Agent-facing files that **do** belong in the repo: `AGENTS.md`, `CLAUDE.md`,
  `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, the five guides under `docs/agents/`,
  and agent configs. The line is not "AI-related or not" — it is **durable
  project documentation vs. a working paper for one task**. A roadmap is the
  former; a plan for implementing one of its items is the latter.
- Other gitignored entries: `config/`, `.dbqm_key`, `tns/`, `*.ora`, `clients/`,
  `exports/`, plus standard Python ignores.

## README

`readme = "README.md"` in `pyproject.toml`, so **the README IS the package's
PyPI page**. Every claim in it is public and is read by people deciding whether
to install dbqm — an out-of-date flag or a dependency that does not exist costs
more there than in a repo file.

Keep in sync when features are added or removed: the Features list, the
Keyboard Navigation table, the Dashboard tabs table, and the CLI-mode examples.
**Verify CLI examples against the parser, not against memory** — a `--param1
value1` that never existed survived there for months, and a `Pillow`
dependency was listed that is not in `pyproject.toml` at all.

There is deliberately **no Project Structure tree**: it was a second copy of the
architecture documentation, drifting independently, in the one document where an
internal file layout serves no reader. Architecture lives in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); the README describes what the
program does for the person installing it.

The test count lives in this file (Testing section), not in the README — one
place to update instead of two.

## PyPI Publishing

**Releases are tag-driven and run in CI.** Push a `v*` tag and
`.github/workflows/publish.yml` builds and publishes. It guards that the tag
equals `dbqm/_version.py` and fails if they differ, which is the only thing
standing between a manual version edit and a wrong release.

```bash
git tag -a v1.22.0 -m "v1.22.0 - <one line>" && git push origin v1.22.0
gh run watch <run-id> --exit-status          # then verify
python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('https://pypi.org/pypi/dbqm/json'))['info']['version'])"
```

Two things learned the hard way:

- **The PyPI JSON API caches.** It can answer with the previous version for a
  while after a successful upload. Trust the workflow log (it lists each file
  uploaded), not the first API response.
- **A version whose tag was never pushed is not released.** Merging and pushing
  `main` changes nothing on PyPI — the page keeps serving the old version's
  README, including any claim you just corrected.

A manual `twine upload` from a developer machine bypasses the tag guard and is
**not** a release. `twine` is deliberately not installed.

## Environment

- Windows-first development. **No WSL** — always propose native Windows solutions.
- Primary shell is PowerShell; a POSIX Bash tool is also available (mind syntax).
