# QA — history (`HIST`)

`dbqm history [-n N] [-f table|json] [--clear]`

Every `run` and `run-group` writes one entry — success, failure or
divergence alike, since a divergence is a completed run. `history` lists
the newest first; `-n` caps the count; `--clear` empties it. The rows that
prove an entry *gets written* live with the command that writes it
(QA-QUERY-010, QA-GROUP-009); this document is about reading it back.
Envelope and exit codes: [output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-HIST-001 | Given no execution / When `dbqm history -f json` / Then exit 0 and `data == []` | functional | all | tests/functional/test_history.py::test_an_empty_history_is_an_empty_list |
| QA-HIST-002 | Given two runs of `run ativos` / When `dbqm history -f json` / Then two entries with `entry_type == "query"`, `name == "ativos"`, `connection == "local"`, `success == true`, `row_count == 2`, each carrying an `id` and a `timestamp` | functional | all | tests/functional/test_history.py::test_each_run_is_one_entry_with_its_facts |
| QA-HIST-003 | Given a run that failed (`run quebrada`, missing table) / When `dbqm history -f json` / Then the entry carries `success == false` and `error == "no such table: nao_existe"` | functional | all | tests/functional/test_history.py::test_a_failed_run_is_recorded_with_its_error |
| QA-HIST-004 | Given three runs / When `dbqm history -n 2 -f json` / Then exactly two entries, the two most recent | functional | all | tests/functional/test_history.py::test_n_caps_the_count_newest_first |
| QA-HIST-005 | Given recorded runs / When `dbqm history --clear -f json` then `history -f json` / Then both answer `data == []` | functional | all | tests/functional/test_history.py::test_clear_empties_it |
| QA-HIST-007 | Given `-n 0` or `-n -5` / When `dbqm history -n 0 -f json` / Then exit 2, `usage`, `-n must be greater than zero.` — `-n 0` used to mean 20 (the default) and `-n -5` used to mean "all but the last five" | functional | all | tests/functional/test_history.py::test_a_limit_below_one_is_refused |
| QA-HIST-008 | Given two runs and `-n 1` / When run / Then exactly one entry | functional | all | tests/functional/test_history.py::test_a_limit_of_one_returns_one |
| QA-HIST-006 | Given one run / When `dbqm history` (table) / Then exit 0 and the name `ativos` appears on stdout | functional | all | tests/functional/test_history.py::test_table_format_prints_the_entries |
