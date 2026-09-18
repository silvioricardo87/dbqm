# QA — history (`HIST`)

`dbqm history [-n N] [-f table|json] [--clear]`

Every `run` and `run-group` writes one entry — success, failure or
divergence alike, since a divergence is a completed run. `history` lists
the newest first; `-n` caps the count; `--clear` empties it. The rows that
prove an entry *gets written* live with the command that writes it
(QA-QUERY-010, QA-GROUP-009); this document is about reading it back.
Envelope and exit codes: [output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-HIST-001 | Dado nenhuma execucao / Quando `dbqm history -f json` / Entao exit 0 e `data == []` | functional | all | tests/functional/test_history.py::test_an_empty_history_is_an_empty_list |
| QA-HIST-002 | Dado duas execucoes de `run ativos` / Quando `dbqm history -f json` / Entao dois registros `entry_type == "query"`, `name == "ativos"`, `connection == "local"`, `success == true`, `row_count == 2`, cada um com `id` e `timestamp` | functional | all | tests/functional/test_history.py::test_each_run_is_one_entry_with_its_facts |
| QA-HIST-003 | Dado uma execucao que falhou (`run quebrada`, tabela inexistente) / Quando `dbqm history -f json` / Entao o registro traz `success == false` e `error == "no such table: nao_existe"` | functional | all | tests/functional/test_history.py::test_a_failed_run_is_recorded_with_its_error |
| QA-HIST-004 | Dado tres execucoes / Quando `dbqm history -n 2 -f json` / Entao exatamente dois registros, os dois mais recentes | functional | all | tests/functional/test_history.py::test_n_caps_the_count_newest_first |
| QA-HIST-005 | Dado execucoes registradas / Quando `dbqm history --clear -f json` e depois `history -f json` / Entao as duas respondem `data == []` | functional | all | tests/functional/test_history.py::test_clear_empties_it |
| QA-HIST-007 | Dado `-n 0` ou `-n -5` / Quando `dbqm history -n 0 -f json` / Entao exit 2, `usage`, `-n must be greater than zero.` — `-n 0` significava 20 (o default) e `-n -5` significava “todos menos os ultimos cinco” | functional | all | tests/functional/test_history.py::test_a_limit_below_one_is_refused |
| QA-HIST-008 | Dado duas execucoes e `-n 1` / Quando executado / Entao exatamente um registro | functional | all | tests/functional/test_history.py::test_a_limit_of_one_returns_one |
| QA-HIST-006 | Dado uma execucao / Quando `dbqm history` (table) / Entao exit 0 e o nome `ativos` aparece no stdout | functional | all | tests/functional/test_history.py::test_table_format_prints_the_entries |
