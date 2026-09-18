# QA — the output contract (`OUT`)

Every command under `-f json` emits one JSON object and nothing else:

```json
{"ok": true,  "command": "sql", "data": {...}}
{"ok": false, "command": "sql", "error": {"code": "...", "message": "...", "exit": 4}}
```

The first goes to stdout with exit 0; the second to stderr with the exit the
token maps to. `ok(...)` may add `"warnings": [...]` (DBMS_OUTPUT lines,
result-set notes). On failure **stdout is empty** — that is what lets `| jq`
work. Under `-f table` the same failure prints `error.message` to stdout and
exits with the same code. `error.code` is the token a program branches on;
the message is free to be reworded. The mapping lives in
`dbqm/cli/errors.py`:

| `error.code` | exit | produced by |
|---|---|---|
| `usage` | 2 | bad invocation: DML without `--commit`, `-p` without `=`, unknown SQL verb, `--flat -e html` |
| `not_found` | 2 | a name that is not registered |
| `validation` | 2 | a value that fails a builder's rules, a missing required param |
| `read_only` | 2 | the guard refused to send the statement |
| `connection_failed` | 3 | the database did not answer |
| `sql_error` | 4 | the driver rejected or failed the statement |
| `divergent` | 5 | a comparison completed and did not match |
| `unexpected` | 1 | dbqm itself failed |

The shape is asserted **once, here**; other documents reference these IDs
instead of repeating the assertion. Exit 5 needs two databases that
disagree — [groups.md](groups.md) and [multi.md](multi.md) own the
divergence scenarios, and QA-OUT-014 below is the one that stands for the
exit code itself.

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-OUT-001 | Given any successful command / When `dbqm sql "SELECT 1 AS um" local -f json` / Then stdout is exactly one JSON object with the keys `ok`, `command`, `data` (nothing else), `ok == true`, `command == "sql"`, stderr empty, exit 0 | functional | all | tests/functional/test_output_contract.py::test_the_success_envelope_has_exactly_three_keys |
| QA-OUT-002 | Given any failure / When `dbqm sql "SELECT 1" nope -f json` / Then stderr is one object with `ok == false`, `command`, `error`, and `error` has exactly `code`, `message`, `exit`; stdout empty | functional | all | tests/functional/test_output_contract.py::test_the_failure_envelope_has_exactly_three_keys |
| QA-OUT-003 | Given a failure under `-f json` / When the process ends / Then `error.exit` equals the process's real exit code, for every token (`usage`, `not_found`, `validation`, `read_only`, `connection_failed`, `sql_error`) | functional | all | tests/functional/test_output_contract.py::test_the_exit_field_matches_the_process_exit |
| QA-OUT-004 | Given success / When `dbqm sql "SELECT 1" local -f json` / Then exit 0 | functional | all | tests/functional/test_output_contract.py::test_exit_0_on_success |
| QA-OUT-005 | Given an UPDATE without `--commit` / When run / Then exit 2 and `error.code == "usage"` | functional | all | tests/functional/test_output_contract.py::test_exit_2_usage |
| QA-OUT-006 | Given a connection that does not exist / When `dbqm sql "SELECT 1" nope -f json` / Then exit 2 and `error.code == "not_found"` | functional | all | tests/functional/test_output_contract.py::test_exit_2_not_found |
| QA-OUT-007 | Given a query with a required parameter missing / When `dbqm run por_status -f json` / Then exit 2 and `error.code == "validation"` | functional | all | tests/functional/test_output_contract.py::test_exit_2_validation |
| QA-OUT-008 | Given the `ro` connection / When `dbqm sql "DELETE FROM clientes" ro -f json` / Then exit 2 and `error.code == "read_only"` | functional | all | tests/functional/test_output_contract.py::test_exit_2_read_only |
| QA-OUT-009 | Given the `broken` connection, whose `database` is a directory / When `dbqm sql "SELECT 1" broken -f json` / Then exit 3, `error.code == "connection_failed"`, the driver's message `unable to open database file` | functional | all | tests/functional/test_output_contract.py::test_exit_3_connection_failed |
| QA-OUT-010 | Given a table that does not exist / When `dbqm sql "SELECT * FROM nao_existe" local -f json` / Then exit 4 and `error.code == "sql_error"` | functional | all | tests/functional/test_output_contract.py::test_exit_4_sql_error |
| QA-OUT-011 | Given `-f table` / When `dbqm sql "SELECT * FROM nao_existe" local` / Then the message `no such table: nao_existe` goes to stdout, stderr stays empty and the exit is still 4 | functional | all | tests/functional/test_output_contract.py::test_table_format_prints_the_failure_to_stdout_with_the_same_exit |
| QA-OUT-012 | Given `-f json` / When `dbqm sql "SELECT * FROM nao_existe" local -f json` / Then stdout is empty — not one line of prose before the envelope | functional | all | tests/functional/test_output_contract.py::test_json_failure_leaves_stdout_empty |
| QA-OUT-013 | Given the token table above / When it is read against `dbqm.cli.errors.ERROR_CODES` / Then this document's tokens and exits are exactly the code's | functional | all | tests/functional/test_output_contract.py::test_this_document_matches_the_error_table_in_code |
| QA-OUT-014 | Given `local` and `local2` disagreeing on one order / When `dbqm run-group pedidos -f json` / Then exit 5 with `ok == true` on stdout (the comparison finished; the answer is "no") and `data.all_match == false` | functional | all | tests/functional/test_run_group.py::test_a_real_divergence_exits_5 |
