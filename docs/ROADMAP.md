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

**Empty.** Nine of the ten were fixed and shipped in 1.22.2; the tenth was
closed as not applicable. Each is recorded under
[Verified resolved](#verified-resolved) with what was measured. Bugs return here
the moment one is found — this tier stays above every feature.

**B8 was closed by a ruling, not a fix.** The complaint was that the tab strip
is cut at 80 columns. The maintainer's decision: *"deixa como está mesmo, não
pretendo trabalhar com 80 colunas, as resoluções atuais são bem maiores, nem faz
sentido se preocupar com 80 colunas."* At the widths actually used, all eight
labels render whole. Two attempts were built and rejected before that call —
dropping the emoji (the only one of four variants that fit) and collapsing
inactive labels to the emoji alone (prototyped and shown). Both are recorded in
`docs/ARCHITECTURE.md` so neither is retried by accident.

That ruling reaches further than one bug: the design guards and several debt
entries use 80x24 as their reference size. Worth revisiting deliberately.

---

## Verified resolved

### Field reports from sustainment

Recorded so nobody reopens them. These came from
`analise-tickets/_plugin/melhorias-dbqm`, where a sustainment analyst files what
forced them into a second tool (SQL Developer, Toad, sqlplus) mid-ticket.

| Report | Status |
|---|---|
| 001 — anonymous PL/SQL blocks, `DBMS_OUTPUT` capture, faithful trailing `;` in DDL, `--format raw`, UTF-8 Oracle errors on Windows | **Shipped.** All five are current features. |
| 002 — CTE (`WITH … SELECT`) and `EXPLAIN PLAN` support in the `sql` parser | **Shipped.** `--explain` runs `EXPLAIN PLAN FOR` + `DBMS_XPLAN.DISPLAY` in one step. |
| 003 — `PACKAGE BODY` of 8423 lines rejected with `Maximum number of tokens exceeded (10000)` | **Fixed, verified.** `classify_sql` now decides DDL by the leading keyword *before* touching `sqlparse`, so a named-object `CREATE` never reaches the tokenizer. Measured against a synthetic 12 002-line body: classified `DDL` in 2 ms, no error. The report predates the fix; it can be archived. |
| 004 — `EXEC` broken on SQL Server, T-SQL batches swallow their result sets | **Open — this is B10 above.** |

### Tier 0 — the nine bugs fixed, and what was measured

| # | Fix | Evidence |
|---|---|---|
| **B10** | `_normalize_plsql` takes `db_type` and returns non-Oracle input untouched; the `PLSQL` branch walks `cursor.nextset()` for non-Oracle and returns the last result set, naming the others rather than dropping them; `AdhocResult` carries `db_type` so both front ends label the dialect. | `EXEC sp_helptext` returns rows on a real SQL Server; a T-SQL batch prints its `SELECT` under `Bloco T-SQL`; Oracle `EXEC` still expands and captures DBMS_OUTPUT. 7 unit tests on the seam. |
| **B7** | `decrypt("")` returns `""` — a connection saved without a password is not a failure. A non-empty token that will not decrypt now raises a message naming `.dbqm_key` and the command to fix it. | The old path produced `Erro ao conectar:` and nothing else, because `str(InvalidToken())` is empty. |
| **B4** | List panel `2fr` against the detail's `1fr` (min 4, max 9). | Real `DBQMApp` at 80x24: table viewport **3 → 5 rows**; at 120x40, 19 rows against a 9-row detail. |
| **B5** | Not fixable here — it is 1.17.x's behaviour. The class of failure is closed going forward and now proven end to end. | The app boots with an unknown theme in `settings.json` and falls back to `plano-escuro`. |
| **B1** | Widget, export and call site deleted. | `Breadcrumb()` appeared 0 times; the only reference raised into a bare `except` on every package open. |
| **B2** | Field deleted. | `pymssql.connect` has no trusted-connection parameter, so honouring it would mean swapping the driver for pyodbc. A test proves an older `connections.json` carrying `windows_auth` still loads. |
| **B3** | `include_png`, the button and the obsolete test deleted; the "no PNG" assertion kept, with its reason. | All three call sites passed `include_png=False` explicitly; the feature died with the Rich UI layer removed in `bfafdf1`, and no PNG writer exists. |
| **B6** | Autouse fixture points `SETTINGS_FILE` at an empty temp file for that class. | Reproduced first: with `oracle_client_dir` set, the finder returned the user's path. Now passes both with it empty and populated. |
| **B9** | `_branch_ids` skips the test of any `If` whose `orelse` it climbed out of. | Break-tested both ways: `elif "zzz-fuga"` beside an exempt id escaped before, fails now. |

**B8 is not in this table** because it was not fixed: it was closed as not
applicable once the 80-column premise was rejected. The two attempts and their
measurements live in `docs/ARCHITECTURE.md`.

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

## Tier 1 — Pending

**Empty.** All three closed.

| # | Item | How |
|---|---|---|
| **P2** | The TUI could not clear a password | Solved without a new widget, because the premise was wrong: loading a connection already decrypts its password **into the field**, so the box shows what is stored and an empty box means the user emptied it. Treating that as "keep" contradicted the screen they were looking at. Two guards: the field is authoritative only while it is showing *that* connection — typing an existing name into a blank form shows nothing about what is stored — and a password that will not decrypt survives a save, because a blank box there is the screen failing, not the user deciding. |
| **P3** | Release workflow on deprecated Node 20 | `actions/checkout@v4` → `@v7` and `actions/setup-python@v5` → `@v7`. Verified rather than assumed: queried each action's `action.yml` per major and confirmed checkout is node24 from v5 and setup-python from v6. The only recent breaking change in either (`allow-unsafe-pr-checkout`) affects PR checkouts; this workflow checks out a tag. |
| **P4** | Empty-stdin hint named a flag the bundle commands lack | The hint is now derived from the parser — `getattr(args, "no_password", None)` — so it appears where the flag exists and nowhere else. A hand-kept list of which command has which flag would be a second truth waiting to drift. |

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

Tiers 0 and 1 are empty. The next item is **X1** — one machine-readable output
contract — because **C2** (schema discovery) is worth much less without it: an
agent cannot parse a Rich table. X1 also settles the exit-code table that the
`connection` group currently implements alone.

**C11** (HTML report from the CLI) is the only remaining item of effort S with
real value: `core/html_report.py` exists and `-e/--export` simply does not offer
`html`.

One thing to decide when convenient, from the B8 ruling: the design guards and
parts of the recorded debt are calibrated to **80x24**. If that is not a target
width, the reference size is worth changing on purpose rather than leaving the
guards measuring something nobody runs.
