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

**Empty.** The two it held were decided in 2.12.0: a read-only connection is
pinned read-only on the server where the engine allows it (SQL Server has no
such statement and stays a dbqm-side guard), and driver error text has the
connection's password masked before it is published. See `CHANGELOG.md`.

---

## Tier 1 — Pending

**Empty.**

---

## Tier 2 — Toolchain adoption

**Complete.** All five steps from the deviations section of
[`docs/agents/BACKEND-PYTHON.md`](agents/BACKEND-PYTHON.md) have shipped.
**The order was fixed** — that file explains why a type checker before a
lockfile turns the ratchet into a negotiation.

| Order | Step | Effect | Status |
|---|---|---|---|
| 1 | uv + `uv.lock` + `.python-version` | Every later gate runs on a reproducible environment. `requirements.txt` was already gone before this started, not deleted by it. | Done — 2.3.1 |
| 2 | ruff, starting with the rules the code already passes, widening one family at a time | Fills the empty Lint step of the task-completion cycle | Done — 2.3.1, fifteen rule families |
| 3 | mypy `strict` with a per-module ratchet for legacy modules | New code is typed from its first line | Done — 2.3.2, `.github/workflows/checks.yml` runs `uv run mypy` after `ruff`. |
| 4 | pytest strict config (`--strict-markers`, `filterwarnings = error`, `xfail_strict`) | Surfaces warnings the suite currently swallows | Done — 2.3.1 |
| 5 | CI running steps 1-3 on every push | Until it does, the gates are manual and therefore optional | Done — 2.3.2. All three gates (uv sync, ruff, mypy) plus the test suite run on every push to `main` and every pull request. |

**Where typing stands today:** `[tool.mypy] strict = true` in `pyproject.toml`
makes every module strict unless it is named in an `[[tool.mypy.overrides]]`
exemption block. **55 of dbqm's 91 modules are strict**; the remaining **36
are exempt**, each entry carrying the finding count it owes as a debt
register, not just a name. `tests/design/test_typing_policy.py` is what
makes the ratchet real: it fails if the exemption list grows, if an entry
names a module that no longer exists, or if the tracked count drifts from
the list — a module is typed by fixing its findings and deleting its entry,
never by adding one.

Two limits of that gate are worth knowing. It checks `dbqm/` only
(`files = ["dbqm"]`), so `tests/` is outside it while `ruff` covers the whole
tree. And `python_version` is pinned while the platform is not, so a
`sys.platform` branch is only type-checked on a host that takes it —
`core/oracle_client_installer.py`'s darwin and linux branches are skipped by
every Windows run and get their first check on CI. Deliberate: between them
the two hosts cover every branch, which pinning a single platform would not.

The **464 findings at `--strict`, 76 at default** this tier carried in its
planning figures were wrong, and it is worth recording why rather than
quietly replacing them: they were measured with `uvx mypy
--ignore-missing-imports`, and `uvx` runs mypy in an isolated environment
without the project's own dependencies. mypy could not import Textual,
`--ignore-missing-imports` turned every Textual base class into `Any`, and
every class deriving from one produced a phantom "cannot subclass" finding.
Seven of dbqm's eight dependencies actually ship `py.typed`. Measured inside
the project's own environment (`uv run mypy --strict`), the real figure was
**396 findings across 58 modules**; the work in this tier brought that to
**361 findings across 36 modules**. A tool run outside the environment it is
meant to check reports on the isolation, not on the code — worth saying
plainly so the next person does not inherit the wrong number by citation.

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
**Evidence** (`C11`) shipped in 2.4.0 — `--export html` on `run`, `run-group`
and `sql`, a standalone report a human reads without a tool.
Comparison across connections (`C8`) shipped in 2.5.0 — `dbqm multi` runs one
ad-hoc SQL against several databases and reports whether they agree.
**Execution** (`C4`) shipped in 2.6.0 — `dbqm call` runs a stored procedure
or function, Oracle-only, refused before any connection opens on any other
engine. **Curation** (`C5`/`C6`) shipped in 2.7.0 — `dbqm query` and
`dbqm group` create and curate saved queries and comparison groups from the
command line, over the same `core/` rules the TUI screens now call instead
of owning. **`C7` was closed without being built** -- the investigation for
it found both halves already shipped, in commands that do the job for more
object types than a dedicated pair would. See "C7, closed on the evidence"
below. **`C9`/`C10`/`C12`/`X4` shipped in 2.8.0** — `dbqm config get|set|list`,
`dbqm template`, `dbqm oracle-client` and `dbqm describe-cli` — and with them
**Tier 3 is complete**: every item either shipped or was closed on the
evidence above.

**2.1.0 and 2.2.0 are deliberately internal versions.** Both exist in
`CHANGELOG.md` and in the code — discovery and the read-only guard are real,
shipped, tested features — but neither was ever tagged, and neither will be
published to PyPI on its own. That was the maintainer's decision, not an
oversight: whoever installs 2.3.x receives everything 2.1.0 and 2.2.0 added,
already folded in. Recorded here so it is not rediscovered later as a gap in
the release history.

### Tier 3 — the table

**Empty.** All ten items are accounted for: `X1` in 2.0.0, `C2`/`C3` in
2.1.0, `X3` in 2.2.0, `C11` in 2.4.0, `C8` in 2.5.0, `C4` in 2.6.0,
`C5`/`C6` in 2.7.0, and `C9`/`C10`/`C12`/`X4` in 2.8.0. `C7` was closed
without being built — see "C7, closed on the evidence" below.

### C7, closed on the evidence

`C7` proposed `dbqm source` and `dbqm compile`. Its own note asked for the
overlap with `ddl` to be confirmed before building. It was, and both halves
already exist:

- **Reading current source is `dbqm ddl`.** `core/ddl_extractor.py` fetches
  `PACKAGE SPEC` and `PACKAGE BODY` through `DBMS_METADATA.GET_DDL`, falling
  back to `ALL_SOURCE`, and covers nine object types -- `TABLE`, `VIEW`,
  `PACKAGE`, `PROCEDURE`, `FUNCTION`, `TRIGGER`, `SEQUENCE`, `TYPE` and
  `SYNONYM`. `dbqm ddl PKG conn --stdout` already prints the source. A
  `dbqm source` would do less, for fewer types.
- **Compiling with error detection is `dbqm sql`.** `execute_adhoc` runs DDL
  and then calls `_fetch_ddl_errors`, which reads `all_errors` and sets
  `success = not compilation_errors` (`core/query_engine.py:487-502`). This
  matters more than it sounds: Oracle accepts `CREATE OR REPLACE PACKAGE
  BODY` even when the body compiles with errors, leaving the object INVALID,
  so a client that only checked the driver's result would report success.
  dbqm does not. And `dbqm sql` already accepts a path to a `.sql` file, so
  compiling a package from disk works today.

Building the pair would have added a second way to do what one command
already does, and two ways are how they start to disagree -- the failure this
tier spent five sub-projects removing. The id is retired and not reused.

### MCP server, shipped

**MCP server** — shipped in 2.13.0 (`dbqm mcp`, extra `dbqm[mcp]`, eleven
tools over `ops/`, read-only by default). See `docs/MCP.md`.

It had been "Deliberately not scheduled" below: the condition the maintainer
set was that it wrap a settled CLI contract rather than race it, and that
condition was met once the contract (2.0.0), discovery (2.1.0), the
read-only guard (2.2.0), execution (2.6.0) and curation plus the rest of
Tier 3 (2.7.0/2.8.0) had all landed.

### Deliberately not scheduled

**Empty.**

---

## Known gaps

Two things are the way they are on purpose, decided rather than pending:
OUT values of Oracle routines travel back as text (typing them needs real
output binds and an Oracle to test against), and the fields only the TUI
authors (`column_maps`, `normalize`, `column_mapping`, `template_fields`,
`order_by`) have no CLI flag -- `dbqm query update` and `dbqm group update`
preserve them, which is the property that matters.

`sql(explain=true)` on Oracle is expected to be refused by the server under
the read-only session the MCP server forces (`EXPLAIN PLAN` writes
`PLAN_TABLE`); unverified against a real Oracle; `--allow-write` on a
connection with `read_only=false` lifts it.


## Suite hygiene

- **The 3.10 floor is measured, but only by hand.** The suite was run on
  3.10.21 on 2026-09-19: 1769 passed, same as 3.14. So `requires-python =
  ">=3.10"` is a fact rather than a claim, and the floor stays. What is NOT
  in place is anything keeping it true -- `checks.yml` still runs one
  version (whatever `.python-version` pins) and a CI matrix was declined as
  not worth five runners. The next person to use 3.11-or-later syntax will
  find out from a user, not from CI. Repeating the manual run before a
  release is the cheap mitigation; the matrix is the real one, if the cost
  ever stops mattering.

- **`rendered_text` after a thread worker can come back frame-only.** The
  adhoc pilot in `tests/ui/test_functional_screens.py` read the screenshot
  after `wait_for_complete()` + one `pause()`; run after `test_screens.py`'s
  adhoc tests it painted only borders while `#adhoc-result-info` already
  held its row-count line. The pilots read the widget's `content` instead, which
  is the fact the screenshot lags behind. `test_adhoc_controls_do_not_wear_the_frame`
  had the same cold-start shape and took a second `pause()` in 2.9.0;
  one `pause()` is not always a frame.

  **A second instance of the same shape, found and fixed on 3.10.** A widget
  mounted dynamically can receive its own `Mount` before the children its
  `compose` yielded are queryable. `GroupManageScreen.on_mount` queried
  `#gm-table` there and died with `NoMatches` on roughly one run in three on
  3.10, while 3.14 hid it entirely (0 failures in 5). Both it and
  `TemplateManageScreen`, which had the identical shape and had simply not
  lost the coin flip, now do child work in `call_after_refresh`. Worth
  knowing when writing the next tools-hosted screen: `on_mount` is safe for
  the ActionBar, not for your own children.

Not a tier — the sections above are the product's bugs, toolchain and features.
This is the test suite's own upkeep, recorded here because there is nowhere
else a reader would think to look for it.

---

## Suggested next slice

**Tier 0, Tier 1 and Tier 3 are all empty.** The html-export sub-project
(2.4.0), `dbqm multi` (2.5.0), `dbqm call` (2.6.0), saved query/group
curation (2.7.0), the last four Tier 3 commands (2.8.0), SQLite and the QA
review (2.9.0), the hardening slice (2.10.0, which closed seven of the gaps
below) and the move to English as the source language with Portuguese as a
translation (2.11.0) have now shipped. What was left was **decisions**, not
tasks, and all three this list held have been made:

1. **The server-side read-only session** — decided in 2.12.0. A read-only
   connection is pinned read-only on the server where the engine allows it
   (Oracle, PostgreSQL, MySQL, SQLite); SQL Server has no such statement and
   stays a dbqm-side guard.
2. **`to_dict()` publishing driver errors unredacted** — decided in 2.12.0.
   The connection's password is masked in driver error text before it is
   published; the host and `output_lines` were deliberately left alone.
3. **The design guards were calibrated to 80x24** — decided in 3.1.0. The
   reference is 120: the guards and the baseline renders measure it, the
   tests whose premise is a narrow window keep 80, and no layout, CSS or
   elision threshold moved. The CLI's help is laid out for 120 as well.

**A note on estimating, not an apology:** the html item's effort **S** was
measured against `run-group` alone, where `export_group_html` already
existed and `-e/--export` simply needed to offer `html`. It undercounted
`run` and `sql` — `html_report.py` could draw a comparison across named
queries and nothing else, so a renderer for one result set
(`export_query_html`) turned out to be new code, not a wiring change. An
estimate keyed to "the code already exists" is only as good as checking that
it exists for every caller, not just the first one checked.
