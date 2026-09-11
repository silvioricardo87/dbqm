# ROADMAP

What to work on next. **Ordered by importance first, grouped by theme inside
each tier.** Bugs outrank everything — a feature built on top of a known defect
is two problems.

Each item carries the evidence that earned it: the file, the line, and what goes
wrong for a user. **An item with no failure scenario is not ready to be worked
on** — that rule is what keeps this list from filling with opinions.

This is the single backlog. There is no other list: the two `docs/plans/`
backlogs it replaced were folded in here and deleted, their resolved items
recorded below rather than dropped.

> Working papers (specs, plans, execution logs) live under `docs/plans/` and
> `docs/superpowers/`, both gitignored. This file is the committed, public one.

---

## Tier 0 — Bugs

**Always above any feature.** Four themes, in this order: a wrong answer beats a
missing one, a broken screen beats dead code, and a guard that lies beats
cosmetics — because a green guard actively misleads the next person.

### Theme: execution correctness — *gives a wrong answer*

| # | Bug | Where | What goes wrong |
|---|---|---|---|
| **B10** | **SQL Server ad-hoc execution is broken in two ways**, both silent | `core/query_engine.py` — `_normalize_plsql` (called at ~`:259` without checking `conn.db_type`), and the `PLSQL` branch of `execute_adhoc` | **(a)** `EXEC`/`EXECUTE`/`CALL` is rewritten into Oracle syntax for *every* engine: `EXEC dbo.PROC @p='1'` is sent to SQL Server as `BEGIN dbo.PROC @p='1'; END;`, which is why the driver answers `Incorrect syntax near 'dbo'`. The README scopes the shortcut to Oracle, so the defect is that it mangles the statement instead of passing it through or refusing clearly. **(b)** The `PLSQL` branch never reads `cursor.description` and never calls `cursor.nextset()`, so a T-SQL batch ending in `SELECT @n, @m` runs and prints only `Bloco PL/SQL executado` — the result set is silently dropped. Correct for Oracle (a block returns no rows); wrong for SQL Server. **(c)** Cosmetic: that message says "PL/SQL" on a T-SQL connection (`cli.py:445`, `ui/screens/adhoc.py:37`). Reported from ticket IM05325534, where it forced debugging a T-SQL procedure through a hand-written `get_connection()` script. |
| **B7** | `decrypt("")` on a passwordless connection produces `Erro ao conectar:` with an **empty message** | `core/db_manager.py:349` | `InvalidToken`'s `str()` is empty, so the user gets an error with no information. Pre-existing, but `--no-password` made it easy to reach. |

### Theme: TUI usability — *a screen or a rollback fails outright*

| # | Bug | Where | What goes wrong |
|---|---|---|---|
| **B4** | `history` starves vertically: at 80x24, `min-height: 8` on the detail panel leaves the table a 4-line viewport | `ui/screens/history.py:37` | **With 30 entries, 2 are visible.** The history screen is effectively unusable at the default terminal size — which is the size most people run. |
| **B5** | Downgrading breaks the app | `models/settings.py` + `ui/theme.py` | Rolling back to 1.17.x with `theme: plano-escuro` in `settings.json` raises `InvalidThemeError: Theme 'plano-escuro' has not been registered`. Data and the Fernet key stay readable; recovery is hand-editing one key. |

### Theme: dead code — *advertises something that cannot happen*

| # | Bug | Where | What goes wrong |
|---|---|---|---|
| **B1** | `Breadcrumb` is entirely dead — zero instances anywhere, yet `package_editor` still queries it, so **every call raises into a bare `except Exception: pass`** | `ui/widgets/breadcrumb.py`; `ui/screens/package_editor.py:702-710`; exported from `ui/widgets/__init__.py:3,15-16` | A silent exception on a normal path, and a widget in the public surface that nothing can use. Verified: `Breadcrumb()` appears 0 times in `dbqm/`. |
| **B2** | `Connection.windows_auth` is declared and **never read or written** anywhere in `dbqm/` | `models/connection.py:26` | SQL Server Windows authentication looks supported and is unreachable: no form field, no CLI flag, and `get_sqlserver_connection` never consults it. Either implement it end to end or delete the field. |
| **B3** | PNG export is unreachable and its dependency does not exist | `ui/modals/export_picker.py` (8 references to `include_png`) | `ExportPickerModal` renders a PNG button when `include_png=True`, and **no caller ever passes it**. `Pillow` is in no dependency list and imported nowhere. The README claimed both the format and the dependency until 1.22.0. |

### Theme: tests and guards that lie — *green while the rule is broken*

| # | Bug | Where | What goes wrong |
|---|---|---|---|
| **B6** | Two Oracle Instant Client tests read the **live user config** instead of `tmp_config_dir` | `tests/core/test_db_manager.py` | The suite fails on the machine of anyone who actually set `oracle_client_dir` — a test that depends on the developer's own environment. |
| **B8** | The tab strip breaks the layout grammar it is measured against | `ui/app.py` | Eight tabs where the grammar says ~7 must fit the width. At 80 columns the strip ends mid-word (`⚙️  Confi`), Consultas and Ferramentas are invisible, and it scrolls with **no overflow indicator**. |
| **B9** | Layout guard 6 has an `elif`-chain hole | `tests/design/test_layout_inventory.py:764-776` | `_ids_do_ramo` walks up parent `If` nodes and picks `sorted(ids)[0]`, so in an `if/elif` chain a navigating branch inherits a sibling's exemption when its id sorts later — it passes in silence. Break-tested: `zzz-` escapes, `aaa-` fails. |

---

## Field reports — already resolved

Recorded so nobody reopens them. These came from
`analise-tickets/_plugin/melhorias-dbqm`, where a sustainment analyst files what
forced them into a second tool (SQL Developer, Toad, sqlplus) mid-ticket.

| Report | Status |
|---|---|
| 001 — anonymous PL/SQL blocks, `DBMS_OUTPUT` capture, faithful trailing `;` in DDL, `--format raw`, UTF-8 Oracle errors on Windows | **Shipped.** All five are current features. |
| 002 — CTE (`WITH … SELECT`) and `EXPLAIN PLAN` support in the `sql` parser | **Shipped.** `--explain` runs `EXPLAIN PLAN FOR` + `DBMS_XPLAN.DISPLAY` in one step. |
| 003 — `PACKAGE BODY` of 8423 lines rejected with `Maximum number of tokens exceeded (10000)` | **Fixed, verified.** `classify_sql` now decides DDL by the leading keyword *before* touching `sqlparse`, so a named-object `CREATE` never reaches the tokenizer. Measured against a synthetic 12 002-line body: classified `DDL` in 2 ms, no error. The report predates the fix; it can be archived. |
| 004 — `EXEC` broken on SQL Server, T-SQL batches swallow their result sets | **Open — this is B10 above.** |

### The TUI visual backlog — all of it

`docs/plans/BACKLOG.md` held 21 open items, 19 of them "this modal is missing
`height: auto`". Re-checked one by one against the current code before deleting
the file, because a backlog written in July predates both the redesign and the
design-system phases:

| Claim | Status |
|---|---|
| 19 modals stretch to the screen edge for lack of `height: auto` | **Resolved structurally.** The `Dialog` component replaced 29 hand-copied frames and carries `height: auto; max-height: 90%` in its own CSS. Counted: `group_manage` 6, `package_editor` 4, `query_manage` 6, `template_manage` 1 — exactly the modals the backlog named, all now built on `Dialog`. A component-inventory guard blocks a second hand-rolled copy from reappearing. |
| `group_exec`'s `_QueryPickerModal` and `_TemplateInputModal` | **Gone.** Neither class exists any more. |
| Settings stacks sections vertically with fixed margins; wasted space on wide terminals, excessive scrolling on narrow ones. *Proposal: multi-column layout.* | **Resolved, and by the proposed design.** `SettingsScreen.compose` is a `Horizontal` of `settings-col-esquerda` / `settings-col-direita`, each a `NavVerticalScroll` of `Panel` sections. |

Nothing from that file survived into this one. It was deleted rather than
carried forward as noise.

---

## Tier 1 — Pending (1.22.0 leftovers)

| # | Item | Why now |
|---|---|---|
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

**Shipped in 1.22.0** and therefore absent from the table below: `X2`
(non-interactive secrets), `R1` (the connection rules extracted to
`core/connection_builder.py`) and `C1` (`dbqm connection add|update|rm|show|list`).
Item ids are stable and carried over from the backlog this file replaced; the
`B` ids in Tier 0 are this file's own and do not map to it.

Themes, in the order they unlock each other: **the contract** (X1) must settle
before **discovery** (C2, C3) is worth parsing, **execution** (C4, C8) is what an
agent does once it can see, **safety** (X3) is what makes that defensible, and
**curation** (C5-C7) is how findings survive the session.

| Order | Item | Theme | Effort | Agent value | Notes |
|---|---|---|---|---|---|
| 1 | **X1** — one machine-readable output contract | contract | M | **critical** | `-f json` on *every* command; errors as structured JSON on **stderr** (today they go to stdout with Rich markup, which corrupts a JSON stream); a stable documented exit-code table. Today almost everything exits `1`. |
| 2 | **C2** — `dbqm objects` / `dbqm describe` | discovery | M | **critical** | The biggest gain for the least work: `core/object_browser.py` is already complete and engine-aware (columns, PK, FK, indexes, view definitions, package routines). Without it an agent hand-writes catalogue SQL per engine. |
| 3 | **C4** — `dbqm call` (execute a routine) | execution | M | high | `execute_routine` already handles IN/OUT binding, return values and DBMS_OUTPUT capture. |
| 4 | **X3** — read-only guard | safety | S | high | `DBQM_READONLY=1` / `--read-only` refuse anything but SELECT/EXPLAIN before it reaches the driver, plus a `read_only` field on `Connection`. This is what makes handing an agent the tool defensible. |
| 5 | **C8** — `dbqm multi` (one ad-hoc SQL across N connections, compared) | execution | M | high | The Multi-Exec tab has no CLI equivalent; `run-group` only runs *saved* groups of *saved* queries. For sustainment work this is the most-used flow. Reuses `build_group_result` as-is. |
| 6 | **C11** — HTML report from the CLI | evidence | **S** | medium | `core/html_report.py` exists; `-e/--export` just does not offer `html`. The cheapest item on this list. |
| 7 | **C3** — `dbqm rows` (browse a table) | discovery | M | medium-high | `core/table_browser.py` resolves foreign keys to a human label, so an agent reads `PAGO` instead of `3`. Open question: is `--where` worth the injection surface when `dbqm sql` exists? |
| 8 | **C5 / C6** — saved query and group CRUD | curation | M | medium | Follows the `connection_builder` pattern: rules in `core`/`models`, both front ends calling them. |
| 9 | **C7** — `dbqm source` / `dbqm compile` (PL/SQL packages) | curation | S-M | medium | Narrower than it looks — `dbqm sql` already compiles and surfaces errors. What is genuinely missing is *reading* current source. Confirm the overlap with `ddl` and `sql -f raw` first. |
| 10 | **C9 / C10 / C12 / X4** — templates, `config get|set`, oracle-client, self-description | S-M | low | `config set audit_log_enabled true` is the one an agent flow cares about. |

### Deliberately not scheduled

- **An MCP server** (`dbqm mcp`, operations as MCP tools). It is the native shape
  for agent consumption and would remove the shell round-trip entirely — but it
  should wrap a settled CLI contract, not race it. Revisit after **X1** and the
  first two items above have landed.

---

## Suggested next slice

**B10 first, on its own.** It is the only bug that makes dbqm give a wrong
answer on a workflow someone actually runs, and it costs a sustainment analyst a
second tool mid-ticket. Both halves are small and db_type-aware: do not
normalize `EXEC`/`EXECUTE`/`CALL` unless the connection is Oracle, and walk
`cursor.nextset()` in the non-Oracle branch. It needs a SQL Server connection to
verify, which no other item here does — so it is worth doing while that is at
hand.

**Then B1-B4 together.** B1 and B3 are deletions, B2 is a delete-or-implement
decision, and B4 is a CSS constraint — all small, all TUI-side.

P1 shipped in 1.22.1.

Then **X1**, because **C2** is worth much less without it: schema discovery that
answers with a Rich table is schema discovery an agent cannot parse.
