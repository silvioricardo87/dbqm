# QA — saved queries, the run half (`QUERY`)

`dbqm query add <name> --connection <c> --sql <sql>` then
`dbqm run <name> [-c connection] [-p k=v] [-f ...] [-e ...]`.

The CRUD half (`update`, `show`, `rm`, `list`) belongs to the curation
documents; this one is only what `run` does with a query once it exists.
`:name` placeholders in the SQL become required params (`detect_params`).
Envelope and exit codes: [output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-QUERY-001 | Given `dbqm query add ativos --connection local --sql "SELECT id, nome FROM clientes WHERE status = 'A' ORDER BY id"` / When `dbqm run ativos -f json` / Then exit 0, `command == "run"`, `data.query_name == "ativos"`, `data.rows == [[1,"Ana"],[3,"Caio"]]` | functional | all | tests/functional/test_run.py::test_query_add_then_run_end_to_end |
| QA-QUERY-002 | Given a query with `:st` in its SQL / When `dbqm run por_status -p st=I -f json` / Then `data.rows == [[2,"Bia"]]` — the `-p` reached the bind | functional | all | tests/functional/test_run.py::test_a_param_reaches_the_sql |
| QA-QUERY-003 | Given the same query / When `dbqm run por_status -f json` without `-p` / Then exit 2, `error.code == "validation"`, message `Required parameters missing: st` | functional | all | tests/functional/test_run.py::test_a_missing_required_param_is_validation |
| QA-QUERY-004 | Given the `ro` connection (read-only) / When `dbqm run ativos -c ro -f json` / Then exit 0 and `data.connection_name == "ro"` — a SELECT passes the guard | functional | all | tests/functional/test_run.py::test_a_select_runs_on_a_read_only_connection |
| QA-QUERY-005 | Given a query that does not exist / When `dbqm run nope -f json` / Then exit 2, `not_found`, `Query "nope" not found.` | functional | all | tests/functional/test_run.py::test_an_unknown_query_is_not_found |
| QA-QUERY-006 | Given `-c` naming a connection that does not exist / When `dbqm run ativos -c nope -f json` / Then exit 2, `not_found`, `Connection "nope" not found.` | functional | all | tests/functional/test_run.py::test_an_unknown_connection_override_is_not_found |
| QA-QUERY-007 | Given a query whose SQL reads a missing table / When `dbqm run quebrada -f json` / Then exit 4, `sql_error`, the driver's message `no such table: nao_existe` | functional | all | tests/functional/test_run.py::test_a_query_the_driver_rejects_is_sql_error |
| QA-QUERY-008 | Given `-e csv` / When `dbqm run ativos -e csv -f json` / Then `data.exported` is an existing `.csv` whose header is `id,nome`, and `data.format == "csv"` | functional | all | tests/functional/test_run.py::test_export_writes_the_file_and_reports_it |
| QA-QUERY-009 | Given `-f table` / When `dbqm run ativos` / Then exit 0 and `Ana` and `Caio` appear on stdout | functional | all | tests/functional/test_run.py::test_table_format_prints_the_rows |
| QA-QUERY-011 | Given the TUI's **Queries** screen and the saved query `ativos` / When it runs / Then the info bar carries `ativos`, `local` and `2 rows`, and the table carries 2 rows | functional | all | tests/ui/test_functional_screens.py::test_query_exec_runs_a_saved_query_and_shows_the_row_count |
| QA-QUERY-012 | Given `-p naoexiste=1` on a query that does not declare that parameter / When `dbqm run ativos -p naoexiste=1 -f json` / Then exit 2, `validation`, `Query "ativos" does not declare the parameter "naoexiste".` — it used to run unfiltered and return the rows as a result | functional | all | tests/functional/test_run.py::test_a_param_the_query_does_not_declare_is_refused |
| QA-QUERY-013 | Given one valid `-p` beside an invalid one / When run / Then the refusal names the invalid one | functional | all | tests/functional/test_run.py::test_a_declared_param_alongside_an_undeclared_one_is_still_refused |
| QA-QUERY-010 | Given a successful run / When `dbqm run ativos -f json` then `dbqm history -f json` / Then the history carries one entry with `name == "ativos"`, `connection == "local"` and `entry_type == "query"` | functional | all | tests/functional/test_run.py::test_a_run_is_recorded_in_history |
