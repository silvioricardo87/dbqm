# QA — groups and `run-group` (`GROUP`)

`dbqm group add <name> --query <q1> --query <q2> --join-key <col> [--compare-column <col>]...`
then `dbqm run-group <name> [-p k=v] [-f table|json] [-e csv|json|txt|html] [--flat]`.

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
the same schema and data except order 13 (`valor` 5.25 vs 6.0). The queries
`ped_*` read `pedidos` (diverge), `cli_*` read `clientes` (agree). Envelope
and exit codes: [output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-GROUP-001 | Given `cli_local` and `cli_local2` saved / When `dbqm group add clientes --query cli_local --query cli_local2 --join-key id --compare-column nome -f json` then `dbqm run-group clientes -f json` / Then the first returns `data == {"name":"clientes","created":true}` and the second exit 0, `data.all_match == true`, one `nome` comparison with `total_keys 3`, `equal_count 3`, `diff_count 0` | functional | all | tests/functional/test_run_group.py::test_group_add_then_run_group_that_agrees |
| QA-GROUP-002 | Given the `pedidos` group over `ped_local`/`ped_local2` / When `dbqm run-group pedidos -f json` / Then **exit 5**, `ok == true` on stdout, `data.all_match == false`, the `valor` comparison with `total_keys 4`, `equal_count 3`, `diff_count 1` | functional | all | tests/functional/test_run_group.py::test_a_real_divergence_exits_5 |
| QA-GROUP-003 | Given the `pedidos` group / When `dbqm run-group pedidos` (table) / Then exit 5 and `DIVERGENT` on stdout; for `clientes`, exit 0 and `CONSISTENT` | functional | all | tests/functional/test_run_group.py::test_table_format_prints_the_verdict_with_the_same_exit |
| QA-GROUP-004 | Given the `pedidos` group / When `dbqm run-group pedidos -e html -f json` / Then the `.html` is written (it exists, it carries `<table`), `data.format == "html"` **and the exit is still 5** | functional | all | tests/functional/test_run_group.py::test_export_html_still_exits_5_after_writing |
| QA-GROUP-005 | Given `--flat -e html` / When `dbqm run-group pedidos --flat -e html -f json` / Then exit 2, `usage`, the message `--flat has no HTML version. ...` and nothing ran: the history gains no entry | functional | all | tests/functional/test_run_group.py::test_flat_with_html_is_refused_before_anything_runs |
| QA-GROUP-006 | Given `--flat -e csv` / When `dbqm run-group pedidos --flat -e csv -f json` / Then the `flat_*.csv` file exists and the exit is 5 | functional | all | tests/functional/test_run_group.py::test_flat_csv_writes_and_keeps_the_verdict |
| QA-GROUP-007 | Given a group that does not exist / When `dbqm run-group nope -f json` / Then exit 2, `not_found`, `Group "nope" not found.` | functional | all | tests/functional/test_run_group.py::test_an_unknown_group_is_not_found |
| QA-GROUP-008 | Given `group add` with a single query / When `dbqm group add um --query cli_local --join-key id -f json` / Then exit 2, `validation`, `Select at least 2 queries.` | functional | all | tests/functional/test_run_group.py::test_a_group_needs_two_queries |
| QA-GROUP-009 | Given a divergent run / When `dbqm history -f json` / Then there is an entry with `entry_type == "group"`, `name == "pedidos"`, `all_match == false` — a divergence is a completed run, not an aborted one | functional | all | tests/functional/test_run_group.py::test_a_divergent_run_is_still_recorded_in_history |
| QA-GROUP-011 | Given a group whose `id` key comes from `cliente_id` (four orders, two customers) / When `dbqm run-group por_cliente -f json` / Then exit 5, `warnings` carries one line per side (`Key 'id' has repeated values in 'pc_local': 2 row(s) left out of the comparison.`) and `comparisons[0].duplicate_rows == {"pc_local": 2, "pc_local2": 2}` | functional | all | tests/functional/test_run_group.py::test_a_repeated_join_key_is_reported_not_swallowed |
| QA-GROUP-012 | Given a group with a unique key / When run / Then the envelope carries no `warnings` and `duplicate_rows == {}` | functional | all | tests/functional/test_run_group.py::test_a_unique_join_key_warns_about_nothing |
| QA-GROUP-013 | Given `-f table` and a repeated key / When run / Then the warning appears on stdout beside the verdict | functional | all | tests/functional/test_run_group.py::test_the_warning_reaches_the_table_format_too |
| QA-GROUP-014 | Given the TUI's **Comparison** screen and the `pedidos` group (divergent) / When run / Then the bar carries `pedidos`, `2 queries` and `DIVERGENT`, and the widget loads the comparison with `diff_count == 1` | functional | all | tests/ui/test_functional_screens.py::test_group_run_runs_a_group_and_shows_the_verdict |
| QA-GROUP-015 | Given the same screen and a group with a repeated key / When run / Then the screen notifies once per side, with the same text as the CLI's `warnings` | functional | all | tests/ui/test_functional_screens.py::test_group_run_warns_that_a_repeated_key_left_rows_out |
| QA-GROUP-016 | Given the same screen and a group with a unique key / When run / Then no notification is emitted | functional | all | tests/ui/test_functional_screens.py::test_group_run_says_nothing_when_the_key_is_unique |
| QA-GROUP-017 | Given a group **without** `--compare-column` (the flag is optional) whose queries diverge / When `dbqm run-group sem_colunas -f json` / Then exit 5 and the `valor` comparison with `diff_count 1` — it used to answer exit 0 `all_match: true` with `comparisons: []` | functional | all | tests/functional/test_run_group.py::test_a_group_with_no_compare_columns_still_compares |
| QA-GROUP-018 | Given the same group / When run / Then the first `warnings` entry is `Group "sem_colunas" does not define columns to compare; comparing the common ones: valor.` | functional | all | tests/functional/test_run_group.py::test_deriving_the_columns_is_said_out_loud |
| QA-GROUP-019 | Given a group with no columns whose queries share only the key / When run / Then exit 2, `validation`, `Group "so_id" does not define columns to compare, and the queries have no column in common other than "id".` | functional | all | tests/functional/test_run_group.py::test_nothing_common_beyond_the_key_is_refused |
| QA-GROUP-020 | Given `group add --query q --query q` / When run / Then exit 2, `validation`, `Query "ped_local" is repeated. A group compares distinct queries.` — the index is keyed by name, so the query would be compared against itself | functional | all | tests/functional/test_run_group.py::test_a_group_cannot_name_the_same_query_twice |
| QA-GROUP-010 | Given a group whose query reads a missing table / When `dbqm run-group quebrado -f json` / Then exit 4, `sql_error`, the message `Error in query "quebrada": no such table: nao_existe` | functional | all | tests/functional/test_run_group.py::test_a_failing_query_names_itself |
