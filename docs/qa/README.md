# QA — what a working dbqm must do, and what proves it

One document per feature. Each lists the scenarios a person validating the
app would check, and for every scenario names the test that proves it — or
says plainly that nothing does.

**A `functional` row saying `—` is a bug in this directory.** The
traceability check (`tests/design/test_qa_traceability.py`) fails on it, on
a referenced test that does not exist, and on an ID used twice. A document
that a test enforces is a specification; one that nothing enforces is a
wish.

## Format

```markdown
| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-RUN-001 | Dado ... / Quando `dbqm run ...` / Entao exit 0 e ... | functional | all | tests/functional/test_run.py::test_x |
| QA-CALL-004 | Dado ... / Quando ... / Entao ... | manual | oracle | — |
```

- **ID** — `QA-<FEATURE>-<NNN>`, three digits, stable, never reused.
- **Cenario** — `Dado … / Quando … / Entao …` on one line, slashes as
  separators, in Portuguese without accents, quoting the exact command and the
  exact token or string expected. It is read by a person, not parsed.
- **Camada** — `unit` (an existing mocked test proves the orchestration),
  `functional` (runs against a real SQLite database through `run_cli`, nothing
  patched), or `manual` (needs an engine the suite does not have).
- **Engine** — `all`, `sqlite`, `oracle`.
- **Teste** — `tests/<path>::<test>` (class-qualified when inside a class), or
  `—` for `manual` only.

A `manual` row is followed by a fenced block with the exact commands and the
exact expected output, so whoever has the Oracle can run it without reading
code.

## The three layers, and why the middle one exists

| Layer | Against | Covers |
|---|---|---|
| unit | mocks | isolated logic |
| functional | a seeded SQLite file (`tests/functional/conftest.py`) | every engine-agnostic command end to end |
| manual | a real Oracle the maintainer has | `call`, packages, DBMS_OUTPUT, `ddl` via `DBMS_METADATA`, `--explain` on Oracle |

Before 2.9.0 the CLI had 1448 tests and not one ran a command against a
database: every command test verified orchestration against mocks. SQLite as
an engine is what made the middle layer possible.

## Feature codes

`CONN` connections · `QUERY` saved queries · `GROUP` groups · `MULTI` multi ·
`SQL` ad-hoc SQL · `RO` read-only guard · `CALL` routines · `DISC` discovery ·
`DDL` ddl · `PKG` packages · `EXPORT` export · `PORT` config portability ·
`HIST` history · `CFG` settings · `TPL` templates · `OCLI` oracle client ·
`OUT` output contract · `DESC` self-description.

## Documents

Counted from the documents by the review's closing task, not typed. The
`unit` layer is unused: every scenario a mocked test proves is listed as
`manual` with that test named in its row, because a mock never proves the
scenario, only the orchestration around it.

| Document | Code | Scenarios | functional | manual |
|---|---|---|---|---|
| [adhoc-sql.md](adhoc-sql.md) | `SQL` | 18 | 17 | 1 |
| [saved-queries.md](saved-queries.md) | `QUERY` | 10 | 10 | 0 |
| [groups.md](groups.md) | `GROUP` | 13 | 13 | 0 |
| [multi.md](multi.md) | `MULTI` | 16 | 16 | 0 |
| [read-only-guard.md](read-only-guard.md) | `RO` | 11 | 10 | 1 |
| [output-contract.md](output-contract.md) | `OUT` | 14 | 14 | 0 |
| [connections.md](connections.md) | `CONN` | 21 | 21 | 0 |
| [templates.md](templates.md) | `TPL` | 8 | 8 | 0 |
| [settings.md](settings.md) | `CFG` | 7 | 7 | 0 |
| [config-portability.md](config-portability.md) | `PORT` | 7 | 7 | 0 |
| [history.md](history.md) | `HIST` | 6 | 6 | 0 |
| [discovery.md](discovery.md) | `DISC` | 16 | 15 | 1 |
| [ddl.md](ddl.md) | `DDL` | 8 | 7 | 1 |
| [export.md](export.md) | `EXPORT` | 9 | 9 | 0 |
| [self-description.md](self-description.md) | `DESC` | 6 | 6 | 0 |
| [routines.md](routines.md) | `CALL` | 15 | 0 | 15 |
| [packages.md](packages.md) | `PKG` | 5 | 0 | 5 |
| [oracle-client.md](oracle-client.md) | `OCLI` | 6 | 0 | 6 |
| **Total** | | **196** | **166** | **30** |

The 30 manual rows are the Oracle-only surface (`call`, packages, the
client installer, `DBMS_METADATA`, DBMS_OUTPUT, `EXPLAIN PLAN FOR` on a
read-only connection) plus the Oracle catalogue arm of `objects`. Each
carries the exact commands and the unit test that covers its CLI side.
