# QA — ddl (`DDL`)

`dbqm ddl <object> <connection> [--stdout] [-f table|json]`

Extracts the object's DDL: to a directory of `.sql` files under
`exports/ddl/<object>/<connection>_<ts>/` by default, or to the output with
`--stdout`. A table brings its indexes (and triggers) along. Under
`-f json` the per-object progress goes to **stderr**, so stdout is the
envelope and nothing else. On SQLite the source is `sqlite_master`; on
Oracle it is `DBMS_METADATA` (manual row). Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-DDL-001 | Given `customers` / When `dbqm ddl customers local --stdout -f json` / Then exit 0, `data.path == null`, `data.objects` carries `customers` (`TABLE`, ddl starting with `CREATE TABLE customers`) and `ix_customers_name` (`INDEX`, `CREATE UNIQUE INDEX ix_customers_name ON customers(name);`) | functional | all | tests/functional/test_ddl.py::test_stdout_returns_the_create_table_and_its_index |
| QA-DDL-002 | Given `-f json` / When the command finishes / Then stdout is the envelope alone (it parses) and the progress `[1/2] TABLE: customers` went to stderr | functional | all | tests/functional/test_ddl.py::test_json_keeps_the_progress_off_stdout |
| QA-DDL-003 | Given `--stdout` without `-f json` / When `dbqm ddl customers local --stdout` / Then `CREATE TABLE customers` and `CREATE UNIQUE INDEX ix_customers_name` appear on stdout | functional | all | tests/functional/test_ddl.py::test_stdout_table_format_prints_the_ddl |
| QA-DDL-004 | Given `v_active` / When `dbqm ddl v_active local --stdout -f json` / Then one `VIEW` object whose ddl is `CREATE VIEW v_active AS SELECT id, name FROM customers WHERE status = 'A';` | functional | all | tests/functional/test_ddl.py::test_a_view_is_extracted |
| QA-DDL-005 | Given no `--stdout` / When `dbqm ddl customers local -f json` / Then `data.path` is an existing directory under the export folder holding a `.sql` with `CREATE TABLE customers` | functional | all | tests/functional/test_ddl.py::test_without_stdout_a_sql_file_is_written |
| QA-DDL-006 | Given a name that does not exist / When `dbqm ddl nao_existe local -f json` / Then exit 2, `not_found`, `Object 'nao_existe' not found.` | functional | all | tests/functional/test_ddl.py::test_an_unknown_object_is_not_found |
| QA-DDL-007 | Given a connection that is not registered / When `dbqm ddl customers nope -f json` / Then exit 2, `not_found`, `Connection "nope" not found.` | functional | all | tests/functional/test_ddl.py::test_an_unknown_connection_is_not_found |
| QA-DDL-008 | Given an Oracle table / When `dbqm ddl <table> <oracle> --stdout -f json` / Then the DDL comes from `DBMS_METADATA.GET_DDL` and includes indexes and constraints | manual | oracle | — |

## Manual (Oracle)

QA-DDL-008 — the Oracle extractor (`DBMS_METADATA`, dependents, grants)
is unit-tested with mocks in `tests/core/test_ddl_extractor.py`; this is
the run against a real dictionary. Before 2.9.0 the CLI ran this Oracle
SQL on every engine — found by the SQLite scenarios above.

```
dbqm ddl <TABLE> <oracle-connection> --stdout -f json
# exit 0; stderr: "[1/N] TABLE: <TABLE>" ...
# "data": {"objects": [{"name": "<TABLE>", "obj_type": "TABLE", "ddl": "CREATE TABLE ..."}, ...], "path": null}
```
