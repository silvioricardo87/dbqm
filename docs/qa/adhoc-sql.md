# QA — ad-hoc SQL (`SQL`)

Until 2.9.0 `-e/--export` was accepted and ignored on anything that was
not a SELECT (the export block lives inside the SELECT branch). Now a
command that returns no rows refuses the flag, and refuses it **before
running**.

`dbqm sql <sql|file.sql> <connection> [-p k=v] [-f table|json|csv|raw] [-e csv|json|txt|html] [--commit] [--force-write] [--explain]`

Runs one statement against a named connection. The seed every row below
counts on is `tests/functional/conftest.py::SEED`: `clientes` (3 rows: Ana/A,
Bia/I, Caio/A), `pedidos` (4 rows), a unique index `ix_clientes_nome`, a view
`v_ativos`. Envelope shape and exit codes: [output-contract.md](output-contract.md).
Read-only refusals: [read-only-guard.md](read-only-guard.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-SQL-001 | Given the `local` connection / When `dbqm sql "SELECT id, nome FROM clientes ORDER BY id" local -f json` / Then exit 0, `data.rows` are the 3 seeded rows, `data.columns == ["id","nome"]` and `data.sql_type == "SELECT"` | functional | all | tests/functional/test_sql.py::test_select_returns_the_seed_rows |
| QA-SQL-002 | Given `-p id=2` / When `dbqm sql "SELECT nome FROM clientes WHERE id = :id" local -p id=2 -f json` / Then exit 0 and `data.rows == [["Bia"]]` — the bind reached the driver | functional | all | tests/functional/test_sql.py::test_a_param_reaches_the_statement |
| QA-SQL-003 | Given an UPDATE without `--commit` / When `dbqm sql "UPDATE clientes SET status='X' WHERE id=1" local -f json` / Then exit 2, `error.code == "usage"`, the message `DML requires --commit to confirm the operation.` and the row still reads `A` on a following read | functional | all | tests/functional/test_sql.py::test_dml_without_commit_is_refused_before_running |
| QA-SQL-004 | Given the same UPDATE with `--commit` / When it runs and then `dbqm sql "SELECT status FROM clientes WHERE id=1" local -f json` on a second call / Then the first returns `rows_affected == 1` and `committed == true`, the second reads `X` | functional | all | tests/functional/test_sql.py::test_dml_with_commit_persists_for_the_next_call |
| QA-SQL-005 | Given `CREATE TABLE auditoria (id INTEGER)` / When it runs and then `dbqm objects local --type TABLE -f json` / Then the first returns `sql_type == "DDL"` and exit 0, the second lists `auditoria` | functional | all | tests/functional/test_sql.py::test_ddl_creates_a_table_that_objects_then_lists |
| QA-SQL-006 | Given a DDL the driver rejects (`CREATE TABLE clientes (id INTEGER)`, it already exists) / When run with `-f json` / Then exit 4, `error.code == "sql_error"` and the driver's message (`table clientes already exists`) | functional | all | tests/functional/test_sql.py::test_a_ddl_the_driver_rejects_is_sql_error |
| QA-SQL-007 | Given `--explain` / When `dbqm sql "SELECT id FROM clientes" local --explain -f json` / Then exit 0 and `data.plan` is a non-empty list of strings mentioning `clientes` | functional | all | tests/functional/test_sql.py::test_explain_returns_a_plan |
| QA-SQL-008 | Given a table that does not exist / When `dbqm sql "SELECT * FROM nao_existe" local -f json` / Then exit 4, `error.code == "sql_error"` and `error.message == "no such table: nao_existe"` (the driver's message, not a paraphrase) | functional | all | tests/functional/test_sql.py::test_a_statement_the_driver_rejects_is_sql_error |
| QA-SQL-009 | Given a verb dbqm does not recognise (`SELEC 1`) / When run / Then exit 2 and `error.code == "usage"` (core refuses before sending it to the driver; it is not `sql_error`) | functional | all | tests/functional/test_sql.py::test_an_unknown_verb_is_usage_not_sql_error |
| QA-SQL-010 | Given a file `consulta.sql` holding `SELECT COUNT(*) AS n FROM pedidos` / When `dbqm sql <path> local -f json` / Then the file is read and `data.rows == [[4]]` | functional | all | tests/functional/test_sql.py::test_a_sql_file_path_is_read |
| QA-SQL-011 | Given `-e csv`, `-e json`, `-e txt`, `-e html` / When `dbqm sql "SELECT id, nome FROM clientes" local -e <fmt> -f json` / Then exit 0, `data.exported` points at an existing file with the format's extension (`.htm` for html), `data.format == <fmt>`, and the content carries `Ana` | functional | all | tests/functional/test_sql.py::test_export_writes_a_file_per_format |
| QA-SQL-012 | Given `-p semigual` / When `dbqm sql "SELECT 1" local -p semigual -f json` / Then exit 2, `usage`, the message `Invalid parameter (use key=value): semigual` | functional | all | tests/functional/test_sql.py::test_a_param_without_equals_is_usage |
| QA-SQL-013 | Given a connection that does not exist / When `dbqm sql "SELECT 1" nope -f json` / Then exit 2, `not_found`, the message `Connection "nope" not found.` | functional | all | tests/functional/test_sql.py::test_an_unknown_connection_is_not_found |
| QA-SQL-014 | Given `-f table` (the default) / When `dbqm sql "SELECT nome FROM clientes WHERE id=1" local` / Then exit 0 and `Ana` appears on stdout | functional | all | tests/functional/test_sql.py::test_table_format_prints_the_rows |
| QA-SQL-016 | Given `-e csv` on an UPDATE / When `dbqm sql "UPDATE clientes SET status='X' WHERE id=1" local --commit -e csv -f json` / Then exit 2, `usage`, `--export needs a command that returns rows; UPDATE does not return any.`, the row still reads `A` and no file was written — the refusal comes before it runs | functional | all | tests/functional/test_sql.py::test_export_on_a_dml_is_refused_before_the_write |
| QA-SQL-017 | Given `-e json` on a DDL / When `dbqm sql "CREATE TABLE auditoria (id INTEGER)" local -e json -f json` / Then exit 2, `usage`, `... DDL does not return any.` and `objects` does not list `auditoria` | functional | all | tests/functional/test_sql.py::test_export_on_a_ddl_is_refused_and_nothing_is_created |
| QA-SQL-018 | Given `-e csv` on a SELECT / When run / Then exit 0 and the file exists — the guard names statement types, not the flag | functional | all | tests/functional/test_sql.py::test_a_select_still_exports |
| QA-SQL-019 | Given `--explain -e csv` / When `dbqm sql "SELECT id FROM clientes" local --explain -e csv -f json` / Then exit 0 and the file carries the `plan` header and the plan — a plan is a result set, and this branch returns before the guard | functional | all | tests/functional/test_sql.py::test_explain_exports_the_plan |
| QA-SQL-020 | Given the `ro` connection and `UPDATE ... --commit -e csv` / When run / Then exit 2 and `read_only` — the connection refusing comes before any problem with a flag | functional | all | tests/functional/test_sql.py::test_the_read_only_refusal_comes_before_the_export_one |
| QA-SQL-021 | Given the TUI's **Ad-hoc SQL** screen on the `local` connection / When a SELECT is run from the Run button / Then the info bar shows `3 rows` and the table carries 3 rows | functional | all | tests/ui/test_functional_screens.py::test_adhoc_executes_a_select_and_shows_the_rows |
| QA-SQL-022 | Given `-p naoexiste=1` on SQL that never binds it / When run / Then exit 2, `validation`, `The SQL does not use the parameter "naoexiste".` | functional | all | tests/functional/test_sql.py::test_a_param_the_statement_never_binds_is_refused |
| QA-SQL-023 | Given a path ending in `.sql` that does not exist / When `dbqm sql caminho.sql local -f json` / Then exit 2, `not_found`, `File "<path>" not found.` — it used to be read as SQL and come back `Unsupported SQL type` | functional | all | tests/functional/test_sql.py::test_a_missing_sql_file_says_so |
| QA-SQL-015 | Given an anonymous PL/SQL block with DBMS_OUTPUT / When `dbqm sql "BEGIN DBMS_OUTPUT.PUT_LINE('oi'); END;" <oracle> -f json` / Then `data.sql_type == "PLSQL"` and `warnings == ["oi"]` | manual | oracle | — |

## Manual (Oracle)

QA-SQL-015 — DBMS_OUTPUT capture only exists on Oracle. The mocked CLI tests
prove the CLI forwards `output_lines` as `warnings`; this row is what proves
the driver side.

```
dbqm sql "BEGIN DBMS_OUTPUT.PUT_LINE('oi'); END;" <oracle-connection> -f json
# exit 0
# "data": {"sql_type": "PLSQL", ...}, "warnings": ["oi"]
```
