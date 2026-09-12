# ROADMAP

What to work on next. **Ordered by importance first, grouped by theme inside
each tier.** Bugs outrank everything — a feature built on top of a known defect
is two problems.

Each item carries the evidence that earned it: the file, the line, and what goes
wrong for a user. **An item with no failure scenario is not ready to be worked
on** — that rule is what keeps this list from filling with opinions.

This is the single backlog, and it is **forward-looking**: a shipped item leaves
this file. What was delivered lives in `CHANGELOG.md`; what was measured and must
not be retried lives in `docs/ARCHITECTURE.md` under the known debt.

> Working papers (specs, plans, execution logs) live under `docs/plans/` and
> `docs/superpowers/`, both gitignored. This file is the committed, public one.

---

## Tier 0 — Bugs

**Empty.** Bugs return here the moment one is found, above every feature.

---

## Tier 1 — Pending

**Empty.**

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

Item ids are stable: a shipped one is removed and its number is never reused, so
the sequence below has gaps on purpose. `CHANGELOG.md` says what each release
carried.

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
