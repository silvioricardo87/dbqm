# QA — curation: connections, queries and groups (`CONN`)

`dbqm connection|query|group add|update|show|rm|list ...`

The three curated things share one shape: `add` creates and refuses a
duplicate, `update` changes only what it is given, `show -f json` returns
the record, `rm` needs `--yes` when stdin is not a terminal, `list` returns
the summaries. Templates have their own document ([templates.md](templates.md));
what `run`/`run-group` do with a query or group once it exists is in
[saved-queries.md](saved-queries.md) and [groups.md](groups.md).

Every `add` here is a SQLite connection (`--type sqlite --database <file>
--no-password`); the networked engines' field rules are unit-tested in
`tests/core/test_connection_builder.py`. Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-CONN-001 | Given a SQLite file / When `dbqm connection add local --type sqlite --database <file> --no-password --description seed -f json` / Then exit 0, `command == "connection.add"`, `data == {"name":"local","created":true}` and `dbqm test local -f json` answers | functional | all | tests/functional/test_connection.py::test_add_creates_a_connection_that_answers |
| QA-CONN-002 | Given `local` already registered / When `add local ...` runs again / Then exit 2, `validation`, `Connection "local" already exists.` — the same token as query/group/template | functional | all | tests/functional/test_connection.py::test_add_refuses_a_duplicate |
| QA-CONN-003 | Given `--type sqlite` without `--database` / When `add` / Then exit 2, `validation`, `Give the SQLite database file (or :memory:).` | functional | all | tests/functional/test_connection.py::test_sqlite_needs_a_database |
| QA-CONN-004 | Given `--type sqlite --host x` / When `add` / Then exit 2, `validation`, `SQLite does not use host; leave it blank.` | functional | all | tests/functional/test_connection.py::test_sqlite_refuses_a_host |
| QA-CONN-005 | Given `local` with `description == "seed"` / When `dbqm connection update local --read-only -f json` then `show local -f json` / Then `updated == true`, `read_only` became `true`, and `description`, `db_type`, `database` are what they were | functional | all | tests/functional/test_connection.py::test_update_changes_only_what_it_is_given |
| QA-CONN-006 | Given a name that is not registered / When `update nope --read-only -f json` / Then exit 2, `not_found`, `Connection "nope" not found.` | functional | all | tests/functional/test_connection.py::test_update_of_an_unknown_name_is_not_found |
| QA-CONN-007 | Given `local` / When `dbqm connection show local -f json` / Then `data.name == "local"`, `data.db_type == "sqlite"`, `data.database` is the path and `data.read_only == false` | functional | all | tests/functional/test_connection.py::test_show_returns_the_record |
| QA-CONN-008 | Given `local` / When `dbqm connection list -f json` / Then the list has one item `{"name":"local","db_type":"sqlite","target":<file>,"read_only":false}` — a SQLite connection's target is its file | functional | all | tests/functional/test_connection.py::test_list_shows_the_file_as_the_target |
| QA-CONN-009 | Given stdin that is not a terminal / When `dbqm connection rm local -f json` without `--yes` / Then exit 2, `usage`, `Use --yes to remove without confirming.` and `show local` still answers | functional | all | tests/functional/test_connection.py::test_rm_without_yes_off_a_tty_is_refused_and_keeps_it |
| QA-CONN-010 | Given `local` / When `dbqm connection rm local --yes -f json` / Then `data == {"name":"local","removed":true}` and `show local` is `not_found` | functional | all | tests/functional/test_connection.py::test_rm_with_yes_removes_it |
| QA-CONN-011 | Given `local` / When `dbqm query add q1 --connection local --sql "SELECT 1" --description d --folder f -f json` then `query show q1 -f json` / Then `created == true` and the show carries `connection`, `sql`, `description == "d"`, `folder == "f"`, `is_favorite == false` | functional | all | tests/functional/test_connection.py::test_query_add_then_show |
| QA-CONN-012 | Given `q1` / When `query add q1 ...` runs again / Then exit 2, `validation`, `Query "q1" already exists.` | functional | all | tests/functional/test_connection.py::test_query_add_refuses_a_duplicate |
| QA-CONN-013 | Given `query add` without `--connection` / When run / Then exit 2, `validation`, `Choose a connection.`; with `--connection nope`, `Connection "nope" not found.` | functional | all | tests/functional/test_connection.py::test_query_add_needs_a_registered_connection |
| QA-CONN-014 | Given `q1` with a description and a folder / When `query update q1 --favorite -f json` then `show` / Then `is_favorite == true` and `description`, `folder`, `sql`, `connection` untouched | functional | all | tests/functional/test_connection.py::test_query_update_changes_only_what_it_is_given |
| QA-CONN-015 | Given `q1` on the `local` connection / When `query list -f json` and `query list --connection nope -f json` / Then the first carries `q1` with `connection`, `folder`, `description`, `params`; the second is `[]` | functional | all | tests/functional/test_connection.py::test_query_list_filters_by_connection |
| QA-CONN-016 | Given `q1` / When `query rm q1 -f json` runs without `--yes`, then with `--yes` / Then the first is `usage` and `q1` survives; the second `removed == true` and `show q1` is `not_found` `Query "q1" not found.` | functional | all | tests/functional/test_connection.py::test_query_rm_needs_yes_off_a_tty |
| QA-CONN-017 | Given `qa` and `qb` saved / When `group add g1 --query qa --query qb --join-key id --description gd -f json` then `group show g1 -f json` / Then `created == true` and the show carries `queries == ["qa","qb"]`, `join_key == "id"`, `description == "gd"` | functional | all | tests/functional/test_connection.py::test_group_add_then_show |
| QA-CONN-018 | Given `g1` / When `group add g1 ...` runs again / Then exit 2, `validation`, `Group "g1" already exists.` | functional | all | tests/functional/test_connection.py::test_group_add_refuses_a_duplicate |
| QA-CONN-019 | Given `g1` with a description / When `group update g1 --folder folder -f json` then `show` / Then `folder == "folder"` and `description`, `queries`, `join_key` untouched | functional | all | tests/functional/test_connection.py::test_group_update_changes_only_what_it_is_given |
| QA-CONN-020 | Given `g1` / When `group list -f json` / Then one item with `name`, `description`, `folder`, `queries`, `join_key` | functional | all | tests/functional/test_connection.py::test_group_list_shows_the_summary |
| QA-CONN-021 | Given `g1` / When `group rm g1 -f json` runs without `--yes`, then with `--yes` / Then the first is `usage` and `g1` survives; the second `removed == true` and `show g1` is `not_found` | functional | all | tests/functional/test_connection.py::test_group_rm_needs_yes_off_a_tty |
