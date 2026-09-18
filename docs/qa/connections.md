# QA — curation: connections, queries and groups (`CONN`)

`dbqm connection|query|group add|update|show|rm|list ...`

The three curated things share one shape: `add` creates and refuses a
duplicate, `update` changes only what it is given, `show -f json` returns
the record, `rm` needs `--yes` when stdin is not a terminal, `list` returns
the summaries. Templates have their own document ([templates.md](templates.md));
what `run`/`run-group` do with a query or group once it exists is in
[saved-queries.md](saved-queries.md) and [groups.md](groups.md).

Every `add` here is a SQLite connection (`--type sqlite --database <arquivo>
--no-password`); the networked engines' field rules are unit-tested in
`tests/core/test_connection_builder.py`. Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-CONN-001 | Dado um arquivo SQLite / Quando `dbqm connection add local --type sqlite --database <arquivo> --no-password --description seed -f json` / Entao exit 0, `command == "connection.add"`, `data == {"name":"local","created":true}` e `dbqm test local -f json` responde | functional | all | tests/functional/test_connection.py::test_add_creates_a_connection_that_answers |
| QA-CONN-002 | Dado `local` ja registrada / Quando `add local ...` de novo / Entao exit 2, `validation`, `Conexao "local" ja existe.` — o mesmo token que query/group/template | functional | all | tests/functional/test_connection.py::test_add_refuses_a_duplicate |
| QA-CONN-003 | Dado `--type sqlite` sem `--database` / Quando `add` / Entao exit 2, `validation`, `Give the SQLite database file (or :memory:).` | functional | all | tests/functional/test_connection.py::test_sqlite_needs_a_database |
| QA-CONN-004 | Dado `--type sqlite --host x` / Quando `add` / Entao exit 2, `validation`, `SQLite does not use host; leave it blank.` | functional | all | tests/functional/test_connection.py::test_sqlite_refuses_a_host |
| QA-CONN-005 | Dado `local` com `description == "seed"` / Quando `dbqm connection update local --read-only -f json` e depois `show local -f json` / Entao `updated == true`, `read_only` virou `true` e `description`, `db_type`, `database` sao os mesmos de antes | functional | all | tests/functional/test_connection.py::test_update_changes_only_what_it_is_given |
| QA-CONN-006 | Dado um nome nao registrado / Quando `update nope --read-only -f json` / Entao exit 2, `not_found`, `Conexao "nope" nao encontrada.` | functional | all | tests/functional/test_connection.py::test_update_of_an_unknown_name_is_not_found |
| QA-CONN-007 | Dado `local` / Quando `dbqm connection show local -f json` / Entao `data.name == "local"`, `data.db_type == "sqlite"`, `data.database` e o caminho e `data.read_only == false` | functional | all | tests/functional/test_connection.py::test_show_returns_the_record |
| QA-CONN-008 | Dado `local` / Quando `dbqm connection list -f json` / Entao a lista tem um item `{"name":"local","db_type":"sqlite","target":<arquivo>,"read_only":false}` — o target de um SQLite e o arquivo | functional | all | tests/functional/test_connection.py::test_list_shows_the_file_as_the_target |
| QA-CONN-009 | Dado stdin que nao e terminal / Quando `dbqm connection rm local -f json` sem `--yes` / Entao exit 2, `usage`, `Use --yes para remover sem confirmacao.` e `show local` ainda responde | functional | all | tests/functional/test_connection.py::test_rm_without_yes_off_a_tty_is_refused_and_keeps_it |
| QA-CONN-010 | Dado `local` / Quando `dbqm connection rm local --yes -f json` / Entao `data == {"name":"local","removed":true}` e `show local` e `not_found` | functional | all | tests/functional/test_connection.py::test_rm_with_yes_removes_it |
| QA-CONN-011 | Dado `local` / Quando `dbqm query add q1 --connection local --sql "SELECT 1" --description d --folder f -f json` e depois `query show q1 -f json` / Entao `created == true` e o show traz `connection`, `sql`, `description == "d"`, `folder == "f"`, `is_favorite == false` | functional | all | tests/functional/test_connection.py::test_query_add_then_show |
| QA-CONN-012 | Dado `q1` / Quando `query add q1 ...` de novo / Entao exit 2, `validation`, `Consulta "q1" ja existe.` | functional | all | tests/functional/test_connection.py::test_query_add_refuses_a_duplicate |
| QA-CONN-013 | Dado `query add` sem `--connection` / Quando executado / Entao exit 2, `validation`, `Selecione uma conexao.`; com `--connection nope`, `Conexao "nope" nao encontrada.` | functional | all | tests/functional/test_connection.py::test_query_add_needs_a_registered_connection |
| QA-CONN-014 | Dado `q1` com descricao e pasta / Quando `query update q1 --favorite -f json` e depois `show` / Entao `is_favorite == true` e `description`, `folder`, `sql`, `connection` intactos | functional | all | tests/functional/test_connection.py::test_query_update_changes_only_what_it_is_given |
| QA-CONN-015 | Dado `q1` na conexao `local` / Quando `query list -f json` e `query list --connection nope -f json` / Entao a primeira traz `q1` com `connection`, `folder`, `description`, `params`; a segunda e `[]` | functional | all | tests/functional/test_connection.py::test_query_list_filters_by_connection |
| QA-CONN-016 | Dado `q1` / Quando `query rm q1 -f json` sem `--yes` e depois com `--yes` / Entao a primeira e `usage` e `q1` continua; a segunda `removed == true` e `show q1` e `not_found` `Consulta "q1" nao encontrada.` | functional | all | tests/functional/test_connection.py::test_query_rm_needs_yes_off_a_tty |
| QA-CONN-017 | Dado `qa` e `qb` salvas / Quando `group add g1 --query qa --query qb --join-key id --description gd -f json` e depois `group show g1 -f json` / Entao `created == true` e o show traz `queries == ["qa","qb"]`, `join_key == "id"`, `description == "gd"` | functional | all | tests/functional/test_connection.py::test_group_add_then_show |
| QA-CONN-018 | Dado `g1` / Quando `group add g1 ...` de novo / Entao exit 2, `validation`, `Grupo "g1" ja existe.` | functional | all | tests/functional/test_connection.py::test_group_add_refuses_a_duplicate |
| QA-CONN-019 | Dado `g1` com descricao / Quando `group update g1 --folder pasta -f json` e depois `show` / Entao `folder == "pasta"` e `description`, `queries`, `join_key` intactos | functional | all | tests/functional/test_connection.py::test_group_update_changes_only_what_it_is_given |
| QA-CONN-020 | Dado `g1` / Quando `group list -f json` / Entao um item com `name`, `description`, `folder`, `queries`, `join_key` | functional | all | tests/functional/test_connection.py::test_group_list_shows_the_summary |
| QA-CONN-021 | Dado `g1` / Quando `group rm g1 -f json` sem `--yes` e depois com `--yes` / Entao a primeira e `usage` e `g1` continua; a segunda `removed == true` e `show g1` e `not_found` | functional | all | tests/functional/test_connection.py::test_group_rm_needs_yes_off_a_tty |
