# QA — `multi`, one SQL across connections (`MULTI`)

`dbqm multi <sql|file.sql> -c <a> -c <b> [...] [--key <col>] [-p k=v] [-f table|json] [-e csv|json|txt|html] [--flat]`

Runs one query on every named connection and compares the result sets on
their common columns: the join key is the first common column unless
`--key` names another, and every other common column is compared. Same
verdict rule as `run-group`: **0 consistent, 5 divergent**, export or not.
Everything that can be refused is refused **before any connection opens**:
`--flat -e html`, fewer than two distinct connections, a statement that
returns no result set, a name that is not registered.

Fixture: `local` and `local2` (`tests/functional/conftest.py::local2_db`) differ
on order 13 only (`valor` 5.25 vs 6.0). Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-MULTI-001 | Given `local` and `local2` / When `dbqm multi "SELECT id, nome FROM clientes ORDER BY id" -c local -c local2 -f json` / Then exit 0, `data.join_key == "id"`, `data.all_match == true`, the `nome` comparison with `equal_count 3` | functional | all | tests/functional/test_multi.py::test_two_connections_that_agree_exit_0 |
| QA-MULTI-002 | Given the same pair / When `dbqm multi "SELECT id, valor FROM pedidos ORDER BY id" -c local -c local2 -f json` / Then **exit 5**, `ok == true`, `data.all_match == false`, the `valor` comparison with `total_keys 4`, `equal_count 3`, `diff_count 1` | functional | all | tests/functional/test_multi.py::test_two_connections_that_differ_exit_5 |
| QA-MULTI-003 | Given `--key cliente_id` / When `dbqm multi "SELECT id, valor, cliente_id FROM pedidos" -c local -c local2 --key cliente_id -f json` / Then `data.join_key == "cliente_id"` and the comparisons are `id` and `valor` (the key left the compared list, the rest stayed) | functional | all | tests/functional/test_multi.py::test_key_overrides_the_join_column_and_is_reported |
| QA-MULTI-004 | Given `--key nope` / When run / Then exit 2, `validation`, `Key column "nope" is not common to every connection.` | functional | all | tests/functional/test_multi.py::test_a_key_that_is_not_common_is_validation |
| QA-MULTI-005 | Given `-c local -c local` / When run / Then exit 2, `usage`, `Connection "local" is repeated. Give at least two distinct connections with -c/--connection.` | functional | all | tests/functional/test_multi.py::test_the_same_connection_twice_is_refused |
| QA-MULTI-006 | Given a single `-c` / When run / Then exit 2, `usage`, `Give at least two connections with -c/--connection.` | functional | all | tests/functional/test_multi.py::test_one_connection_is_refused |
| QA-MULTI-007 | Given `DELETE FROM pedidos` / When `dbqm multi "DELETE FROM pedidos" -c local -c local2 -f json` / Then exit 2, `usage`, `multi compares query results (SELECT or EXPLAIN); got: DELETE.` and `pedidos` still has 4 rows on both connections | functional | all | tests/functional/test_multi.py::test_a_non_query_is_refused_before_any_connection_opens |
| QA-MULTI-008 | Given `broken` (a file that will not open) among the connections / When `dbqm multi ... -c local -c broken -f json` / Then exit 3, `connection_failed`, the message `Connection "broken" failed: unable to open database file` — it names which one | functional | all | tests/functional/test_multi.py::test_one_missing_file_is_connection_failed_naming_it |
| QA-MULTI-009 | Given a name that is not registered / When `-c local -c nope` / Then exit 2, `not_found`, `Connection "nope" not found.` | functional | all | tests/functional/test_multi.py::test_an_unregistered_name_is_not_found |
| QA-MULTI-010 | Given `-e html` on a divergent comparison / When `dbqm multi "SELECT id, valor FROM pedidos ORDER BY id" -c local -c local2 -e html -f json` / Then the `.html` exists and carries `<table`, `data.join_key == "id"`, `data.format == "html"` and the exit is still 5 | functional | all | tests/functional/test_multi.py::test_export_html_writes_and_keeps_the_verdict |
| QA-MULTI-011 | Given `--flat -e html` / When run / Then exit 2, `usage`, `--flat has no HTML version. ...` | functional | all | tests/functional/test_multi.py::test_flat_with_html_is_refused |
| QA-MULTI-012 | Given a query with a single column / When `dbqm multi "SELECT id FROM pedidos" -c local -c local2 -f json` / Then exit 2, `validation`, `Column "id" is the only one common to every connection; there is no column left to compare.` | functional | all | tests/functional/test_multi.py::test_a_single_common_column_has_nothing_to_compare |
| QA-MULTI-013 | Given a table that does not exist / When `dbqm multi "SELECT * FROM nao_existe" -c local -c local2 -f json` / Then exit 4, `sql_error`, and the message names **both** connections: `Error in the query on "local": no such table: nao_existe; Error in the query on "local2": ...` | functional | all | tests/functional/test_multi.py::test_every_failing_connection_is_named |
| QA-MULTI-015 | Given `SELECT cliente_id AS id, valor FROM pedidos` on both connections / When `dbqm multi ... -c local -c local2 -f json` / Then `join_key == "id"`, `warnings` names both connections and `duplicate_rows == {"local": 2, "local2": 2}` — `multi` derives the key itself, so an ambiguous key is easier to hit here than in a curated group | functional | all | tests/functional/test_multi.py::test_a_repeated_derived_key_is_reported |
| QA-MULTI-016 | Given a unique derived key / When run / Then the envelope carries no `warnings` | functional | all | tests/functional/test_multi.py::test_a_unique_derived_key_warns_about_nothing |
| QA-MULTI-017 | Given `-p naoexiste=1` / When run / Then exit 2, `validation`, `The SQL does not use the parameter "naoexiste".` | functional | all | tests/functional/test_multi.py::test_a_param_the_statement_never_binds_is_refused |
| QA-MULTI-018 | Given a `.sql` path that does not exist / When run / Then exit 2, `not_found`, naming the file | functional | all | tests/functional/test_multi.py::test_a_missing_sql_file_says_so |
| QA-MULTI-014 | Given `-f table` / When `dbqm multi "SELECT id, valor FROM pedidos ORDER BY id" -c local -c local2` / Then exit 5 and `DIVERGENT` and `key: id` on stdout | functional | all | tests/functional/test_multi.py::test_table_format_prints_the_verdict_with_the_same_exit |
