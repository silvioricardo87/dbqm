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
instead of repeating the assertion. Exit 5 is produced by a real divergence
in [groups.md](groups.md) / [multi.md](multi.md) — its row joins this table
with the comparison task, when the test that produces it exists.

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-OUT-001 | Dado qualquer comando bem-sucedido / Quando `dbqm sql "SELECT 1 AS um" local -f json` / Entao stdout e exatamente um objeto JSON com as chaves `ok`, `command`, `data` (nada mais), `ok == true`, `command == "sql"`, stderr vazio, exit 0 | functional | all | tests/functional/test_output_contract.py::test_the_success_envelope_has_exactly_three_keys |
| QA-OUT-002 | Dado qualquer falha / Quando `dbqm sql "SELECT 1" nope -f json` / Entao stderr e um objeto com `ok == false`, `command`, `error` e `error` tem exatamente `code`, `message`, `exit`; stdout vazio | functional | all | tests/functional/test_output_contract.py::test_the_failure_envelope_has_exactly_three_keys |
| QA-OUT-003 | Dado uma falha sob `-f json` / Quando o processo termina / Entao `error.exit` e igual ao exit code real do processo, para cada token (`usage`, `not_found`, `validation`, `read_only`, `connection_failed`, `sql_error`) | functional | all | tests/functional/test_output_contract.py::test_the_exit_field_matches_the_process_exit |
| QA-OUT-004 | Dado sucesso / Quando `dbqm sql "SELECT 1" local -f json` / Entao exit 0 | functional | all | tests/functional/test_output_contract.py::test_exit_0_on_success |
| QA-OUT-005 | Dado um UPDATE sem `--commit` / Quando executado / Entao exit 2 e `error.code == "usage"` | functional | all | tests/functional/test_output_contract.py::test_exit_2_usage |
| QA-OUT-006 | Dado uma conexao que nao existe / Quando `dbqm sql "SELECT 1" nope -f json` / Entao exit 2 e `error.code == "not_found"` | functional | all | tests/functional/test_output_contract.py::test_exit_2_not_found |
| QA-OUT-007 | Dado uma consulta com parametro obrigatorio ausente / Quando `dbqm run por_status -f json` / Entao exit 2 e `error.code == "validation"` | functional | all | tests/functional/test_output_contract.py::test_exit_2_validation |
| QA-OUT-008 | Dado a conexao `ro` / Quando `dbqm sql "DELETE FROM clientes" ro -f json` / Entao exit 2 e `error.code == "read_only"` | functional | all | tests/functional/test_output_contract.py::test_exit_2_read_only |
| QA-OUT-009 | Dado a conexao `broken` cujo `database` e um diretorio / Quando `dbqm sql "SELECT 1" broken -f json` / Entao exit 3, `error.code == "connection_failed"`, mensagem do driver `unable to open database file` | functional | all | tests/functional/test_output_contract.py::test_exit_3_connection_failed |
| QA-OUT-010 | Dado uma tabela que nao existe / Quando `dbqm sql "SELECT * FROM nao_existe" local -f json` / Entao exit 4 e `error.code == "sql_error"` | functional | all | tests/functional/test_output_contract.py::test_exit_4_sql_error |
| QA-OUT-011 | Dado `-f table` / Quando `dbqm sql "SELECT * FROM nao_existe" local` / Entao a mensagem `no such table: nao_existe` vai para o stdout, stderr fica vazio e o exit continua 4 | functional | all | tests/functional/test_output_contract.py::test_table_format_prints_the_failure_to_stdout_with_the_same_exit |
| QA-OUT-012 | Dado `-f json` / Quando `dbqm sql "SELECT * FROM nao_existe" local -f json` / Entao stdout esta vazio — nem uma linha de prosa antes do envelope | functional | all | tests/functional/test_output_contract.py::test_json_failure_leaves_stdout_empty |
| QA-OUT-013 | Dado a tabela de tokens acima / Quando lida contra `dbqm.cli.errors.ERROR_CODES` / Entao os tokens e os exits deste documento sao exatamente os do codigo | functional | all | tests/functional/test_output_contract.py::test_this_document_matches_the_error_table_in_code |
