# QA — schema discovery (`DISC`)

`dbqm objects <connection> [--type TABLE|VIEW|PACKAGE|ROUTINE]`,
`dbqm describe <object> <connection>`, `dbqm rows <table> <connection> [--limit N] [--offset N]`.

What an agent runs before writing SQL against a database it has not seen:
the names, then one object's columns/keys/indexes, then a page of rows.
A type the engine does not have is `usage` and the message names the
engine. Seed: `customers` (PK `id`, unique index `ix_customers_name`),
`orders` (FK `customer_id -> customers.id`), view `v_active`. Envelope and
exit codes: [output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-DISC-001 | Given `local` / When `dbqm objects local -f json` (default type TABLE) / Then exit 0, `data.obj_type == "TABLE"` and `data.objects == ["customers","orders"]` | functional | all | tests/functional/test_discovery.py::test_objects_lists_the_seed_tables |
| QA-DISC-002 | Given `local` / When `dbqm objects local --type VIEW -f json` / Then `data.objects == ["v_active"]` | functional | all | tests/functional/test_discovery.py::test_objects_lists_the_seed_view |
| QA-DISC-003 | Given `local` (sqlite) / When `dbqm objects local --type PACKAGE -f json` / Then exit 2, `usage`, `Packages only exist on Oracle. This connection is sqlite.` | functional | sqlite | tests/functional/test_discovery.py::test_packages_on_sqlite_is_usage_naming_the_engine |
| QA-DISC-004 | Given `local` (sqlite) / When `dbqm objects local --type ROUTINE -f json` / Then exit 2, `usage`, `SQLite has no stored routines.` | functional | sqlite | tests/functional/test_discovery.py::test_routines_on_sqlite_is_usage |
| QA-DISC-005 | Given `customers` / When `dbqm describe customers local -f json` / Then `data.object_type == "TABLE"`, columns `id` (`is_pk == true`, `INTEGER`), `name` (`nullable == false`, `TEXT`), `status`; and `data.indexes == [{"name":"ix_customers_name","columns":["name"],"is_unique":true}]` | functional | all | tests/functional/test_discovery.py::test_describe_reports_pk_nullability_and_the_unique_index |
| QA-DISC-006 | Given `orders` / When `dbqm describe orders local -f json` / Then the `customer_id` column carries `fk_ref == "customers.id"` | functional | all | tests/functional/test_discovery.py::test_describe_reports_the_foreign_key |
| QA-DISC-007 | Given `v_active` / When `dbqm describe v_active local -f json` / Then `data.object_type == "VIEW"`, columns `id` and `name`, and `data.sql_definition` starts with `CREATE VIEW v_active` | functional | all | tests/functional/test_discovery.py::test_describe_a_view_brings_its_definition |
| QA-DISC-008 | Given a name that does not exist / When `dbqm describe nao_existe local -f json` / Then exit 2, `not_found`, `"nao_existe" is neither a table nor a view in local.` | functional | all | tests/functional/test_discovery.py::test_describe_of_an_unknown_object_is_not_found |
| QA-DISC-009 | Given `-f table` / When `dbqm describe customers local` / Then exit 0 and `PK`, `ix_customers_name` and `UNIQUE` appear on stdout | functional | all | tests/functional/test_discovery.py::test_describe_table_format_prints_keys_and_indexes |
| QA-DISC-010 | Given `customers` / When `dbqm rows customers local -f json` / Then `data.rows` are the 3 seeded rows, `row_count == 3`, `total_count == 3`, `limit == 100`, `offset == 0` | functional | all | tests/functional/test_discovery.py::test_rows_returns_the_seed |
| QA-DISC-011 | Given `--limit 2` then `--limit 2 --offset 2` / When run / Then the first brings Ana and Bia with `total_count == 3`; the second brings only Caio, `row_count == 1`, `offset == 2` | functional | all | tests/functional/test_discovery.py::test_rows_pages_with_limit_and_offset |
| QA-DISC-012 | Given `--limit 0` or `--offset -1` / When run / Then exit 2, `usage`, `--limit must be greater than zero.` / `--offset cannot be negative.` | functional | all | tests/functional/test_discovery.py::test_rows_refuses_a_bad_page |
| QA-DISC-013 | Given a table that does not exist / When `dbqm rows nao_existe local -f json` / Then exit 2, `not_found`, `Table "nao_existe" not found in local.` | functional | all | tests/functional/test_discovery.py::test_rows_of_an_unknown_table_is_not_found |
| QA-DISC-014 | Given `-f csv` / When `dbqm rows customers local -f csv` / Then stdout starts with `id,name,status` and has one line per row | functional | all | tests/functional/test_discovery.py::test_rows_csv_prints_a_header_and_the_rows |
| QA-DISC-015 | Given a connection that is not registered / When `dbqm objects nope -f json` / Then exit 2, `not_found`, `Connection "nope" not found.` | functional | all | tests/functional/test_discovery.py::test_objects_of_an_unknown_connection_is_not_found |
| QA-DISC-016 | Given an Oracle connection with a package / When `dbqm objects <oracle> --type PACKAGE -f json` and `--type ROUTINE` / Then the owner's names from `ALL_OBJECTS` | manual | oracle | — |

## Manual (Oracle)

QA-DISC-016 — the Oracle catalogue arms (`ALL_OBJECTS`, `ALL_PROCEDURES`)
are unit-tested with mocks in `tests/core/test_object_browser.py`; this is
the confirmation against a real dictionary.

```
dbqm objects <oracle-connection> --type PACKAGE -f json
# "data": {"obj_type": "PACKAGE", "objects": ["PKG_...", ...]}
dbqm objects <oracle-connection> --type ROUTINE -f json
# "data": {"obj_type": "ROUTINE", "objects": ["PROC_...", "FN_...", ...]}
```
