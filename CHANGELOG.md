# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases before 1.18.0 predate this file; their history is in the git log.

## [2.13.0] — 2026-09-20

### Added

- `dbqm mcp` — an MCP server over stdio (extra `dbqm[mcp]`), eleven tools
  (`list`, `test_connection`, `objects`, `describe`, `rows`, `ddl`,
  `history`, `run`, `run_group`, `multi`, `sql`) that call the same `ops/`
  functions the CLI calls and answer with the CLI's envelope; read-only by
  default, `--allow-write` and `--connection` at start. See `docs/MCP.md`.
- `tests/design/test_mcp_parity.py` pairs every tool with its command.

### Changed

- The `multi` and `run-group` JSON shapes are built by `ops/compare`
  (`multi_data`, `run_group_data`); output unchanged.
- History writes go through a temp file and an atomic replace, audit writes
  are lock-serialised appends; the MCP server runs tools in worker threads
  and the CLI never raced either file. `add_history_entry` holds the same
  lock across load, insert and save, and `load_history` now takes it too,
  so a reader can no longer see the file mid-replace.
- `ops/schema` reports a connection failure through the password masker,
  like `sql` and `run` already did.

### Fixed

- A read-only connection refuses `SELECT ... INTO` (a table on SQL Server
  and PostgreSQL, a file on MySQL); it was classified as a plain SELECT.

## [2.12.1] — 2026-09-20

### Fixed

- `dbqm ddl` for an object that does not exist exits 2 (`not_found`) in
  table format too; it exited 4 there while `-f json` already said 2 --
  one exit code regardless of format, as `describe` and `rows` do. Under
  `-f table` the errors print as one line.
- `dbqm run --export` embeds the parameters the query actually ran with,
  its declared defaults included, in the file name and the file body.

### Changed

- The logic of eleven CLI commands (`test`, `list`, `history`, `objects`,
  `describe`, `rows`, `ddl`, `sql`, `run`, `multi`, `run-group`) lives in a
  new operations layer, `dbqm/ops/`, as functions that return values and
  raise `OperationError` with the same `error.code` tokens. The CLI's
  output, exit codes and refusal order are unchanged: `tests/functional/`
  passes as before. This is the ground the MCP server (next minor) stands
  on.
- `dbqm/cli/deps.py` is `dbqm/ops/deps.py`. Tests patch the new path.
- `dbqm run-group --export` builds its file from `Comparison.params`, the
  parameters the comparison actually ran with (a group's `shared_params`
  defaults included); no behaviour change versus 2.12.0.
- A failed DDL under `dbqm sql -f table` no longer prints the
  elapsed-seconds line next to its compile errors; the message and exit
  code are unchanged.
- The unused catalogue key `sql.ddl_compile_errors` is removed.

## [2.12.0] — 2026-09-19

A MINOR release: the roadmap's two open decisions, decided and shipped, and
the test suite made honest about the Python floor it promises.

### Added

- **A read-only connection is read-only on the server.** Until now the
  guard was dbqm's own classification: it refused to send anything but a
  query, and nothing else stood in the way -- a routine that writes
  internally, a DDL that commits itself, another client on the same handle.
  The connection is now also pinned read-only the moment it opens, where
  the engine allows it: `SET SESSION CHARACTERISTICS AS TRANSACTION READ
  ONLY` on PostgreSQL, `SET SESSION TRANSACTION READ ONLY` on MySQL, `SET
  TRANSACTION READ ONLY` on Oracle (per transaction: it holds for the
  statement dbqm is about to run and ends at a COMMIT inside a routine),
  `PRAGMA query_only` on SQLite. **SQL Server has no such statement** and
  stays a dbqm-side guard; `--help` and the docs say so rather than
  pretend. `--force-write` opens the connection unpinned, which is why it
  can write at all. Proven end to end on SQLite: an INSERT sent straight to
  the handle, past every dbqm check, is refused by the engine.
- **`dbqm group add --adhoc-sql "..." --connection a --connection b`** creates
  the other shape of a group -- one statement over a set of connections,
  exactly what Multi-Exec saves -- and **`dbqm run-group` runs it**, which
  it could not before even for a group the TUI had saved. It runs through
  the same path as `dbqm multi` (same refusals, same derived join key,
  reported back as `join_key`), exits 5 on divergence like every other
  comparison, and is recorded in history under the group's name. An
  ad-hoc group needs two or more distinct connections that exist; a group
  file carrying both shapes is not refused -- `adhoc_sql` decides, here
  and in `run-group`.

### Fixed

- **The connection's password never travels in an error message.** Every
  `error` the CLI publishes is built from `str(e)` of whatever the driver
  raised, and a driver is free to echo the DSN it was given. `error_text`
  now builds all of them, masking the password when it appears; the host
  is not a secret (`connection show` prints it) and `output_lines` is the
  routine's own text, so neither is touched. This closes the roadmap's
  `to_dict()` decision: redact the one thing that is a secret, say what is
  deliberately not.
- **The 3.10 floor is measured, not claimed.** The suite had never run on
  3.10 -- and could not: a test imported `tomllib`, which arrived in 3.11,
  so collection failed before a single test ran. With `tomli` declared for
  older Pythons the suite ran, and passed everything but a handful of UI
  tests that read layout after a fixed number of `pause()` calls: a bet on
  the interpreter's speed, won on 3.14 and lost on 3.10. Those read the
  fact they assert now (`wait_until`, in `tests/ui/_helpers.py`). Three
  latent races in the product's own screens came out of it too -- a
  `Mount` that arrives before the children it composed are queryable --
  in `GroupManageScreen` and `TemplateManageScreen`. 1789 passed on both
  versions. A CI matrix was declined as not worth five runners; the run
  is manual, and the roadmap says so.
- **Two tests that passed for free.** The no-notice-on-startup test
  compared against Portuguese notice texts no screen paints, and the
  `describe`/`rows` fixture path carried `ds-background` in the middle of
  it -- left by an old blanket rename that replaced the word `fundo` inside
  a string. Both fixed; the first now resolves its notices by catalogue
  key and was proven able to fail.
- **Sixteen more assertion messages and two docstrings** were still
  Portuguese, behind words the earlier sweep's list did not have (`sem`,
  `fora`, `abaixo`).

### Changed

- The roadmap's "Decision pending" section and three of its known gaps
  are closed: typed OUT values are accepted as text (an Oracle to test
  against would be the price of doing better), and the fields only the
  TUI authors keep having no CLI flag, `update` preserving them being the
  property that matters. `--favorite`, which the roadmap said had no
  flag, has had one since 2.7.0.

## [2.11.1] — 2026-09-19

A PATCH release: documentation that had fallen behind 2.11.0, one `--help`
string that was wrong, and the licence file the project always claimed to
have.

### Fixed

- **`--explain`'s help text omitted SQLite.** It named Oracle, PostgreSQL and
  MySQL; SQLite has answered with `EXPLAIN QUERY PLAN` since the engine was
  added. The only code change in this release.
- **`docs/CLI.md` showed output the program no longer produces** — the
  read-only JSON envelope, the `describe` table (`Coluna | Tipo | Nulo`) and
  the `rows` footer (`3 registros em 0.61s`), all transcribed before English
  became the source language. Recaptured from a real run.
- **Sample names and screen names had moved.** The README, `PYPI.md` and
  `docs/CLI.md` still used a Portuguese sample schema next to English
  screenshots; `docs/ARCHITECTURE.md` named tabs by labels that no longer
  exist; the README and `PYPI.md` listed the eight tabs in the wrong order;
  and five QA scenarios quoted test fixtures that had been renamed.

### Added

- **`LICENSE`.** `pyproject.toml` declared MIT and the README said so, but the
  file was never in the repository, so GitHub detected no licence at all.
- **A capability table per engine** in the README, and connection examples for
  SQL Server, MySQL and PostgreSQL before the SQLite one. The table is checked
  against the dispatch in `ddl_extractor.py` and `query_engine.py`: SQL Server
  has neither DDL extraction nor an execution plan, and SQLite does have one.
- **Badges** — PyPI version, supported Pythons, CI, licence and downloads.

### Changed

- The README leads with the five engines and gives the CLI its own section
  before the TUI.

## [2.11.0] — 2026-09-18

A MINOR release: dbqm speaks English, and Portuguese became a translation.

Every string a user reads — the TUI, the CLI's messages, its `--help`, the
headers of exported files and HTML reports — now comes from a catalogue in
`dbqm/i18n/` instead of being written into a widget. English is the source
language and the default; `pt.py` is the Portuguese translation, still
without accents.

```bash
dbqm config set language pt     # or: en
DBQM_LANG=en dbqm run sales -f json
```

### Added

- **`language` setting**, resolved as `DBQM_LANG` > stored setting >
  English. An unknown value falls back to English rather than refusing to
  start: a typo in a config file should not stop the program.
- **`dbqm/i18n/`** — a catalogue of ~640 keys per language, `t("key")` to
  read one. A key with no translation falls back to English, so a new
  language is usable before it is finished.
- **Six design guards**: screen text must come from the catalogue (by
  where a string goes, not by what it says); `t()` must not run at import
  time; catalogue values carry no Rich markup; every language carries every
  key English defines, with the same placeholders and no accents in
  Portuguese; every `t()` call passes exactly the fields its key declares;
  and the old word-list ratchet stays at zero.

  What counts as a place a string *goes* was widened by what it kept
  missing: `console.print`, every positional of `add_row` and
  `add_columns`, `ProgressIndicator.start` and `Static.update`, the calls
  that forward to a sink named by their first argument
  (`call_from_thread`), the fields of a `t()` call, a name followed one
  step back to the literal its own scope assigns it, and both branches of
  a conditional. Each rule was added because something got past the one
  before it, and each was proven to fail before it was trusted.

### Fixed

- **`dbqm ddl` classified a missing object differently per engine.**
  `ddl_pg` and `ddl_mysql` reported the object as not found but never set
  `result.not_found`, so the same condition exited `not_found` (2) on
  Oracle and SQLite and `sql_error` (4) on PostgreSQL and MySQL. Both tests
  covering the path asserted the message and never the flag, which is how
  four engines disagreed in silence.
- **Three places classified an outcome by reading their own message.**
  Matching English or Portuguese text to decide an exit code is correct in
  one language and silently wrong in every other; they read `error_kind`
  and `result.not_found` now.
- **Five confirmation prompts accepted only the Portuguese "s".**
  `connection`, `query`, `group`, `template` and `oracle-client` each
  hard-coded the affirmative, so in English the prompt would have said
  `[y/N]` and refused `y`. They read `common.yes_answers`.
- **Six alignments were computed from the length of a Portuguese word** —
  the CLI's comparison summary, the flat export's status column, the
  evidence header's colons, the TUI's comparison summary, the shortcut
  sheet's key column and the ad-hoc connection prompt. Each measures the
  widest label in the language in use, and the two that a test can catch
  now run once per language.
- **Both HTML reports declared `<html lang="pt-BR">`** whatever they
  contained, which misleads a screen reader and makes a browser offer to
  translate what is already translated.
- **The template engine wrote Portuguese into a rendered template.**
  `{{n}}` mapped to `query:X:_count_label` came back as `3 registros`, and
  `_status` answered `VAZIO`. Worse than the language: the plural rule was
  a Python expression (`registro{'s' if n != 1 else ''}`), so how many
  plural forms a language has was a decision the code had made. It is one
  key per number now.
- **Fifteen more strings a screen paints**, each behind a shape no guard
  was looking at: a table's `add_columns` header row (the package editor's
  templates, the column maps, the Instant Client lists), the vertical
  result view's `Registro N`, the group manager's `(sem pasta)`, the
  mapping toggle's `Original`/`De-Para`, and `dbqm describe-cli`'s
  `sim`/`nao` Required column. `dbqm config set` also accepted `sim`/`nao`
  for a boolean and not `yes`/`no`; it takes both now, because that is
  input tolerance rather than screen text, and a script written when the
  CLI was Portuguese must keep working.
- **A design guard had gone quiet.**
  `test_empty_state_is_not_hand_written` looks in `dbqm/ui/` for the word
  `Nenhum...` inside a `Static(...)`; since the catalogue, that word lives
  in `dbqm/i18n/` and the scan matched nothing, passing for having nothing
  to look at. It resolves the key now and reads the sentence, which
  immediately turned up two status readouts that needed a written
  exemption.
- **Thirty-odd sentences never reached the catalogue at all**, because
  none of them was written at the call that paints. The history table said
  `grupo` while the detail panel beside it and `dbqm history -f table`
  printed the stored `group` — one field, two languages, one screen. Six
  progress messages arrived through `ProgressIndicator.start`. Thirteen
  errors were forwarded through `call_from_thread`, whose own name says
  nothing about where the text lands. `dbqm connection test` handed
  `"desconhecida"` to a translated sentence as a field. Each shape is now
  a rule in the guard, proven to fail before it was trusted.

### Changed

- The TUI's connection outcomes reuse the CLI's sentences, losing an
  exclamation mark: two catalogue entries for one sentence is not worth a
  translator's confusion.
- `consultas/` and `grupos/` stay Portuguese in every language. They are
  directories on disk; translating them would write the next export beside
  everything already there.

## [2.10.0] — 2026-09-17

A MINOR release: seven recorded gaps closed, and the comparison engine
stops answering about rows it never told apart.

### Fixed

- **`run-group` answered CONSISTENTE without comparing anything.**
  `--compare-column` is optional, and a group that names none produced zero
  `ComparisonResult` — which makes `all(...)` vacuously true: `all_match`,
  exit 0, over data nothing ever looked at, while the equivalent `multi`
  exited 5 on the same rows. The columns are derived the way `multi` derives
  them, the caller is told that is what happened, and a comparison with
  nothing common beyond the key is refused instead of answered.
- **A group could name the same query twice.** `run_comparison` keys its
  index by query name, so the repeat collapsed to one side and the group
  agreed with itself — `equal_count` over a comparison that never had two
  sides. `multi` has always refused the same shape for a repeated `-c`.
- **`-p` with a name the statement never declared was accepted and ignored.**
  A typo ran unfiltered and the rows came back as a result. `run`, `sql` and
  `multi` refuse it now, as `call` always has. `run-group` is deliberately
  left alone: its `shared_params` cross several queries and a parameter some
  of them do not use is the point.
- **`history -n 0` meant 20 and `-n -5` meant "all but the last five".**
  Both fell through to slicing. `-n` below one is `usage`, the way `rows`
  has always validated `--limit` and `--offset`.
- **A `.sql` path that does not exist was read as SQL**, so a typo in the
  filename came back as "Tipo de SQL nao suportado". It is `not_found`,
  naming the file.
- **`export-config` excluding every kind still wrote a bundle** carrying
  nothing but its own salt, and reported a successful export.
- **`dbqm sql` accepted `--export` and silently wrote nothing.** The export
  block sits inside the SELECT branch, so `dbqm sql "UPDATE ..." c --commit
  -e csv` wrote the row, wrote no file, and said nothing about either. A
  statement type that returns no rows now refuses the flag with `usage`,
  **before it runs** — refusing afterwards would mean the write happened and
  the caller still got exit 2. A PL/SQL block is the one type whose result
  set is not knowable from its text, so it is judged after the fact: a block
  that returned rows exports them.
- **A comparison could report `all_match: true` over rows it never compared.**
  `run_comparison` indexes each side by the join key, and a second row under
  the same key overwrote the first. It still keeps the last row — comparing
  as multisets is a redesign, not a fix — but the rows it dropped are now
  counted in `comparisons[*].duplicate_rows` and every caller warns, naming
  the key and the side. `dbqm multi` derives its key from whatever columns
  the connections share, which is what made this worth hitting.
- **A standalone routine was only found in the caller's own schema.**
  `all_arguments` was filtered by `owner = USER`, so a routine the caller
  can execute but does not own came back with no arguments at all —
  indistinguishable from a real zero-argument procedure, and the block was
  then built without its parameters. The owner is resolved from
  `all_objects` first, which answers two more questions in the same round
  trip: whether the name exists, and whether it is a PROCEDURE or a
  FUNCTION — which the CLI had to guess at.
- **The TUI never committed a routine.** `execute_routine` leaves the commit
  to its caller; `dbqm call` has `--commit` and the Executar Rotina screen
  had nothing, so it reported "Executado com sucesso" over work the driver
  discarded at close. The screen has a `Confirmar alteracoes (commit)`
  checkbox, off by default, and the result panel now always says which of
  the two happened.
- **`dbqm sql --explain` accepted `--export` and ignored it.** The explain
  branch returns before everything else, so the flag never reached the
  guard above — the same "accepted and ignored" this release set out to
  remove, one branch further up. A plan is a result set (`plan`, one row
  per line) and is now exported like any other.
- **The export refusal jumped ahead of the read-only one.** On a read-only
  connection, `sql "UPDATE ..." ro -e csv` reported the flag, sending the
  caller to drop it and only then meet the real obstacle — the two round
  trips the `--commit` ordering exists to avoid. The connection's refusal
  comes first.
- **The comparison screens were silent about a repeated key.** The CLI
  warned and the TUI did not, over the same wrong answer. Both screens
  notify now, with the wording the CLI uses: it lives in
  `group_engine.duplicate_key_warnings`, read by all three.
- **OUT values and a function's return were indistinguishable from output.**
  They arrived as bare `NOME=valor` lines mixed into whatever the routine
  printed, so a routine printing its own `RETURN=...` shadowed the real
  return value. They travel under a marker generated per execution and
  arrive in `data.out_values`; `warnings` now holds only what the routine
  printed.

### Changed

- **`comparisons[*]` gained `duplicate_rows`** in the `run-group` and `multi`
  envelopes, and both commands may now emit `warnings`. Additive: a consumer
  reading the existing keys is unaffected.
- **`GroupResult` carries the `join_key` it was compared on**, and publishes
  it in `to_dict()`. An ad-hoc comparison derives its key, and the result
  had no way to say which column that had been — which is what a warning
  naming the key needs.

### Internal

- `dbqm.core.group_engine` comes off the mypy exemption list — 35 modules
  left, and `ResultLike` replaces the `dict[str, QueryResult]` annotation
  that had always been passed `AdhocResult`.
- `dbqm sql` and `dbqm multi` share one reader for "SQL text, or a path to a
  `.sql` file", and one exporter for an `AdhocResult`'s rows.
- `TestCmdRunGroup` isolates the config paths for every test in the class: it
  relied on per-test patching, and a mutation that left one call unpatched
  once wrote into the developer's real `~/.dbqm`.
- `TestBuildParser`'s hand-typed command set is gone — the parser's own
  subparsers are the source, which is what it was trying to say.
- The QA traceability ratchet accepts `tests/ui/test_functional_screens.py`
  as a `functional` source: it drives the real screens against the real
  database and patches nothing, which is what makes a row functional. The
  five TUI pilots are traced from the documents now — 216 scenarios, 186
  functional.

---

## [2.9.0] — 2026-09-15

A MINOR release: SQLite is the fifth engine.

### Added

- **SQLite as an engine.** `dbqm connection add local --type sqlite
  --database ./meu.db` and every engine-agnostic command runs against it —
  `run`, `run-group`, `multi`, `sql` (SELECT, DML with `--commit`, DDL,
  `--explain` via `EXPLAIN QUERY PLAN`), `objects`, `describe`, `rows`,
  `ddl`, and the `--export` formats. `:memory:` is accepted. The whole
  configuration is one file: a host, port, user or password typed for it is
  refused by name rather than ignored, and the connection form hides those
  fields when SQLite is chosen. A zero-setup local database, and the ground
  the functional test suite stands on.
- **The `mysql` extra.** `_connect_mysql` has imported `pymysql` since the
  engine was added; no extra installed it. `pip install dbqm[mysql]` now
  does.

### Fixed

- **`dbqm ddl` sent Oracle catalogue SQL to every engine.** `extract_ddl`,
  the function the command calls, had no notion of engine: a PostgreSQL or
  MySQL connection was asked `all_objects` and `all_synonyms` questions and
  answered with a driver error. Only the TUI's browser screen knew to route
  to `ddl_pg` and `ddl_mysql`. The dispatch now lives in `extract_ddl`,
  once, and SQL Server — which has no extractor — is told so instead.
- **The read-only guard refused SQLite's `EXPLAIN QUERY PLAN`.** A
  hand-written `EXPLAIN QUERY PLAN SELECT ...` on a read-only connection was
  reported as an EXPLAIN that executes what it explains: the prefix regex
  knew PostgreSQL's, MySQL's and Oracle's shapes but not SQLite's.
  `--explain` was never affected. Found by QA-RO-005.
- **`connection list` printed an empty target for SQLite.** `display_target`
  fell through to `host`; the file is now the target. Found by QA-CONN-008.
- **`import-config` on a path that does not exist** surfaced the OS's
  localised error text under `validation`, after asking for the password.
  It is `not_found`, in dbqm's words, before the prompt. Found by QA-PORT-006.
- **The TUI browser's DDL extraction routed engines itself.** It refused
  SQLite as unsupported and, before 2.9.0's `extract_ddl` dispatch, sent
  everything that was not PostgreSQL to the MySQL extractor. It now calls
  `extract_ddl` for every non-Oracle engine: SQLite extracts, SQL Server is
  told there is no extractor. Two TUI pilots prove both.
- **`test_adhoc_controls_do_not_wear_the_frame` failed on a cold start** —
  one `pause()` before reading the frame; it takes two now.

### Changed

- **`dbqm connection add` on a name that already exists reports
  `validation`**, as `query add`, `group add` and `template add` always did.
  It said `usage`; the exit code is 2 either way, and a name collision is not
  a malformed invocation. A consumer branching on the token for this one
  case sees a different word — the number it branches on is the same.

### QA

- **`docs/qa/`** — one document per feature, 18 in all, 183 scenarios written
  as `Dado / Quando / Entao` with the exact command and the exact token or
  string expected. Every scenario names the test that proves it or says
  `manual` and carries the commands for whoever has the Oracle. The index in
  `docs/qa/README.md` is counted from the documents.
- **`tests/functional/`** — 183 tests that run `run_cli` against a seeded
  SQLite file and patch nothing (`test_harness.py` reads the folder and
  refuses a `patch("dbqm.cli.deps` in it). Every exit code the CLI produces
  is produced by a real condition: 0; 2 for each of `usage`, `not_found`,
  `validation`, `read_only`; 3 from a database path that is a directory;
  4 from a missing table; 5 from two files that disagree in one row. Every
  export format on every exporting command is opened and read. Before this
  release, no CLI test ran a command against a database.
- **The traceability ratchet** (`tests/design/test_qa_traceability.py`) fails
  on a `functional` row that says `—`, on a referenced test that does not
  exist, on a `functional` row pointing outside `tests/functional/`, and on
  an ID used twice.
- **Five TUI pilots that execute** (`tests/ui/test_functional_screens.py`):
  `query_exec`, `adhoc`, `group_run` and the browser's DDL run against the
  real SQLite file and read the result back from the widget. The first UI tests that do more
  than render.
- The suite went from 1479 tests to 1680: 183 functional, 9 in the ratchet,
  5 pilots, and the unit cases the fixes above brought.

### Notes on the design

- **What SQLite refuses, and why.** Packages, stored routines and
  `dbqm call` are refused with the same `UnsupportedEngine` message
  PostgreSQL gets: an anonymous PL/SQL block has no equivalent, and an empty
  list would read as "none here" instead of "does not apply here".
  `get_standalone_routine_info` and `execute_routine` took an open handle
  rather than a `Connection`, so nothing had stopped them from sending
  PL/SQL to any engine; both now check the engine first.
- **The engine tests stopped pretending.** They used to patch
  `get_connection` to hand in an in-memory SQLite handle and then patch the
  connection's `db_type` to `"oracle"` so the bind path would accept
  `:name` — the code believed it was talking to Oracle. They now open a real
  SQLite file through the engine's own path, with nothing patched.
- **PRAGMA takes no bind parameters**, so in the one place a table name
  reaches SQL as text the catalogue refuses anything that is not a plain
  identifier rather than interpolating it.

## [2.8.0] — 2026-09-15

A MINOR release: four new command groups, and with them Tier 3 of the
roadmap is complete.

### Added

- **`dbqm config get|set|list`** — reads and writes what dbqm stores. Valid
  keys come from `Settings`' own fields and valid themes from the design
  tokens, both read at runtime, so neither list can go stale. A bad value is
  **refused, not coerced**: `dbqm config set audit_log_enabled talvez` fails
  and leaves the setting alone. `get -f json` returns the real type, so a
  caller branching on a boolean gets `true`, not `"true"`. A non-empty
  directory setting that does not exist is refused too — that setting exists
  to override auto-detection, and a typo there would otherwise surface much
  later as a confusing connection failure instead of at the point it was set.
- **`dbqm describe-cli`** — emits dbqm's own command surface as JSON, walking
  the same `argparse.ArgumentParser` the CLI dispatches through and
  recursing into nested subcommands with their own arguments. Nothing about
  the surface is written down twice, so a command or flag added later
  appears without anyone updating this one.
- **`dbqm template add|update|show|rm|list`** — creates and curates report
  templates from the command line, over a new `core/template_builder.py`,
  the third module of the `validate`/`build`/`upsert` shape
  `connection_builder.py`, `query_builder.py` and `group_builder.py` already
  share. `content` (from `--content` or `--content-file`) is stored
  **verbatim**, never stripped — whitespace in a report body is formatting —
  but content that is *only* whitespace is still refused.
- **`dbqm oracle-client list|available|install|rm`** — manages Oracle
  Instant Client installations from the CLI, the last thing the TUI's
  Oracle Clients screen could do that scripted use could not. `install` is
  the only command in dbqm that reaches the internet; a failed download or
  extraction is reported as `unexpected` (exit `1`), and an unsupported host
  as `usage` (exit `2`), naming the platform.

### Notes on the CLI surface's design

These are properties the four command groups have from their first release,
not fixes to anything a user of 2.7.0 could have run — nothing in this
branch shipped before.

- **`config set` validates before writing, never after.** A key that does
  not exist on `Settings`, a theme not in the design tokens, a boolean that
  is not one of `true/false`, `1/0`, `sim/nao`, or a non-empty directory
  that does not exist on disk — all are refused with `validation` (or
  `not_found` for an unknown key) before `settings.json` is touched, so a
  rejected `set` never leaves the file half-changed.
- **`describe-cli` reports nothing about the surface by name.** Every
  command's arguments are read the way argparse itself reads them to print
  `--help` — no hand-typed list of command or flag names lives inside the
  module, so the description cannot drift from what the parser actually
  builds.
- **`template`'s `add`/`update` share one field-adding helper with the
  same `--content`/`--content-file` mutual-exclusion shape** `query`
  already uses for `--sql`/`--sql-file`, and `update` preserves `content`
  and `description` it is not asked to change, the same guarantee
  `query_builder.build`/`group_builder.build` already give their own
  records.
- **`oracle-client install`'s download progress goes to stderr**, the same
  routing `dbqm ddl` uses for its per-object progress, so the `-f json`
  envelope on stdout stays parseable while a long download is running.
  `rm` refuses under a non-terminal stdin rather than hanging on an
  unanswerable confirmation prompt, matching `connection rm`/`query
  rm`/`group rm`/`template rm`.

## [2.7.0] — 2026-09-15

A MINOR release: two new command groups.

### Added

- **`dbqm query add|update|show|rm|list`** — creates and curates saved
  queries from the command line. `add NOME --sql "..." --connection prod`
  (or `--sql-file`, mutually exclusive with `--sql`) needs a name, SQL and a
  connection that exists; `update` changes only the flags given, `show`
  prints one query, `rm` removes one (confirms unless `--yes`, refuses
  outright rather than prompting when stdin is not a terminal), `list`
  lists them, optionally filtered by `--connection`.
- **`dbqm group add|update|show|rm|list`** — creates and curates comparison
  groups from the command line. `add NOME --query q1 --query q2 --join-key id`
  needs a name, at least two `--query` and a join key; every query named
  must exist. `--compare-column` repeats to narrow which columns are
  compared. Same `update`/`show`/`rm`/`list` shape as `query`.
- Both groups are modelled on `dbqm connection`: `-f json` everywhere, the
  same `add`/`update`/`show`/`rm`/`list` verbs, `rm` confirming unless
  `--yes`, and a non-terminal stdin refusing rather than hanging on a
  prompt.
- **Two new `core/` modules**, `query_builder.py` and `group_builder.py`,
  mirroring `connection_builder.py`'s `validate`/`build`/`upsert` split.
  Until now this validation and assembly lived inside the TUI's
  `query_manage.py` and `group_manage.py` screens, so a second front end
  could only reach it by copying the rules and risking them drifting apart.
  The screens now call the same `core/` functions the CLI calls, with no
  observable change to either one. They do gain one refusal apiece — a group
  naming a query that no longer exists — which is the point of sharing the
  rule rather than copying it, and which is unreachable through the widgets,
  since those only ever offer records that exist.

### Notes on the CLI surface's design

These are properties the two command groups have from their first release,
not fixes to anything a user of 2.6.0 could have run — nothing in this
branch shipped before.

- **The CLI deliberately exposes no flag for `column_maps`, `normalize`,
  `column_mapping`, `template`, `template_fields`, `validation_rule`,
  `is_favorite` or an `order_by` override.** They are TUI-authored, several
  are nested maps with no sane flag shape, and none is needed to create a
  query or group an agent will run. `update` **preserves** them rather than
  dropping them on a record that already has them — the property
  `query_builder.build`/`group_builder.build` exist to guarantee, the same
  way `connection_builder.build` already guarantees it for connections.
- **An ad-hoc (Multi-Exec) group cannot be created from the CLI.**
  `Group.adhoc_sql` and `Group.connections` describe a connection
  selection, not a comparison of saved queries — `dbqm multi` runs that
  flow directly and never saves it. `group_builder.build` preserves both
  fields on an `update` of a group that already has them, for the same
  reason it preserves the TUI-only fields above.

## [2.6.0] — 2026-09-13

A MINOR release: a new command.

### Added

- **`dbqm call PACOTE.ROTINA <conexao> [-p nome=valor] [--commit]`** — calls
  a stored procedure or function from the command line. A name with a dot
  is `PACOTE.ROTINA`; a bare name is a standalone routine. Parameters are
  bound by name and **case-insensitively** — Oracle declares `P_ID`, and
  `-p p_id=7` is not a mistake. **Oracle only**, refused with `usage` (exit
  2) before any connection is opened: `db_type` is known from configuration
  alone, and an anonymous PL/SQL block — what `execute_routine` builds — has
  no equivalent on the other three engines.
- **`--commit`**, meaning what it means on `dbqm sql`: without it the
  transaction is explicitly rolled back, with it committed — and the output
  says which, in both the table and the `-f json` renderers. A routine that
  raises is rolled back regardless of the flag.

### Notes on `dbqm call`'s design

These are properties the command has from its first release, not fixes to
anything a user of 2.5.0 could have run. They are recorded because each was
a trap found and closed while building it, and the next person reading this
code will want to know why it is shaped this way.

- **A standalone function is re-tagged before it runs.**
  `get_standalone_routine_info` takes a `routine_type` argument and honours
  it, but `dbqm call` has no way to know which it is before looking, so it
  calls the lookup with the default and re-tags from the `return_type` the
  lookup fills in. Without that, `execute_routine` would declare no return
  variable and Oracle would answer PLS-00221. The TUI was never affected —
  it passes the real type, because the user picked it from a list.
- **A routine that cannot be found is not guessed at.** An empty
  `ALL_ARGUMENTS` result is indistinguishable from a procedure that simply
  takes no arguments, so `dbqm call` does not treat it as "does not exist":
  a name that truly does not exist comes back as Oracle's own PLS-00201
  (`sql_error`, exit 4) rather than a client-side guess that would have
  refused every zero-argument procedure.
- **Parameter names are folded to the routine's declared spelling** before
  they reach `execute_routine`, which looks them up by exact name and falls
  back to the parameter's default. Without the fold, `-p p_id=7` against a
  declared `P_ID` would have run the routine on its default instead of the
  value given.
- **A routine that raises, and a commit that fails, are rolled back
  explicitly** rather than left to the driver's close-time behaviour. The
  block may have executed in part before either happened, and a caller who
  omitted `--commit` is told plainly that the transaction was undone.

## [2.5.0] — 2026-09-13

A MINOR release: a new command.

### Added

- **`dbqm multi "<sql>" -c prod -c homolog [-c ...]`** — runs one ad-hoc SQL
  across several connections and compares the results. This is the flow the
  TUI's Multi-Exec tab has always had and the CLI never did; `run-group`
  only ever ran *saved* groups of *saved* queries. At least two connections
  are required. `--key` overrides the join column, and the key actually
  used is reported — in the `-f json` envelope and in the `-f table`
  header — because a key derived by a rule the caller cannot see turns
  every number downstream into a guess. Exits `5` on divergence like
  `run-group`, `3` when a database never answered, `4` when one answered
  and rejected the statement, `2` for a usage, not-found or validation
  failure. A failed connection stops the command and exports nothing: a
  comparison over a subset silently answers a different question than the
  one asked. (The ad-hoc comparison itself moved out of
  `ui/screens/group_exec.py` and into `core/` in 2.4.1, precisely so a
  second front end could reach it — this is that front end.)
- **`_export_group`** (`cli/commands/query.py`) — the group export is now
  one code path shared by `run-group` and `multi`, rather than a branch
  copied per command.

### Fixed

- **`multi` refuses, rather than answers, three shapes of comparison that
  would compare nothing:** an explicit `--key` naming a column not common
  to every result; a set of results sharing exactly one column; and `--key`
  naming that sole column. All three previously produced "everything
  matches" over data never compared.
- **`multi` refuses SQL that is not a query, before opening a single
  connection.** It had no `--commit` gate the way `cmd_sql` does, so
  `multi "DELETE FROM t" -c prod -c homolog` ran the delete on every
  connection (uncommitted) and only then failed with "no comparable
  columns" — a comparison has no result set to compare when the statement
  never returns one. Refuses DML, DDL and PL/SQL with `usage` up front;
  allows only `SELECT` and `EXPLAIN`.
- **A read-only connection is reported as `read_only`/exit 2, not
  `connection_failed`/exit 3.** `execute_across` (`core/group_engine.py`)
  tagged a `ReadOnlyViolation` the same as an unreachable host, so the
  message read "Falha na conexao" for a connection that was never
  unreachable — it was refused on purpose, the same condition `cmd_sql`
  already reports as `read_only`. The two commands now agree about what
  the same event is.
- **`-c prod -c prod` no longer compares a database with itself.**
  `execute_across` keys its result dict by connection name, so a repeated
  `-c` collapsed to one entry and a comparison over a single result could
  only ever report CONSISTENTE. `multi` now de-duplicates its connection
  names and refuses with `usage`, naming the repeated one, unless at least
  two *distinct* connections remain.

The TUI's Multi-Exec tab is unchanged; its tests were the check.

## [2.4.1] — 2026-09-13

A PATCH release, and a pure refactor: nothing a user runs behaves
differently. It moves the ad-hoc comparison out of the TUI so that a second
front end can reach it.

### Changed

- **The ad-hoc cross-connection comparison moved from
  `ui/screens/group_exec.py` into `core/group_engine.py`**, as
  `derive_comparison_columns`, `build_adhoc_group_result`, `execute_across`
  and `NoComparableColumns`. The Multi-Exec screen has always intersected the
  columns common to every result, taken the first as the join key and the
  rest as the compared columns, and built its `GroupResult` by hand — all of
  it inside the screen, where only the TUI could use it. The logic is
  unchanged; only its address is.
- **`execute_across` takes no view on what a failure means.** It returns one
  entry per connection that ran, successful or not, and reports a connection
  it could not resolve through a callback instead. The two front ends need
  opposite policies — the TUI carries on so a dead connection does not
  discard the comparison on screen, and a command-line caller should stop,
  because a comparison over a subset silently answers a different question
  than the one asked — so the choice belongs to the caller.

### Fixed

- **`derive_comparison_columns` raised `StopIteration` on an empty set of
  results.** The screen guarded against it; nothing else would have, and a
  `StopIteration` escaping into a command line is an exit code this project
  reserves for a bug in dbqm. It now raises `NoComparableColumns`.

The TUI's behaviour is unchanged, including *when* it reports a failed or
missing connection: that is per-connection and in sequence, as before. Its
Multi-Exec tests were the check and none of them needed editing.

## [2.4.0] — 2026-09-13

A MINOR release: `html` joins `-e/--export` on `run`, `run-group` and `sql`.

### Added

- **`-e/--export html`** on `run`, `run-group` and `sql`. `export_query_html`
  (`core/html_report.py`) renders one result set as a standalone HTML report
  meant to be read in a browser, sharing its document shell and CSS
  (`_BASE_STYLE_RULES`) with the existing group report rather than
  duplicating it.

### Fixed

- **Every export branch in `cmd_sql` and both arms of `cmd_run_group` is now
  exhaustive.** Each previously ended in a bare `else` that wrote TXT, so
  adding a format without naming it in that branch would have written a
  `.txt` file and printed `Exportado: …` as though the requested format had
  been honoured. The fall-through is now a `usage` failure instead of a
  silent wrong file.
- **`--flat` with `-e html` is refused before any work runs.** The check is
  the first statement of `cmd_run_group`, exits `2` (`usage`) naming both
  flags. Placed later, it would have resolved the group, run every query,
  and written a history record before rejecting what is a pure argument
  error.

## [2.3.2] — 2026-09-13

A PATCH. Nothing a user of the published package can observe changed — this
release finishes Tier 2 of the roadmap: strict typing joins the lockfile,
lint gate and strict pytest config from 2.3.1, all four now running in CI.

### Internal

- **mypy `strict = true` joins the gate**, with a per-module exemption list
  that only shrinks — 36 modules today, out of 91, each entry carrying the
  finding count it owes. A new module is strict from its first line; nothing
  fixes the count except typing the module and deleting its entry.
  `tests/design/test_typing_policy.py` enforces the direction: the exemption
  list may not grow, every entry must name a module that still exists, and
  the tracked count must match reality.
- **`.github/workflows/checks.yml`** runs `uv run mypy` in the Lint step,
  after `ruff`. It runs through the locked environment, not `uvx` — mypy
  needs the project's own dependencies to resolve types.
- **The roadmap's earlier figure of 464 findings at `--strict` was wrong.**
  It was measured with `uvx mypy --ignore-missing-imports`, and `uvx` runs
  mypy in an isolated environment without the project's dependencies. mypy
  could not import Textual, `--ignore-missing-imports` turned every Textual
  base class into `Any`, and every class deriving from one produced a
  phantom "cannot subclass" finding. Seven of dbqm's eight dependencies
  actually ship `py.typed`. Measured correctly, through `uv run mypy
  --strict`, the real figure was 396 findings across 58 modules. The three
  slices that built this ratchet brought that down to 361 findings in 36
  modules before this release, and the tool that reports on an environment
  it was never run inside was the thing that was wrong, not the code.

## [2.3.1] — 2026-09-13

A PATCH. Nothing a user of the published package can observe changed — this
release is repository furniture: a reproducible dev environment, a lint gate,
a stricter test configuration, and CI to run both.

### Internal

- **A lockfile.** `uv.lock` and `.python-version`, so a contributor's
  environment is reproducible. `pyproject.toml` is untouched and
  `requires-python = ">=3.10"` is unchanged — that floor is for what a user
  may install, not for contributors.
- **A lint gate.** `ruff check .` now passes over fifteen rule families,
  chosen by measuring which ones the code already passed or nearly passed.
  40 findings fixed (26 in the package, 14 in the tests) — dead code, stale
  idioms, and constructs wider than their authors meant. No behaviour change.
- **A strict test configuration.** `filterwarnings = error`,
  `--strict-markers`, `--strict-config`, `xfail_strict`.
- **CI.** `.github/workflows/checks.yml` runs the lint gate and the test
  suite on pull requests and on pushes to `main`.
- One test in `tests/test_cli_tema.py` depended on whether `NO_COLOR` was set
  in the environment — it passed on some machines and failed on others. Not a
  bug in dbqm; it would have failed on the Linux runner CI now uses, so it is
  pinned to build its `Console` with `no_color=False`.

## [2.3.0] — 2026-09-13

Defects in the published error contract, found and fixed in the same slice
because they share the same paths. **Three exit codes move** for a script
that branches on them — all of them the documented table finally being
honoured, not a new behaviour.

### Fixed

- **A connection failure from `run` and `sql` now exits `3`, not `4`.**
  `core/query_engine.py` used to wrap opening the connection and running the
  statement in one `try`, so "the database never answered" and "the
  statement was rejected" produced the identical string and the identical
  exit code. The three executing functions (`execute_query`,
  `execute_adhoc`, `execute_explain`) now split that `try` and carry the
  answer out on a new `error_kind` field (`"connection"`, `"statement"`, or
  `""` on success) — additive on the `run`/`sql` JSON payloads. The CLI maps
  `error_kind == "connection"` to `connection_failed` (exit `3`); everything
  else keeps exiting `4` (`sql_error`) as before. The obvious alternative —
  catching a connection-specific exception class — does not work on Oracle:
  `oracledb` raises the same `DatabaseError` for a bad password and a
  missing table, so the failure kind has to be decided by where the call
  was made, not by what it raised. **If a script retried `connection_failed`
  and treated `sql_error` as final, it now retries the right thing.**
- **`rows` on an object that does not exist now exits `2` (`not_found`),
  not `4` (`sql_error`), agreeing with `describe`.** `rows` asks the
  catalogue whether the name exists, but only after `browse_table` has
  already failed, so a successful call pays nothing extra. Views are
  checked alongside tables, since a valid view name is not a table. A
  name `_validate_identifier` rejects outright stays `usage` and never
  reaches the catalogue lookup. And if the lookup itself fails — no
  permission on the catalogue, a transient outage — the user still reads
  their own error, not the lookup's.
- **`dbqm ddl -f json --stdout` no longer writes the extraction to disk.**
  The payload keeps its `"path"` key and reports `null` instead of a
  directory, since `--stdout` now means what it says in both formats.

- **`dbqm ddl` now answers like every other command.** Two problems, both
  found by reviewing the whole branch rather than any one change. A missing
  object exited `4` (`sql_error`) where `describe` and `rows` both say
  `not_found` (`2`) — the same disagreement fixed above, one command over.
  And `core/ddl_extractor.py` opens its own connection outside any `try`
  while `cmd_ddl` had no handler, so **an unreachable database escaped as an
  unhandled exception and exited `1`** — "a bug in dbqm" — for a database
  that was merely down. It now exits `3`, like the rest.

- **`--explain`'s own two refusals are `usage` (`2`), not `sql_error` (`4`).**
  Passing `EXPLAIN PLAN FOR` to `--explain`, and asking for `--explain` on an
  engine that has none, both fail before any statement is sent. The second is
  a capability the engine lacks, which the schema commands already answer
  with `usage`.

## [2.2.0] — 2026-09-13

A connection can be marked read-only, and dbqm then declines to send it
anything but a query.

### Added

- **A connection can be marked read-only** —
  `dbqm connection add|update <name> --read-only` / `--no-read-only`, or the
  "Somente leitura" checkbox in the TUI connection form. `connection show`
  and `connection list -f json` report it. Once marked, dbqm refuses
  anything the connection sends except a `SELECT` or a genuine `EXPLAIN`,
  across every path that reaches a driver: ad-hoc SQL, explain plans, routine
  execution and package compilation, in the TUI as well as the CLI. A
  statement string carrying more than one command is refused outright too,
  because it cannot be checked as one.
- **`--force-write` on `dbqm sql`** lifts the refusal for that one
  invocation. It does **not** imply `--commit` — writing to a protected
  connection takes both flags, deliberately. `dbqm sql` has always required
  `--commit` for DML; letting `--force-write` also imply it would leave
  `DELETE`, `UPDATE` and `INSERT` unprotected on a connection marked
  read-only for exactly that reason.

  **There is no override for routine execution or package compilation.**
  Both exist only in the TUI and `--force-write` is a flag on `dbqm sql`, so
  on a protected connection those two operations simply refuse; the way
  through is to clear the read-only mark on the connection, which is what
  their message says.
- **A new `read_only` error token**, exit `2`, alongside `usage`,
  `not_found` and `validation`.

**Two things worth saying plainly, so this is not oversold:**

1. **This is a rail against mistakes, not a security boundary.** Whoever can
   connect can still write with another client — this only stops the wrong
   connection name, the generated statement, the careless paste. It is the
   same distinction DBeaver draws between its client-side "Edit permissions"
   and its server-side "Read-only connection"; dbqm ships the client-side
   rail now. A server-side read-only session (`SET TRANSACTION READ ONLY` on
   Oracle and MySQL, `BEGIN READ ONLY` on PostgreSQL — SQL Server has no
   equivalent) is deferred to the sub-project that builds `dbqm call`.
2. **`--force-write` does not imply `--commit`.** See above.

### Fixed

- **An `EXPLAIN` that runs what it explains was treated as a read.** On
  PostgreSQL and MySQL, `EXPLAIN ANALYZE DELETE FROM t` **executes the
  delete** — the plan comes from running the statement, not predicting it.
  The read-only guard now checks what an `EXPLAIN` actually explains before
  waving it through.
- **`_is_select_only` inspected only the first statement.** The gate
  `execute_query` relies on classified only the leading statement in a
  string, so a saved query ending in a second one passed the check while the
  whole string still reached the driver. It now refuses any input carrying
  more than one statement.

## [2.1.0] — 2026-09-12

Schema discovery on the CLI: three commands to see what is in a database
without hand-written catalogue SQL. Nothing existing changed shape, so this is
a minor release.

### Added

- **`dbqm objects <connection> [--type TABLE|VIEW|PACKAGE|ROUTINE] [-f table|json]`**
  — list what exists.
- **`dbqm describe <object> <connection> [-f table|json]`** — one object's
  columns (type, nullability, PK marker, FK reference) plus its indexes. It
  dispatches on what the object turns out to be, so the caller never says
  "table" or "view". **No row count, in either format**: a `COUNT(*)` is a
  full scan and a describe is meant to be instant — `psql \d` shows none
  either.
- **`dbqm rows <table> <connection> [--limit N] [--offset N] [-f table|json|csv|raw]`**
  — browse a table, paged. `rows` are parallel arrays, matching what 2.0.0
  established for `run` and `sql`. Under `-f table` it also reports the total
  row count and the `--offset` for the next page. There is deliberately no
  `--where`: `dbqm sql` already takes a predicate.

All three speak the 2.0.0 envelope under `-f json` and map failures the same
way `run`/`sql` do: a connection that never opened is `connection_failed`
(exit 3), a statement the engine rejected is `sql_error` (exit 4), and a
capability the engine does not have is `usage` (exit 2).

**Known gap, not introduced here:** `objects --type ROUTINE` cannot tell a
PROCEDURE from a FUNCTION on any engine — the query joins both and returns
only the name. Documented in `core/object_browser.py`.

### Fixed

- **Package and routine introspection on SQL Server, PostgreSQL and MySQL
  raised a raw driver error.** Asking `list_package_routines` or
  `get_package_source` for packages on those three engines used to surface an
  unhandled driver traceback, and `dbqm objects --type PACKAGE` used to return
  an empty list on them — which reads as "there are none here" rather than
  "this engine has no such thing". Both now refuse cleanly with a message
  naming the engine.
- **`dbqm objects --type ROUTINE` on SQL Server returned an empty list.** That
  engine's branch was never written, while PostgreSQL and MySQL both already
  queried `information_schema.routines`; SQL Server now does too. Verified
  against a real SQL Server: 41 routines where there used to be none.
- **`dbqm describe` reported a genuine view as a TABLE** when the connected
  user lacked the `VIEW DEFINITION` grant. SQL Server returns `NULL` from both
  `information_schema.views` and `sys.sql_modules` in that case, with no
  error, so the empty definition looked like "not a view".
- `get_table_structure`'s docstring claimed a row count it never returned.

## [2.0.0] — 2026-09-12

One machine-readable output contract for the whole CLI. Every JSON shape
public since 1.7.0 changes, plus two behaviour changes — this is why it is a
major release, and the **Migration** section below is a straight port of it.

### Added

- **`test`, `ddl`, `export-config` and `import-config` gained `-f/--format`**,
  with a `json` option. Every command now offers `table|json` at minimum,
  and `run`/`run-group`/`sql` add `csv`/`raw` on top.

### Changed

- **Every command emits one JSON envelope under `-f json`.** A success prints
  `{"ok": true, "command": "...", "data": {...}}` to stdout; a failure prints
  `{"ok": false, "command": "...", "error": {"code", "message", "exit"}}` to
  **stderr**, with stdout left completely empty. Before this, an error printed
  Portuguese prose to *stdout*, so `| jq` broke on every failure — a script
  had no reliable way to tell a failed run from a successful one that happened
  to print little.
- **`run`, `run-group` and `sql` now serialise through the `core/` dataclasses'
  own `to_dict()`** instead of a hand-built dict per branch. This renamed
  several keys and changed how `rows` is shaped — see the migration table.
  The `rows` change fixes a real bug: the old `rows` were objects keyed by
  column name, which silently dropped a column whenever a SELECT repeated a
  name — `SELECT a.id, b.id FROM a JOIN b` returned two values for three
  declared columns, the third overwriting the first under the same key.
  Parallel arrays carry every column regardless of repeated names. Verified
  against a real SQL Server with a genuinely repeated column from a join:
  `"columns": ["id", "nome", "id"]`, `"rows": [[1, "texto", 2]]` — all three
  values present.
- **`run-group` now exits `5` when the comparison diverges.** Before this it
  always exited `0`, whether the comparison matched or not. This is the
  single most consequential change in this release for existing scripts: a
  `dbqm run-group ... && next-step` chain used to run `next-step`
  unconditionally and now stops the moment the databases disagree — under
  `-f json` and under the default `-f table` alike, since the exit code is
  set independently of how the result is printed.
- **Exit code `1` stops being a catch-all.** It now means specifically "a bug
  in dbqm," not "anything went wrong." The full, stable table:

  | Code | Meaning |
  |---|---|
  | `0` | success |
  | `1` | a bug in dbqm — not the input, not the database |
  | `2` | usage error, name not found, or a value that fails validation |
  | `3` | connection failed |
  | `4` | SQL error — the statement reached the driver and was rejected |
  | `5` | comparison ran to completion and diverged (`run-group`) |
  | `130` | interrupted (Ctrl+C) |

  This supersedes the narrower table the `connection` group alone documented
  since 1.22.0 (`0`/`2`/`3`); those three codes keep their meaning, and the
  table now applies to every command.

### Migration

**1. Every list/show/mutate command gains an envelope.** What used to be the
whole JSON payload now sits under `data`:

| Command | Before | After |
|---|---|---|
| `list <resource>` | `[{...}]` | `{"ok":true,"command":"list.connections","data":[{...}]}` |
| `history` | `[{...}]` | `{"ok":true,"command":"history","data":[{...}]}` |
| `connection show` | `{...}` | `{"ok":true,"command":"connection.show","data":{...}}` |
| `connection add\|update\|rm` | `{"name":...,"created":true}` | the same object, now under `data` |

A consumer piping with `jq` moves the filter one level down:

```bash
# before
dbqm list connections -f json | jq '.[].name'
# after
dbqm list connections -f json | jq '.data[].name'
```

**2. `run` (`-f json`):**

| Old key | New key | Notes |
|---|---|---|
| `query` (query name) | `query_name` | renamed |
| `connection` | `connection_name` | renamed |
| `columns` | `columns` | unchanged |
| `rows`: `[{"col": val, ...}, ...]` (one dict per row) | `rows`: `[[val, ...], ...]` (one array per row, positionally matching `columns`) | **shape change** — zip `columns` with each row yourself now; this is also the fix for the silent data-loss bug above |
| `row_count` | `row_count` | unchanged |
| `elapsed` (rounded to 3 decimals) | `elapsed` (raw float, unrounded) | may now have more decimal places |
| — | `success` | new (always `true` here — a failed run never reaches this branch) |
| — | `error` | new (always `""` here) |

**3. `sql` (`-f json`) — SELECT, INSERT/UPDATE/DELETE, DDL, PL/SQL and the
unclassified-type fallback all move to the same shape. `--explain` keeps its
own payload but is renamed along with the rest; see below the table:**

| Old key | New key | Notes |
|---|---|---|
| `query` (present only on the SELECT branch; the raw SQL text) | `sql` | renamed — this also resolves `run`'s `"query"` meaning the saved query's *name* while `sql`'s `"query"` meant the SQL *text*; `query_name` and `sql` now never collide |
| `connection` | `connection_name` | renamed |
| `columns` | `columns` | unchanged (present on SELECT/PL-SQL; empty list on DML/DDL/fallback, same as before) |
| `rows`: `[{"col": val, ...}, ...]` (SELECT/PL-SQL only) | `rows`: `[[val, ...], ...]` | **shape change**, same fix as `run` |
| `row_count` | `row_count` | unchanged |
| `rows_affected` | `rows_affected` | unchanged |
| `committed` | `committed` | unchanged |
| `elapsed` (rounded) | `elapsed` (raw) | unrounded now |
| — | `sql_type` | was already present on every branch except SELECT before; now uniform |
| — | `db_type` | new — which engine ran it (`oracle`/`sqlserver`/`postgresql`/`mysql`) |
| — | `success` | new (always `true` here) |
| — | `error` | new (always `""` here) |
| — | `output_lines` | new as a `data` field — was already riding separately as the envelope's top-level `warnings`, which is unchanged; it now also appears inside `data` |

`sql --explain` keeps its `{"elapsed", "plan"}` payload, and its `connection`
key is renamed to `connection_name` along with everything else — it was the one
key left contradicting the rest of the contract.

**4. `--export` with `-f json`, on `run`, `run-group` and `sql`:**

Exporting used to print `Exportado: <path>` as prose **on stdout**, even under
`-f json`. It now emits an envelope, and `data` describes the export rather
than the result:

| Before | After |
|---|---|
| `Exportado: /path/to/file.csv` (plain text on stdout, exit 0) | `{"ok":true,"command":"run","data":{"exported":"/path/to/file.csv","format":"csv"}}` |

So with `--export` the `data` shape is `{"exported", "format"}` — **not** the
result shape in the tables above. The rows are in the exported file, which is
the point of the flag. `run-group --export` still exits `5` when the
comparison diverged; before this release it returned early and exited `0`.

**5. `run-group` (`-f json`): shape unchanged** —
`{"group", "all_match", "comparisons": [{"column", "total_keys", "equal_count",
"diff_count", "absent_count", "normalized_count"}, ...]}` is exactly what it
was. **The behaviour that changed is the exit code**, not the payload: see the
`run-group` exit-`5` note above. A pipeline that only reads the JSON is
unaffected; a pipeline that chains on the shell exit code needs to account for
`5` meaning "ran fine, but diverged."

**6. Errors move to stderr.** Any script that checked "did stdout have
content" instead of the exit code, or that redirected stderr away before
piping stdout to `jq`, now sees empty stdout on failure instead of prose.

## [1.23.0] — 2026-09-12

### Added

- **A password can now be cleared from the TUI.** Until now a blank field meant
  "keep the stored one", so the screen could change a password but never remove
  one — the CLI had `--no-password` and the form had no equivalent. No new
  widget was needed: loading a connection already decrypts its password into
  the field, so the box shows what is stored and emptying it means emptying it.
  Two cases keep their old meaning, because there the box is not showing that
  connection: typing an existing name into a blank form, and a stored password
  that will not decrypt. Neither is wiped by a save.

### Fixed

- **The release workflow no longer runs on Node 20.** `actions/checkout` and
  `actions/setup-python` are on `@v7`; both were being forced onto Node 24 with
  a deprecation warning.
- **The empty-stdin error no longer names a flag the command lacks.** It pointed
  every caller at `--no-password`, which `export-config` and `import-config` do
  not have. The hint is derived from the parser now.

## [1.22.2] — 2026-09-11

Nine of the ten open bugs, closed in one pass. No new commands; no behaviour
change to any command that already worked.

### Fixed

- **SQL Server ad-hoc execution, broken two ways and silent about both.**
  `EXEC`/`EXECUTE`/`CALL` was rewritten into Oracle PL/SQL for every engine, so
  `EXEC dbo.PROC @p='1'` reached SQL Server as `BEGIN dbo.PROC @p='1'; END;` —
  the reason the driver answered `Incorrect syntax near 'dbo'`. And a T-SQL
  batch's result sets were never read, so a batch ending in `SELECT @n, @m`
  printed only `Bloco PL/SQL executado` and dropped the answer. Both are now
  engine-aware, and the outcome is labelled in the dialect that ran it.
  Verified against a real SQL Server, with Oracle re-checked in the same pass.
- **A connection saved without a password no longer fails with an empty
  message.** `decrypt("")` returns `""`; `str(InvalidToken())` is the empty
  string, which reached the user as `Erro ao conectar:` and nothing else. A
  stored password that will not decrypt now names `.dbqm_key` and the command
  that repairs it.
- **The history list gets the room the detail panel was taking.** At 80x24 the
  table had a three-row viewport — 2 of 30 entries visible. Measured in the
  real app: now five rows there, and 19 against a 9-row detail at 120x40.
- **The result-set walk is bounded**, so a driver that never reports the end
  cannot hang the process.

### Removed

- **`Breadcrumb`** — zero instances anywhere, while `package_editor` queried it
  on every package open and every call raised into a bare `except`.
- **PNG export** — unreachable by construction: every call site disabled it,
  no writer survived the removal of the Rich UI layer, and `Pillow` is in no
  dependency list.
- **`Connection.windows_auth`** — never read or written, and unreachable
  anyway: `pymssql` takes no trusted-connection parameter. An older
  `connections.json` carrying the key still loads.

### Internal

- Two Oracle Instant Client tests read the developer's real `~/.dbqm` and
  failed on any machine that set `oracle_client_dir`; they are isolated now.
- The navigating-button layout guard had an `if/elif` hole that let a branch
  inherit a sibling's exemption in silence. Closed, and break-tested both ways.
- The app is proven to boot when `settings.json` names a theme it does not
  know — the failure class that made a 1.17.x rollback fail.

## [1.22.1] — 2026-09-10

### Added

- **`PYPI.md`** — a short, audience-specific page for PyPI, now the package's
  `long_description`. `README.md` stays the repository's page on GitHub. Every
  link in `PYPI.md` is an absolute GitHub URL, because PyPI does not resolve
  relative links.
- **`docs/ARCHITECTURE.md`** and **`docs/ROADMAP.md`** — the architecture
  reference and the prioritised backlog, split out of `AGENTS.md`, which had
  grown to three documents in one. The roadmap puts bugs in a tier above every
  feature.
- **`docs/agents/`** — the shared house guides (agent workflow, task completion,
  Python standards, versioning, commits), copied byte-identical to their source
  up to a `## Deviations in this project` heading, so `diff` remains a working
  drift check.
- **`.gitattributes`** normalising the repository to LF, without which that drift
  check reports differences on line endings alone.

### Fixed

- **A whitespace-only password field in the TUI keeps the stored password**
  instead of overwriting it with whitespace.
- **README corrections** that were public on PyPI: `pip install dbqm` was
  documented nowhere, `dbqm run --param1 value1` is not a flag that has ever
  existed (it is `-p CHAVE=VALOR`), and `Pillow` was listed as a dependency that
  is in no dependency list and imported nowhere. The `Author` metadata read
  "Ricardo" and is now "Silvio Chagas".

## [1.22.0] — 2026-09-10

Connections can now be created and edited from the CLI, without opening the TUI.

### Added

- **`dbqm connection` command group** — `add`, `update`, `rm`, `show` and `list`
  manage connections non-interactively, for scripts, CI and AI agents. `add`
  refuses a duplicate name; `update` changes only the flags you pass and leaves
  the rest as they were; `rm` requires `--yes` when there is no terminal to
  confirm against; `show` never prints the password.
- **Non-interactive passwords** — `--password-stdin` and the `DBQM_PASSWORD`
  environment variable read a connection password without it ever appearing in
  argv or shell history. `export-config` and `import-config` gained the same
  `--password-stdin` and a `DBQM_BUNDLE_PASSWORD` environment variable, so
  neither blocks waiting on a prompt when run without a terminal.
- **`--test`** on `connection add`/`update` tries the connection before saving
  it and refuses to save one that does not answer.

### Changed

- **Connection validation, per-engine defaults and encryption** moved out of
  the TUI's connections screen into `core/connection_builder.py`, a UI-agnostic
  module the CLI now shares with it — both front ends validate and default
  identically instead of each carrying its own copy of the rules.

### Fixed

- **`connection update` no longer reads `DBQM_PASSWORD`** — only
  `--password-stdin` or `--no-password`, given on that command line, change
  the stored password; an ambient environment variable left over from another
  command could otherwise silently replace it.
- **An empty `--password-stdin` read is now always an error** (exit 2, with a
  message pointing at `--no-password`) instead of creating a passwordless
  connection on `add` or silently clearing the stored password on `update`.
- **User-supplied values are escaped before reaching Rich markup**, so a
  connection name, query/group name or bad `--type` value containing `[` or
  `]` can no longer crash the command with a `MarkupError` or vanish from the
  error message it was meant to appear in.
- **A bare `dbqm connection` now prints the command group's help** and exits
  2, instead of a one-line usage reminder.
- **`connection rm` cancellation now respects `-f json`**, emitting
  `{"name": ..., "removed": false}` instead of the plain-text `Cancelado.`,
  which broke JSON consumers.
- **`connection add` validates before asking for a password**, so a bad
  `--type` or missing required field is reported before a terminal user is
  prompted to type a secret.
- **A whitespace-only password field in the TUI keeps the stored password**
  again, instead of overwriting it with whitespace. Moving the rules into
  `core/connection_builder.py` also stopped the screen stripping that field —
  correct for a password that legitimately ends in a space, wrong for one that
  is nothing but spaces. The presence test now strips; the value still does
  not.

## [1.21.0] — 2026-08-23

Structure is now decided once for the whole TUI instead of per screen.

### Added

- **Layout grammar** — four decisions applied across every screen: `Panel` is the
  only section frame and a screen taller than the terminal scrolls instead of
  truncating in silence; navigation follows cardinality (tabs → `Select` with
  counts → `OptionList` → `DataTable`, with `ListView` removed from the
  vocabulary); a list item is a 2–3 line hierarchy (identity / disambiguation /
  context) instead of a concatenated string; a result table pins its key column,
  stripes its rows and scrolls sideways rather than truncating.
- **Six repo-wide guards** (`tests/design/test_inventario_layout.py`) enforcing
  the grammar. Each was verified by breaking the rule it protects, and each
  documents in code what it cannot see.
- Loading skeleton for result tables, shaped from the real median query.

### Changed

- **Settings** is now one `Panel` per subject (theme, audit, export, Oracle
  Instant Client, more settings, Fernet key) in two independently scrolling
  columns, replacing a single panel with centred button clusters.
- **Query and group folders** are a `Select` carrying a per-folder count instead
  of a horizontally scrolling tab bar, which did not scale past a handful of
  folders. The shared folder prefix is elided dynamically, so the full path
  returns on its own the day a second folder family appears.
- **Button menus became lists** in Ferramentas and Export/Import — a button is an
  action, never navigation. Back is `Esc`, announced in the action bar.
- Actions are anchored to the panel they operate on, with destructive ones set
  apart, instead of being centred in the middle of a working screen.
- Long paths in Settings are elided in the middle, keeping root and leaf.

### Fixed

- **Three screens were unreachable since 1.17.0.** Export/Import configuration,
  the Oracle Instant Client manager, and Export/Import's own "Voltar" all queried
  a container removed in the tabbed-shell rewrite, so each reported an error and
  opened nothing.
- **The action bar never rendered anywhere in the app.** It and the status bar
  both docked to the bottom edge, and the status bar painted over the action
  bar's text row — so every screen's contextual shortcuts were registered and
  invisible.
- **Focus could change the active tab.** Textual's `TabbedContent` treats a pane
  focus as navigation, so a screen's deferred initial focus undid the user's tab
  switch, including on an already-hidden pane. This also swallowed function keys
  pressed during startup.
- **Connection, query and group lists** no longer run a wrapped description into
  the identity column, where the eye cannot tell a continuation from the next
  entry.
- Two queries or groups sharing a name no longer crash their screen on mount.
- Opening the app no longer emits toasts for settings the user did not touch, nor
  rewrites `settings.json` unprompted. Upgrading from 1.17.x no longer reports
  "Tema alterado" for what is only an internal rename.
- The Oracle "Client em uso" label now follows the client you just chose.
- Empty history no longer shows an empty table's headers beside its empty state.

## [1.20.0] — 2026-08-22

### Added

- **Shared components**, each the single implementation for its job across the
  TUI: `Dialog` (floating-layer chrome, replacing 29 copied frames), `EmptyState`
  (mandatory what / why / first action), `Veredito` and `StatusOperacao`
  (match / diff / absent plus operation-result markup), and `Esqueleto` (loading
  skeleton and distinct disabled and read-only states).
- Component-inventory guards preventing a second hand-rolled copy of any of them.

### Changed

- Group comparison tables carry the verdict colour instead of plain text.

## [1.19.0] — 2026-08-22

### Added

- **"Plano" design system** — 15 semantic colour tokens (surfaces, text, borda,
  identidade, and a verdict axis for OK / DIFF / AUSENTE) in
  `dbqm/design/tokens.py`, shared by the Textual TUI, the Rich-based CLI output
  and the HTML report CSS, so all three stay visually consistent.
- WCAG contrast checking against every surface a token declares as valid, with no
  known debt. Known gap outside that check: Textual's built-in `$text-muted` and
  Rich's `[dim]` sit outside the token layer.
- A literal-colour scan with a ceiling that only ever decreases; it now sits at
  zero.

### Changed

- Dark and light themes were repainted on the token layer. `github-dark` and
  `github-light` were renamed to `plano-escuro` and `plano-claro`; a legacy map
  migrates the saved setting on first launch.
- HTML report badges and row highlights use a border and marker rather than a
  fill, so text keeps its contrast.

## [1.18.0] — 2026-08-22

### Added

- **Oracle Instant Client path in settings.** The client directory is now
  resolved from dbqm's own configuration rather than the system `ORACLE_HOME`,
  and the resolved path, its origin and its architecture are shown in Settings.

### Fixed

- Connections failing for users with an old PL/SQL Developer, whose 32-bit
  Instant Client was set as the system `ORACLE_HOME` while dbqm requires 64-bit.
  Architecture is validated up front and a mismatch is reported plainly instead
  of surfacing as an opaque driver error.
