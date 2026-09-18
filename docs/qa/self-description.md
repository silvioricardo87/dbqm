# QA — self-description (`DESC`)

`dbqm describe-cli [-f table|json]`

The CLI describes itself from its own parser: every command in
`COMMAND_MAP`, its help, its arguments (flags, required, choices, help),
and — for `connection`, `query`, `group`, `template`, `config`,
`oracle-client` — the subcommands, described the same way. It is what an
agent reads instead of `--help` prose. Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-DESC-001 | Given the parser / When `dbqm describe-cli -f json` / Then exit 0 and the set of `data.commands[].name` is exactly the keys of `dbqm.cli.COMMAND_MAP` | functional | all | tests/functional/test_describe_cli.py::test_every_dispatched_command_is_described |
| QA-DESC-002 | Given the groups `connection`, `query`, `group`, `template` / When described / Then each carries `subcommands` with `add`, `update`, `show`, `rm`, `list`, and every subcommand has `arguments` | functional | all | tests/functional/test_describe_cli.py::test_the_four_curation_groups_list_their_subcommands_with_arguments |
| QA-DESC-003 | Given `run` / When described / Then `arguments` has `query` (`required == true`), `-c/--connection`, `-p/--param`, `-f/--format` with `choices == ["table","json","csv","raw"]`, `-e/--export` with `choices == ["csv","json","txt","html"]` | functional | all | tests/functional/test_describe_cli.py::test_an_argument_carries_flags_required_and_choices |
| QA-DESC-004 | Given a leaf command / When described / Then it has no `subcommands` key — "this name takes arguments", not "this name takes a verb" | functional | all | tests/functional/test_describe_cli.py::test_a_leaf_has_no_subcommands_key |
| QA-DESC-005 | Given `-f table` / When `dbqm describe-cli` / Then exit 0 and every command name appears on stdout | functional | all | tests/functional/test_describe_cli.py::test_table_format_names_every_command |
| QA-DESC-006 | Given `sql` / When described / Then `arguments` exposes `--commit`, `--force-write` and `--explain` — the flags an agent has to know about before writing | functional | all | tests/functional/test_describe_cli.py::test_sql_exposes_its_guard_flags |
