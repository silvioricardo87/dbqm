# ROADMAP

What to work on next, in priority order. **Bugs outrank everything** — a feature
built on top of a known defect is two problems.

Each item carries the evidence that earned it: the file and line, and what goes
wrong for a user. An item with no failure scenario is not ready to be worked on.

> Working papers (specs, plans, execution logs) live under `docs/plans/` and
> `docs/superpowers/`, both gitignored. This file is the committed, public list.

---

## Tier 0 — Bugs

**Always above any feature.** Four of these are dead code that can simply be
deleted; two make a screen or a rollback actually fail for a user.

| # | Bug | Where | What goes wrong |
|---|---|---|---|
| **B1** | `Breadcrumb` is entirely dead — zero instances anywhere, yet `package_editor` still queries it, so **every call raises into a bare `except Exception: pass`** | `ui/widgets/breadcrumb.py`; `ui/screens/package_editor.py:702-710`; exported from `ui/widgets/__init__.py:3,15-16` | A silent exception on a normal path, and a widget in the public surface that nothing can use. Verified: `Breadcrumb()` appears 0 times in `dbqm/`. |
| **B2** | `Connection.windows_auth` is declared and **never read or written** anywhere in `dbqm/` | `models/connection.py:26` | SQL Server Windows authentication looks supported and is unreachable: no form field, no CLI flag, and `get_sqlserver_connection` never consults it. Either implement it end to end or delete the field. |
| **B3** | PNG export is unreachable and its dependency does not exist | `ui/modals/export_picker.py` (8 references to `include_png`) | `ExportPickerModal` renders a PNG button when `include_png=True`, and **no caller ever passes it**. `Pillow` is in no dependency list and imported nowhere. The README claimed both the format and the dependency until 1.22.0. |
| **B4** | `history` starves vertically: at 80x24, `min-height: 8` on the detail panel leaves the table a 4-line viewport | `ui/screens/history.py:37` | **With 30 entries, 2 are visible.** The history screen is effectively unusable at the default terminal size — which is the size most people run. |
| **B5** | Downgrading breaks the app | `models/settings.py` + `ui/theme.py` | Rolling back to 1.17.x with `theme: plano-escuro` in `settings.json` raises `InvalidThemeError: Theme 'plano-escuro' has not been registered`. Data and the Fernet key stay readable; recovery is hand-editing one key. |
| **B6** | Two Oracle Instant Client tests read the **live user config** instead of `tmp_config_dir` | `tests/core/test_db_manager.py` | The suite fails on the machine of anyone who actually set `oracle_client_dir` — a test that depends on the developer's own environment. |
| **B7** | `decrypt("")` on a passwordless connection produces `Erro ao conectar:` with an **empty message** | `core/db_manager.py:349` | `InvalidToken`'s `str()` is empty, so the user gets an error with no information. Pre-existing, but `--no-password` made it easy to reach. |
| **B8** | The tab strip breaks the layout grammar it is measured against | `ui/app.py` | Eight tabs where the grammar says ~7 must fit the width. At 80 columns the strip ends mid-word (`⚙️  Confi`), Consultas and Ferramentas are invisible, and it scrolls with **no overflow indicator**. |
| **B9** | Layout guard 6 has an `elif`-chain hole | `tests/design/test_layout_inventory.py:764-776` | `_ids_do_ramo` walks up parent `If` nodes and picks `sorted(ids)[0]`, so in an `if/elif` chain a navigating branch inherits a sibling's exemption when its id sorts later — it passes in silence. Break-tested: `zzz-` escapes, `aaa-` fails. |

---

## Tier 1 — Pending from the 1.22.0 release

| # | Item | Why now |
|---|---|---|
| **P1** | **Publish 1.22.1 with the corrected README** | 1.22.0 shipped with the old README, so the PyPI page currently advertises a `Pillow` dependency that does not exist, a `dbqm run --param1 value1` flag that never existed, and no `pip install dbqm`. The page only updates on a new release. |
| **P2** | The TUI has **no way to clear a password** | A blank field means "keep the stored one"; the CLI has `--no-password` and the screen has no equivalent. Long-standing, not a regression. Needs a UI decision — and the layout grammar constrains it (a button is an action, never a menu). |
| **P3** | Node 20 deprecation in the release workflow | `actions/checkout@v4` and `actions/setup-python@v5` are being forced onto Node 24. It works today and will stop. |
| **P4** | The empty-stdin error names `--no-password` on `export-config`/`import-config`, which have no such flag | Cosmetic; the message is still actionable where the case arises. |

---

## Tier 2 — Toolchain adoption

From the deviations section of [`docs/agents/BACKEND-PYTHON.md`](agents/BACKEND-PYTHON.md).
**The order is fixed** — that file explains why a type checker before a lockfile
turns the ratchet into a negotiation.

| Order | Step | Effect |
|---|---|---|
| 1 | uv + `uv.lock` + `.python-version`, delete the empty `requirements.txt` | Every later gate runs on a reproducible environment |
| 2 | ruff, starting with the rules the code already passes, widening one family at a time | Fills the empty Lint step of the task-completion cycle |
| 3 | mypy `strict` with a per-module ratchet for legacy modules | New code is typed from its first line |
| 4 | pytest strict config (`--strict-markers`, `filterwarnings = error`, `xfail_strict`) | Surfaces warnings the suite currently swallows |
| 5 | CI running steps 1-3 on every push | Until it does, the gates are manual and therefore optional |

---

## Tier 3 — Features: the CLI surface for scripted and AI-agent use

dbqm's CLI can *run* what already exists. Everything that **creates**, and
everything that **inspects the database's own shape**, was TUI-only until 1.22.0
shipped connection management. The gap is not missing logic — nearly every
capability below already exists in `core/`, UI-agnostic and tested. What is
missing is the CLI surface over it.

**Shipped in 1.22.0:** non-interactive secrets, the connection rules extracted to
`core/connection_builder.py`, and `dbqm connection add|update|rm|show|list`.

| Order | Item | Effort | Agent value | Notes |
|---|---|---|---|---|
| 1 | **X1** — one machine-readable output contract | M | **critical** | `-f json` on *every* command; errors as structured JSON on **stderr** (today they go to stdout with Rich markup, which corrupts a JSON stream); a stable documented exit-code table. Today almost everything exits `1`. |
| 2 | **C2** — `dbqm objects` / `dbqm describe` | M | **critical** | The biggest gain for the least work: `core/object_browser.py` is already complete and engine-aware (columns, PK, FK, indexes, view definitions, package routines). Without it an agent hand-writes catalogue SQL per engine. |
| 3 | **C4** — `dbqm call` (execute a routine) | M | high | `execute_routine` already handles IN/OUT binding, return values and DBMS_OUTPUT capture. |
| 4 | **X3** — read-only guard | S | high | `DBQM_READONLY=1` / `--read-only` refuse anything but SELECT/EXPLAIN before it reaches the driver, plus a `read_only` field on `Connection`. This is what makes handing an agent the tool defensible. |
| 5 | **C8** — `dbqm multi` (one ad-hoc SQL across N connections, compared) | M | high | The Multi-Exec tab has no CLI equivalent; `run-group` only runs *saved* groups of *saved* queries. For sustainment work this is the most-used flow. Reuses `build_group_result` as-is. |
| 6 | **C11** — HTML report from the CLI | **S** | medium | `core/html_report.py` exists; `-e/--export` just does not offer `html`. The cheapest item on this list. |
| 7 | **C3** — `dbqm rows` (browse a table) | M | medium-high | `core/table_browser.py` resolves foreign keys to a human label, so an agent reads `PAGO` instead of `3`. Open question: is `--where` worth the injection surface when `dbqm sql` exists? |
| 8 | **C5 / C6** — saved query and group CRUD | M | medium | Follows the `connection_builder` pattern: rules in `core`/`models`, both front ends calling them. |
| 9 | **C7** — `dbqm source` / `dbqm compile` (PL/SQL packages) | S-M | medium | Narrower than it looks — `dbqm sql` already compiles and surfaces errors. What is genuinely missing is *reading* current source. Confirm the overlap with `ddl` and `sql -f raw` first. |
| 10 | **C9 / C10 / C12 / X4** — templates, `config get|set`, oracle-client, self-description | S-M | low | `config set audit_log_enabled true` is the one an agent flow cares about. |

### Deliberately not scheduled

- **An MCP server** (`dbqm mcp`, operations as MCP tools). It is the native shape
  for agent consumption and would remove the shell round-trip entirely — but it
  should wrap a settled CLI contract, not race it. Revisit after **X1** and the
  first two items above have landed.

---

## Suggested next slice

**B1 through B4, plus P1, in one 1.22.1.** B1 and B3 are deletions, B2 is a
delete-or-implement decision, and B4 is a CSS constraint — all small, and P1 is
the release that finally puts the corrected README on PyPI.

Then **X1**, because **C2** is worth much less without it: schema discovery that
answers with a Rich table is schema discovery an agent cannot parse.
