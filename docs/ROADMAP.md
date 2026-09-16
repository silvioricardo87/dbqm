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

A **server-side read-only session** (`SET TRANSACTION READ ONLY` on
Oracle/MySQL, `BEGIN READ ONLY` on PostgreSQL) is still deferred, as it was
when the client-side guard (`X3`) shipped in 2.2.0, and `dbqm call` (2.6.0)
did not settle it either. It is a decision, not a task: it would change what
"read-only" means product-wide — a database-side guarantee on Oracle, still
only a dbqm-side promise on SQL Server, which has no server-side equivalent
to reach for.

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

### Deliberately not scheduled

- **An MCP server** (`dbqm mcp`, operations as MCP tools). It is the native shape
  for agent consumption and would remove the shell round-trip entirely — but it
  should wrap a settled CLI contract, not race it. The contract settled in
  2.0.0, discovery landed in 2.1.0, the read-only guard landed in 2.2.0, and
  execution (`C4`) landed in 2.6.0, and curation (`C5`/`C6`, 2.7.0) plus the
  last of Tier 3 (`C9`/`C10`/`C12`/`X4`, 2.8.0) have landed since. The
  condition the maintainer set is met: everything else is done. Whether to
  start it is the maintainer's call.

---

## Known gaps

- **SQLite refuses routines, packages and `call` by design.** It has none;
  the refusal is the same `UnsupportedEngine` PostgreSQL gets. What it also
  does not have is an owner concept, so `_detect_owner` returns `""` and a
  DDL extraction names no schema.
- **`dbqm sql` ignores `--export` unless the statement is a SELECT.** The
  export block sits inside `if result.sql_type == "SELECT"`
  (`cli/commands/query.py`), so a DML, DDL or PL/SQL run accepts the flag and
  silently writes nothing. It predates the output contract and `html`
  inherited it, rather than introducing it. The honest options are to export
  what those statements do return — a row count, DBMS_OUTPUT — or to refuse
  the flag with `usage`; what it must not keep doing is accept and ignore.
- **`run_comparison` is annotated `dict[str, QueryResult]` and has always
  been passed `AdhocResult`** by the Multi-Exec screen. The two are
  duck-compatible, so it works, and mypy misses the mismatch because
  `group_engine.py` sits on the per-module exemption list. The `multi`
  sub-project named the real requirement instead of inheriting the wrong
  one — a `ResultLike` `Protocol` in `core/group_engine.py` — but left the
  old signature as it was. Fixing it means taking `group_engine.py` off the
  exemption list, which is a typing slice, not a feature.
- **The `.sql`-file-path block in `cmd_multi` is duplicated verbatim from
  `cmd_sql`.** Both accept either SQL text or a path to a `.sql` file, and
  both implement it in place. Real duplication, deliberately not fixed
  inside the `multi` feature commit.
- **`run_comparison` collapses duplicate key values — last row wins.** It
  indexes each side as `indexed[qname][key_val] = row_dict`
  (`core/group_engine.py`), so two rows sharing a key value on the same side
  compare as one. Two rows with an all-NULL key column collapse to a single
  entry on that side, and genuinely different data can compare as equal —
  `all_match: true`, exit 0, over rows the comparison never actually told
  apart. This is pre-existing behaviour, not something the `multi`
  sub-project introduced, but `run-group` uses a join key a person curated
  for that specific group, while `multi` derives one from whatever columns
  happen to be common to the connections given — which is what turns this
  from a theoretical gap into one worth hitting in practice.
- **Nothing commits a routine in the TUI.** `execute_routine`'s comment says
  the caller handles commit and, before 2.6.0, no caller did — the TUI
  still does not, so a procedure run from the Executar Rotina screen shows
  "Executado com sucesso" and has its work discarded when the connection
  closes. `dbqm call` handles it with `--commit`; the screen is deliberately
  untouched, because changing a screen from inside a CLI slice is how a
  refactor hides a behaviour change.
- **OUT parameter values are not structured data.** `execute_routine` emits
  them as `DBMS_OUTPUT.PUT_LINE('NOME=' || var)`, so they arrive as ordinary
  text lines, indistinguishable from a line the routine printed itself.
- **The function return value is matched by a `RETURN=` prefix**, which a
  routine printing its own `RETURN=` line would shadow.
- **A standalone routine is only found in the caller's own schema** —
  `get_standalone_routine_info` filters `owner = USER`, while `_detect_owner`
  exists and is used elsewhere. Verifying a routine's existence properly
  belongs here too.
- **The CLI deliberately exposes no flag for `column_maps`, `normalize`,
  `column_mapping`, `template`, `template_fields`, `validation_rule`,
  `is_favorite` or an `order_by` override.** They are TUI-authored, several
  are nested maps with no sane flag shape, and none of them is needed to
  create a query or group an agent will run — but `dbqm query update` and
  `dbqm group update` **preserve** them rather than dropping them, which is
  the property `query_builder.build`/`group_builder.build` exist to
  guarantee.
- **An ad-hoc (Multi-Exec) group cannot be created from the CLI.**
  `Group.adhoc_sql` and `Group.connections` describe a connection
  selection, not a comparison of saved queries; `dbqm multi` runs that flow
  directly and never saves it. `dbqm group update` preserves both fields on
  a group that already has them.

## Suite hygiene

- **`rendered_text` after a thread worker can come back frame-only.** The
  adhoc pilot in `tests/ui/test_functional_screens.py` read the screenshot
  after `wait_for_complete()` + one `pause()`; run after `test_screens.py`'s
  adhoc tests it painted only borders while `#adhoc-result-info` already
  held "3 registros". The pilots read the widget's `content` instead, which
  is the fact the screenshot lags behind. `test_adhoc_controls_do_not_wear_the_frame`
  had the same cold-start shape and took a second `pause()` in 2.9.0;
  one `pause()` is not always a frame.

Not a tier — the four above are the product's bugs, toolchain and features.
This is the test suite's own upkeep, recorded here because there is nowhere
else a reader would think to look for it.

- **`TestCmdRunGroup` can write to the real home directory.**
  `tests/conftest.py` provides `tmp_config_dir`, which redirects every
  config, export and history path into a temp directory. `tests/test_cli.py`
  uses it extensively — but not once inside `TestCmdRunGroup`, which relies
  entirely on per-test `patch("dbqm.cli.deps.X")`. During the html-export
  sub-project, a deliberate mutation left `record_group_execution` unpatched
  and the test wrote a junk entry into the developer's real
  `~/.dbqm/config/history/history.json`. No test in the class is known
  broken today; the class is structurally exposed. The fix is to make
  `tmp_config_dir` autouse for that class, not to patch harder. Effort: S.

---

## Suggested next slice

**Tier 0, Tier 1 and Tier 3 are all empty.** The html-export sub-project
(2.4.0), `dbqm multi` (2.5.0), `dbqm call` (2.6.0), saved query/group
curation (2.7.0) and the last four Tier 3 commands (2.8.0, see
`CHANGELOG.md` for all of them) have now shipped. There is no obvious next
slice any more — what remains is **decisions**, not tasks. For the
maintainer to choose among:

1. **The server-side read-only session** (`SET TRANSACTION READ ONLY` on
   Oracle/MySQL, `BEGIN READ ONLY` on PostgreSQL) — it would change what
   "read-only" means per engine: a database-side guarantee on Oracle,
   PostgreSQL and MySQL, still only a dbqm-side promise on SQL Server, which
   has no server-side equivalent to reach for.
2. **`to_dict()` publishes `error` and `output_lines` unredacted.** A JSON
   payload can echo a DSN, a host, or arbitrary DBMS_OUTPUT. Redaction here
   is a policy call, not an implementation detail.
3. **The design guards are calibrated to 80x24.** If that is not the target
   width, the reference is worth changing on purpose rather than left
   measuring a terminal nobody runs.
4. **The `usage`-versus-`validation` divergence.** `connection add` reports
   `usage` for a duplicate name while `query`, `group` and `template` report
   `validation`. `validation` is the more accurate token, but `connection`
   is published and aligning it is a breaking change — a MAJOR's business.
5. **`TestBuildParser::test_all_commands_have_handlers` keeps a hand-typed
   command set**, edited four times in this sub-project alone.
   `describe-cli`'s parser-versus-dispatch-map set equality is a strict
   superset of what it proves, so retiring the hand-typed test is now
   possible.

**A note on estimating, not an apology:** the html item's effort **S** was
measured against `run-group` alone, where `export_group_html` already
existed and `-e/--export` simply needed to offer `html`. It undercounted
`run` and `sql` — `html_report.py` could draw a comparison across named
queries and nothing else, so a renderer for one result set
(`export_query_html`) turned out to be new code, not a wiring change. An
estimate keyed to "the code already exists" is only as good as checking that
it exists for every caller, not just the first one checked.
