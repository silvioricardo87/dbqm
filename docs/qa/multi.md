# QA — `multi`, one SQL across connections (`MULTI`)

`dbqm multi <sql|arquivo.sql> -c <a> -c <b> [...] [--key <col>] [-p k=v] [-f table|json] [-e csv|json|txt|html] [--flat]`

Runs one query on every named connection and compares the result sets on
their common columns: the join key is the first common column unless
`--key` names another, and every other common column is compared. Same
verdict rule as `run-group`: **0 consistent, 5 divergent**, export or not.
Everything that can be refused is refused **before any connection opens**:
`--flat -e html`, fewer than two distinct connections, a statement that
returns no result set, a name that is not registered.

Fixture: `local` and `local2` (`tests/functional/conftest.py::local2_db`) differ
in pedido 13 only (`valor` 5.25 vs 6.0). Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-MULTI-001 | Dado `local` e `local2` / Quando `dbqm multi "SELECT id, nome FROM clientes ORDER BY id" -c local -c local2 -f json` / Entao exit 0, `data.join_key == "id"`, `data.all_match == true`, comparacao `nome` com `equal_count 3` | functional | all | tests/functional/test_multi.py::test_two_connections_that_agree_exit_0 |
| QA-MULTI-002 | Dado o mesmo par / Quando `dbqm multi "SELECT id, valor FROM pedidos ORDER BY id" -c local -c local2 -f json` / Entao **exit 5**, `ok == true`, `data.all_match == false`, comparacao `valor` com `total_keys 4`, `equal_count 3`, `diff_count 1` | functional | all | tests/functional/test_multi.py::test_two_connections_that_differ_exit_5 |
| QA-MULTI-003 | Dado `--key cliente_id` / Quando `dbqm multi "SELECT id, valor, cliente_id FROM pedidos" -c local -c local2 --key cliente_id -f json` / Entao `data.join_key == "cliente_id"` e as comparacoes sao `id` e `valor` (a chave saiu da lista comparada, o resto ficou) | functional | all | tests/functional/test_multi.py::test_key_overrides_the_join_column_and_is_reported |
| QA-MULTI-004 | Dado `--key nope` / Quando executado / Entao exit 2, `validation`, `Key column "nope" is not common to every connection.` | functional | all | tests/functional/test_multi.py::test_a_key_that_is_not_common_is_validation |
| QA-MULTI-005 | Dado `-c local -c local` / Quando executado / Entao exit 2, `usage`, `Connection "local" is repeated. Give at least two distinct connections with -c/--connection.` | functional | all | tests/functional/test_multi.py::test_the_same_connection_twice_is_refused |
| QA-MULTI-006 | Dado um so `-c` / Quando executado / Entao exit 2, `usage`, `Give at least two connections with -c/--connection.` | functional | all | tests/functional/test_multi.py::test_one_connection_is_refused |
| QA-MULTI-007 | Dado `DELETE FROM pedidos` / Quando `dbqm multi "DELETE FROM pedidos" -c local -c local2 -f json` / Entao exit 2, `usage`, `multi compares query results (SELECT or EXPLAIN); got: DELETE.` e `pedidos` continua com 4 linhas nas duas conexoes | functional | all | tests/functional/test_multi.py::test_a_non_query_is_refused_before_any_connection_opens |
| QA-MULTI-008 | Dado `broken` (arquivo que nao abre) entre as conexoes / Quando `dbqm multi ... -c local -c broken -f json` / Entao exit 3, `connection_failed`, mensagem `Connection "broken" failed: unable to open database file` — nomeia qual | functional | all | tests/functional/test_multi.py::test_one_missing_file_is_connection_failed_naming_it |
| QA-MULTI-009 | Dado um nome nao registrado / Quando `-c local -c nope` / Entao exit 2, `not_found`, `Connection "nope" not found.` | functional | all | tests/functional/test_multi.py::test_an_unregistered_name_is_not_found |
| QA-MULTI-010 | Dado `-e html` numa comparacao divergente / Quando `dbqm multi "SELECT id, valor FROM pedidos ORDER BY id" -c local -c local2 -e html -f json` / Entao o `.html` existe e contem `<table`, `data.join_key == "id"`, `data.format == "html"` e o exit continua 5 | functional | all | tests/functional/test_multi.py::test_export_html_writes_and_keeps_the_verdict |
| QA-MULTI-011 | Dado `--flat -e html` / Quando executado / Entao exit 2, `usage`, `--flat has no HTML version. ...` | functional | all | tests/functional/test_multi.py::test_flat_with_html_is_refused |
| QA-MULTI-012 | Dado uma consulta com uma so coluna / Quando `dbqm multi "SELECT id FROM pedidos" -c local -c local2 -f json` / Entao exit 2, `validation`, `Column "id" is the only one common to every connection; there is no column left to compare.` | functional | all | tests/functional/test_multi.py::test_a_single_common_column_has_nothing_to_compare |
| QA-MULTI-013 | Dado uma tabela inexistente / Quando `dbqm multi "SELECT * FROM nao_existe" -c local -c local2 -f json` / Entao exit 4, `sql_error`, e a mensagem nomeia **as duas** conexoes: `Error in the query on "local": no such table: nao_existe; Error in the query on "local2": ...` | functional | all | tests/functional/test_multi.py::test_every_failing_connection_is_named |
| QA-MULTI-015 | Dado `SELECT cliente_id AS id, valor FROM pedidos` nas duas conexoes / Quando `dbqm multi ... -c local -c local2 -f json` / Entao `join_key == "id"`, `warnings` nomeia as duas conexoes e `duplicate_rows == {"local": 2, "local2": 2}` — `multi` deriva a chave sozinho, entao uma chave ambigua e mais facil de acertar aqui do que num grupo curado | functional | all | tests/functional/test_multi.py::test_a_repeated_derived_key_is_reported |
| QA-MULTI-016 | Dado uma chave derivada unica / Quando executado / Entao o envelope nao traz `warnings` | functional | all | tests/functional/test_multi.py::test_a_unique_derived_key_warns_about_nothing |
| QA-MULTI-017 | Dado `-p naoexiste=1` / Quando executado / Entao exit 2, `validation`, `The SQL does not use the parameter "naoexiste".` | functional | all | tests/functional/test_multi.py::test_a_param_the_statement_never_binds_is_refused |
| QA-MULTI-018 | Dado um caminho `.sql` que nao existe / Quando executado / Entao exit 2, `not_found`, nomeando o arquivo | functional | all | tests/functional/test_multi.py::test_a_missing_sql_file_says_so |
| QA-MULTI-014 | Dado `-f table` / Quando `dbqm multi "SELECT id, valor FROM pedidos ORDER BY id" -c local -c local2` / Entao exit 5 e `DIVERGENT` e `chave: id` no stdout | functional | all | tests/functional/test_multi.py::test_table_format_prints_the_verdict_with_the_same_exit |
