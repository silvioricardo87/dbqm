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
Themes, in the order they unlock each other now: **execution** (C4, C8) is
what an agent does once it can see, and **curation** (C5-C7) is how findings
survive the session.

**2.1.0 and 2.2.0 are deliberately internal versions.** Both exist in
`CHANGELOG.md` and in the code — discovery and the read-only guard are real,
shipped, tested features — but neither was ever tagged, and neither will be
published to PyPI on its own. That was the maintainer's decision, not an
oversight: whoever installs 2.3.x receives everything 2.1.0 and 2.2.0 added,
already folded in. Recorded here so it is not rediscovered later as a gap in
the release history.

| Order | Item | Theme | Effort | Agent value | Notes |
|---|---|---|---|---|---|
| 1 | **C4** — `dbqm call` (execute a routine) | execution | M | high | `execute_routine` already handles IN/OUT binding, return values and DBMS_OUTPUT capture — but is **Oracle-only** (no `db_type`, builds an anonymous PL/SQL block). Ship Oracle-first with a clean refusal, or pay for three more routine models. This is also the sub-project that would build a server-side read-only session (`SET TRANSACTION READ ONLY` on Oracle/MySQL, `BEGIN READ ONLY` on PostgreSQL — SQL Server has no equivalent), deferred here when the client-side guard (`X3`) shipped in 2.2.0. |
| 2 | **C5 / C6** — saved query and group CRUD | curation | M | medium | Follows the `connection_builder` pattern: rules in `core`/`models`, both front ends calling them. |
| 3 | **C7** — `dbqm source` / `dbqm compile` (PL/SQL packages) | curation | S-M | medium | Narrower than it looks — `dbqm sql` already compiles and surfaces errors. What is genuinely missing is *reading* current source. Confirm the overlap with `ddl` and `sql -f raw` first. |
| 4 | **C9 / C10 / C12 / X4** — templates, `config get\|set`, oracle-client, self-description | curation | S-M | low | `config set audit_log_enabled true` is the one an agent flow cares about. |

### Deliberately not scheduled

- **An MCP server** (`dbqm mcp`, operations as MCP tools). It is the native shape
  for agent consumption and would remove the shell round-trip entirely — but it
  should wrap a settled CLI contract, not race it. The contract settled in
  2.0.0, discovery landed in 2.1.0, and the read-only guard landed in 2.2.0;
  revisit once execution (`C4`) has landed too.

---

## Known gaps

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

## Suite hygiene

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

**Tier 0 is empty.** Tier 3's own priority order would put **C4** (`dbqm
call`) next — `execute_routine` already exists and handles IN/OUT binding,
return values and DBMS_OUTPUT capture. **It is Oracle-only**, though: it
takes no `db_type` at all and builds an anonymous PL/SQL block, so C4 either
ships Oracle-first with a clean refusal elsewhere, or pays for three more
routine models. Measured in 2.1.0, when the same discovery was made about
`list_package_routines`.

The html-export sub-project (2.4.0) and `dbqm multi` (2.5.0, see
`CHANGELOG.md` for both) shipped ahead of that order: `--export` is shared
plumbing that every later Tier 3 command touches again, and the Multi-Exec
tab's flow was the most-used one missing from the CLI. With both done,
**C4** (`dbqm call`) is next in the controller's ordering, and carries the
server-side read-only session deferred when the client-side guard (`X3`)
shipped in 2.2.0.

**A note on estimating, not an apology:** the html item's effort **S** was
measured against `run-group` alone, where `export_group_html` already
existed and `-e/--export` simply needed to offer `html`. It undercounted
`run` and `sql` — `html_report.py` could draw a comparison across named
queries and nothing else, so a renderer for one result set
(`export_query_html`) turned out to be new code, not a wiring change. An
estimate keyed to "the code already exists" is only as good as checking that
it exists for every caller, not just the first one checked.

One thing to decide when convenient, from the B8 ruling: the design guards and
parts of the recorded debt are calibrated to **80x24**. If that is not a target
width, the reference size is worth changing on purpose rather than leaving the
guards measuring something nobody runs.
