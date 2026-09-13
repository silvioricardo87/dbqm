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

**Empty.** Three defects in the CLI's error contract (`B1`-`B3`, unreachable
exit `3`, `rows`/`describe` disagreeing about the same missing name, and
`ddl --stdout` writing to disk anyway) were found while building 2.0.0
through 2.2.0, parked in execution logs rather than here, and shipped in
2.3.0 — see `CHANGELOG.md`. Bugs return to this tier the moment one is
found; it does not stay empty by policy, only by absence of evidence.

### Decision pending, not a defect

`to_dict()` on the `core/` dataclasses publishes `error` and `output_lines`.
Driver error text can echo a DSN or a host, and `output_lines` carries whatever
DBMS_OUTPUT produced. Nothing is redacted, deliberately — redaction here is a
policy call for the maintainer, not an implementation detail. Worth settling
before anything persists that output to a log.

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

The output contract (`X1`) shipped in 2.0.0: `-f json` on every command, one
envelope, errors as structured JSON on stderr, and a stable documented
exit-code table. **Discovery** (`C2`, `C3`) shipped in 2.1.0 — an agent can
now see a database's shape without hand-written catalogue SQL. The read-only
guard (`X3`) shipped in 2.2.0 — a connection can refuse anything but a query.
Themes, in the order they unlock each other now: **execution** (C4, C8) is
what an agent does once it can see, and **curation** (C5-C7) is how findings
survive the session.

| Order | Item | Theme | Effort | Agent value | Notes |
|---|---|---|---|---|---|
| 1 | **C4** — `dbqm call` (execute a routine) | execution | M | high | `execute_routine` already handles IN/OUT binding, return values and DBMS_OUTPUT capture — but is **Oracle-only** (no `db_type`, builds an anonymous PL/SQL block). Ship Oracle-first with a clean refusal, or pay for three more routine models. This is also the sub-project that would build a server-side read-only session (`SET TRANSACTION READ ONLY` on Oracle/MySQL, `BEGIN READ ONLY` on PostgreSQL — SQL Server has no equivalent), deferred here when the client-side guard (`X3`) shipped in 2.2.0. |
| 2 | **C8** — `dbqm multi` (one ad-hoc SQL across N connections, compared) | execution | M | high | The Multi-Exec tab has no CLI equivalent; `run-group` only runs *saved* groups of *saved* queries. For sustainment work this is the most-used flow. Reuses `build_group_result` as-is. |
| 3 | **C11** — HTML report from the CLI | evidence | **S** | medium | `core/html_report.py` exists; `-e/--export` just does not offer `html`. The cheapest item on this list. |
| 4 | **C5 / C6** — saved query and group CRUD | curation | M | medium | Follows the `connection_builder` pattern: rules in `core`/`models`, both front ends calling them. |
| 5 | **C7** — `dbqm source` / `dbqm compile` (PL/SQL packages) | curation | S-M | medium | Narrower than it looks — `dbqm sql` already compiles and surfaces errors. What is genuinely missing is *reading* current source. Confirm the overlap with `ddl` and `sql -f raw` first. |
| 6 | **C9 / C10 / C12 / X4** — templates, `config get\|set`, oracle-client, self-description | curation | S-M | low | `config set audit_log_enabled true` is the one an agent flow cares about. |

### Deliberately not scheduled

- **An MCP server** (`dbqm mcp`, operations as MCP tools). It is the native shape
  for agent consumption and would remove the shell round-trip entirely — but it
  should wrap a settled CLI contract, not race it. The contract settled in
  2.0.0, discovery landed in 2.1.0, and the read-only guard landed in 2.2.0;
  revisit once execution (`C4`, `C8`) has landed too.

---

## Suggested next slice

**Tier 0 is empty**, so the next item is **C4** (`dbqm
call`) — `execute_routine` already exists and handles IN/OUT binding, return
values and DBMS_OUTPUT capture. **It is Oracle-only**, though: it takes no
`db_type` at all and builds an anonymous PL/SQL block, so C4 either ships
Oracle-first with a clean refusal elsewhere, or pays for three more routine
models. Measured in 2.1.0, when the same discovery was made about
`list_package_routines`.

**C11** (HTML report from the CLI) is the only remaining item of effort S with
real value: `core/html_report.py` exists and `-e/--export` simply does not offer
`html`.

One thing to decide when convenient, from the B8 ruling: the design guards and
parts of the recorded debt are calibrated to **80x24**. If that is not a target
width, the reference size is worth changing on purpose rather than leaving the
guards measuring something nobody runs.
