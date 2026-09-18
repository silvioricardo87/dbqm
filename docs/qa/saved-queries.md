# QA — saved queries, the run half (`QUERY`)

`dbqm query add <nome> --connection <c> --sql <sql>` then
`dbqm run <nome> [-c conexao] [-p k=v] [-f ...] [-e ...]`.

The CRUD half (`update`, `show`, `rm`, `list`) belongs to the curation
documents; this one is only what `run` does with a query once it exists.
`:nome` placeholders in the SQL become required params (`detect_params`).
Envelope and exit codes: [output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-QUERY-001 | Dado `dbqm query add ativos --connection local --sql "SELECT id, nome FROM clientes WHERE status = 'A' ORDER BY id"` / Quando `dbqm run ativos -f json` / Entao exit 0, `command == "run"`, `data.query_name == "ativos"`, `data.rows == [[1,"Ana"],[3,"Caio"]]` | functional | all | tests/functional/test_run.py::test_query_add_then_run_end_to_end |
| QA-QUERY-002 | Dado uma consulta com `:st` no SQL / Quando `dbqm run por_status -p st=I -f json` / Entao `data.rows == [[2,"Bia"]]` — o `-p` chegou ao bind | functional | all | tests/functional/test_run.py::test_a_param_reaches_the_sql |
| QA-QUERY-003 | Dado a mesma consulta / Quando `dbqm run por_status -f json` sem `-p` / Entao exit 2, `error.code == "validation"`, mensagem `Required parameters missing: st` | functional | all | tests/functional/test_run.py::test_a_missing_required_param_is_validation |
| QA-QUERY-004 | Dado a conexao `ro` (somente leitura) / Quando `dbqm run ativos -c ro -f json` / Entao exit 0 e `data.connection_name == "ro"` — um SELECT passa pela guarda | functional | all | tests/functional/test_run.py::test_a_select_runs_on_a_read_only_connection |
| QA-QUERY-005 | Dado uma consulta que nao existe / Quando `dbqm run nope -f json` / Entao exit 2, `not_found`, `Query "nope" not found.` | functional | all | tests/functional/test_run.py::test_an_unknown_query_is_not_found |
| QA-QUERY-006 | Dado `-c` com conexao inexistente / Quando `dbqm run ativos -c nope -f json` / Entao exit 2, `not_found`, `Connection "nope" not found.` | functional | all | tests/functional/test_run.py::test_an_unknown_connection_override_is_not_found |
| QA-QUERY-007 | Dado uma consulta cujo SQL le uma tabela inexistente / Quando `dbqm run quebrada -f json` / Entao exit 4, `sql_error`, mensagem do driver `no such table: nao_existe` | functional | all | tests/functional/test_run.py::test_a_query_the_driver_rejects_is_sql_error |
| QA-QUERY-008 | Dado `-e csv` / Quando `dbqm run ativos -e csv -f json` / Entao `data.exported` e um `.csv` existente cujo cabecalho e `id,nome` e `data.format == "csv"` | functional | all | tests/functional/test_run.py::test_export_writes_the_file_and_reports_it |
| QA-QUERY-009 | Dado `-f table` / Quando `dbqm run ativos` / Entao exit 0 e `Ana` e `Caio` aparecem no stdout | functional | all | tests/functional/test_run.py::test_table_format_prints_the_rows |
| QA-QUERY-011 | Dado a tela **Consultas** da TUI e a consulta `ativos` salva / Quando executada / Entao a barra de informacao traz `ativos`, `local` e `2 registros`, e a tabela traz 2 linhas | functional | all | tests/ui/test_functional_screens.py::test_query_exec_runs_a_saved_query_and_shows_the_row_count |
| QA-QUERY-012 | Dado `-p naoexiste=1` numa consulta que nao declara esse parametro / Quando `dbqm run ativos -p naoexiste=1 -f json` / Entao exit 2, `validation`, `Query "ativos" does not declare the parameter "naoexiste".` — antes rodava sem filtrar e devolvia as linhas como resultado | functional | all | tests/functional/test_run.py::test_a_param_the_query_does_not_declare_is_refused |
| QA-QUERY-013 | Dado um `-p` valido junto de um invalido / Quando executado / Entao a recusa nomeia o invalido | functional | all | tests/functional/test_run.py::test_a_declared_param_alongside_an_undeclared_one_is_still_refused |
| QA-QUERY-010 | Dado uma execucao com sucesso / Quando `dbqm run ativos -f json` e depois `dbqm history -f json` / Entao o historico traz um registro com `name == "ativos"`, `connection == "local"` e `entry_type == "query"` | functional | all | tests/functional/test_run.py::test_a_run_is_recorded_in_history |
