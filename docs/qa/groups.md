# QA — groups and `run-group` (`GROUP`)

`dbqm group add <nome> --query <q1> --query <q2> --join-key <col> [--compare-column <col>]...`
then `dbqm run-group <nome> [-p k=v] [-f table|json] [-e csv|json|txt|html] [--flat]`.

A group names two or more saved queries, each on its own connection, and a
join key; `run-group` runs them all and compares the named columns row by
row. The verdict is the exit code: **0 consistent, 5 divergent** — under
every format and even after an export was written. The CRUD half of `group`
belongs to the curation documents.

A join key whose values repeat on the same side collapses: the index
keeps the last row under each key. The comparison still runs — what
changed in 2.10.0 is that it says so, in `warnings` and in
`comparisons[*].duplicate_rows`, instead of reporting a verdict over rows
it never told apart.

Fixture: `local` and `local2` (`tests/functional/conftest.py::local2_db`) are
the same schema and data except pedido 13 (`valor` 5.25 vs 6.0). The queries
`ped_*` read `pedidos` (diverge), `cli_*` read `clientes` (agree). Envelope
and exit codes: [output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-GROUP-001 | Dado `cli_local` e `cli_local2` salvas / Quando `dbqm group add clientes --query cli_local --query cli_local2 --join-key id --compare-column nome -f json` e depois `dbqm run-group clientes -f json` / Entao a primeira retorna `data == {"name":"clientes","created":true}` e a segunda exit 0, `data.all_match == true`, uma comparacao `nome` com `total_keys 3`, `equal_count 3`, `diff_count 0` | functional | all | tests/functional/test_run_group.py::test_group_add_then_run_group_that_agrees |
| QA-GROUP-002 | Dado o grupo `pedidos` sobre `ped_local`/`ped_local2` / Quando `dbqm run-group pedidos -f json` / Entao **exit 5**, `ok == true` no stdout, `data.all_match == false`, comparacao `valor` com `total_keys 4`, `equal_count 3`, `diff_count 1` | functional | all | tests/functional/test_run_group.py::test_a_real_divergence_exits_5 |
| QA-GROUP-003 | Dado o grupo `pedidos` / Quando `dbqm run-group pedidos` (table) / Entao exit 5 e `DIVERGENT` no stdout; para `clientes`, exit 0 e `CONSISTENT` | functional | all | tests/functional/test_run_group.py::test_table_format_prints_the_verdict_with_the_same_exit |
| QA-GROUP-004 | Dado o grupo `pedidos` / Quando `dbqm run-group pedidos -e html -f json` / Entao o `.html` e escrito (existe, contem `<table`), `data.format == "html"` **e o exit continua 5** | functional | all | tests/functional/test_run_group.py::test_export_html_still_exits_5_after_writing |
| QA-GROUP-005 | Dado `--flat -e html` / Quando `dbqm run-group pedidos --flat -e html -f json` / Entao exit 2, `usage`, mensagem `--flat has no HTML version. ...` e nada foi executado: o historico nao ganha registro | functional | all | tests/functional/test_run_group.py::test_flat_with_html_is_refused_before_anything_runs |
| QA-GROUP-006 | Dado `--flat -e csv` / Quando `dbqm run-group pedidos --flat -e csv -f json` / Entao o arquivo `flat_*.csv` existe e o exit e 5 | functional | all | tests/functional/test_run_group.py::test_flat_csv_writes_and_keeps_the_verdict |
| QA-GROUP-007 | Dado um grupo que nao existe / Quando `dbqm run-group nope -f json` / Entao exit 2, `not_found`, `Group "nope" not found.` | functional | all | tests/functional/test_run_group.py::test_an_unknown_group_is_not_found |
| QA-GROUP-008 | Dado `group add` com uma so consulta / Quando `dbqm group add um --query cli_local --join-key id -f json` / Entao exit 2, `validation`, `Select at least 2 queries.` | functional | all | tests/functional/test_run_group.py::test_a_group_needs_two_queries |
| QA-GROUP-009 | Dado uma execucao divergente / Quando `dbqm history -f json` / Entao ha um registro `entry_type == "group"`, `name == "pedidos"`, `all_match == false` — a divergencia e uma execucao completa, nao abortada | functional | all | tests/functional/test_run_group.py::test_a_divergent_run_is_still_recorded_in_history |
| QA-GROUP-011 | Dado um grupo cuja chave `id` vem de `cliente_id` (quatro pedidos, dois clientes) / Quando `dbqm run-group por_cliente -f json` / Entao exit 5, `warnings` traz uma linha por lado (`Key 'id' has repeated values in 'pc_local': 2 row(s) left out of the comparison.`) e `comparisons[0].duplicate_rows == {"pc_local": 2, "pc_local2": 2}` | functional | all | tests/functional/test_run_group.py::test_a_repeated_join_key_is_reported_not_swallowed |
| QA-GROUP-012 | Dado um grupo com chave unica / Quando executado / Entao o envelope nao traz `warnings` e `duplicate_rows == {}` | functional | all | tests/functional/test_run_group.py::test_a_unique_join_key_warns_about_nothing |
| QA-GROUP-013 | Dado `-f table` e chave repetida / Quando executado / Entao o aviso aparece no stdout junto do veredito | functional | all | tests/functional/test_run_group.py::test_the_warning_reaches_the_table_format_too |
| QA-GROUP-014 | Dado a tela **Comparacao** da TUI e o grupo `pedidos` (divergente) / Quando executado / Entao a barra traz `pedidos`, `2 consultas` e `DIVERGENT`, e o widget carrega a comparacao com `diff_count == 1` | functional | all | tests/ui/test_functional_screens.py::test_group_run_runs_a_group_and_shows_the_verdict |
| QA-GROUP-015 | Dado a mesma tela e um grupo de chave repetida / Quando executado / Entao a tela notifica uma vez por lado, com o mesmo texto do `warnings` do CLI | functional | all | tests/ui/test_functional_screens.py::test_group_run_warns_that_a_repeated_key_left_rows_out |
| QA-GROUP-016 | Dado a mesma tela e um grupo de chave unica / Quando executado / Entao nenhuma notificacao e emitida | functional | all | tests/ui/test_functional_screens.py::test_group_run_says_nothing_when_the_key_is_unique |
| QA-GROUP-017 | Dado um grupo **sem** `--compare-column` (a flag e opcional) cujas consultas divergem / Quando `dbqm run-group sem_colunas -f json` / Entao exit 5 e a comparacao de `valor` com `diff_count 1` — respondia exit 0 `all_match: true` com `comparisons: []` | functional | all | tests/functional/test_run_group.py::test_a_group_with_no_compare_columns_still_compares |
| QA-GROUP-018 | Dado o mesmo grupo / Quando executado / Entao o primeiro `warnings` e `Group "sem_colunas" does not define columns to compare; comparando as comuns: valor.` | functional | all | tests/functional/test_run_group.py::test_deriving_the_columns_is_said_out_loud |
| QA-GROUP-019 | Dado um grupo sem colunas cujas consultas so tem a chave em comum / Quando executado / Entao exit 2, `validation`, `Group "so_id" does not define columns to compare, and the queries have no column in common other than "id".` | functional | all | tests/functional/test_run_group.py::test_nothing_common_beyond_the_key_is_refused |
| QA-GROUP-020 | Dado `group add --query q --query q` / Quando executado / Entao exit 2, `validation`, `Query "ped_local" is repeated. A group compares distinct queries.` — o indice e por nome, entao a consulta se compararia consigo mesma | functional | all | tests/functional/test_run_group.py::test_a_group_cannot_name_the_same_query_twice |
| QA-GROUP-010 | Dado um grupo cuja consulta le uma tabela inexistente / Quando `dbqm run-group quebrado -f json` / Entao exit 4, `sql_error`, mensagem `Error in query "quebrada": no such table: nao_existe` | functional | all | tests/functional/test_run_group.py::test_a_failing_query_names_itself |
