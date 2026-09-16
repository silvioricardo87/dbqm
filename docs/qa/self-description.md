# QA — self-description (`DESC`)

`dbqm describe-cli [-f table|json]`

The CLI describes itself from its own parser: every command in
`COMMAND_MAP`, its help, its arguments (flags, required, choices, help),
and — for `connection`, `query`, `group`, `template`, `config`,
`oracle-client` — the subcommands, described the same way. It is what an
agent reads instead of `--help` prose. Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-DESC-001 | Dado o parser / Quando `dbqm describe-cli -f json` / Entao exit 0 e o conjunto de `data.commands[].name` e exatamente as chaves de `dbqm.cli.COMMAND_MAP` | functional | all | tests/functional/test_describe_cli.py::test_every_dispatched_command_is_described |
| QA-DESC-002 | Dado os grupos `connection`, `query`, `group`, `template` / Quando descritos / Entao cada um traz `subcommands` com `add`, `update`, `show`, `rm`, `list`, e cada subcomando tem `arguments` | functional | all | tests/functional/test_describe_cli.py::test_the_four_curation_groups_list_their_subcommands_with_arguments |
| QA-DESC-003 | Dado `run` / Quando descrito / Entao `arguments` tem `query` (`required == true`), `-c/--connection`, `-p/--param`, `-f/--format` com `choices == ["table","json","csv","raw"]`, `-e/--export` com `choices == ["csv","json","txt","html"]` | functional | all | tests/functional/test_describe_cli.py::test_an_argument_carries_flags_required_and_choices |
| QA-DESC-004 | Dado um comando folha / Quando descrito / Entao nao tem a chave `subcommands` — "este nome recebe argumentos", nao "este nome recebe um verbo" | functional | all | tests/functional/test_describe_cli.py::test_a_leaf_has_no_subcommands_key |
| QA-DESC-005 | Dado `-f table` / Quando `dbqm describe-cli` / Entao exit 0 e cada nome de comando aparece no stdout | functional | all | tests/functional/test_describe_cli.py::test_table_format_names_every_command |
| QA-DESC-006 | Dado `sql` / Quando descrito / Entao `arguments` expoe `--commit`, `--force-write` e `--explain` — as flags que um agente precisa conhecer antes de escrever | functional | all | tests/functional/test_describe_cli.py::test_sql_exposes_its_guard_flags |
