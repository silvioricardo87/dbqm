# QA — CLI help, `tui`, and the near-miss command (`HELP`)

`dbqm --help`, `dbqm tui`, and what happens when a name is not quite right.
`self-description.md` covers `dbqm describe-cli`, the machine-readable form
an agent reads instead of this prose; this document covers the prose itself
— the grouped `--help`, the interactive interface as a named command, and
the bare invocation and the unknown-command message that sit beside it.
Envelope and exit codes: [output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-HELP-001 | Given the 23 commands in `COMMAND_MAP` / When `COMMAND_GROUPS` is built / Then every command is in exactly one group and none is lost | unit | all | tests/cli/test_help_shape.py::test_every_command_is_in_exactly_one_group |
| QA-HELP-002 | Given `dbqm --help` at 80 columns / When the usage line prints / Then it does not spell out all 23 commands, carrying `<command>` instead | unit | all | tests/cli/test_help_shape.py::test_the_usage_line_does_not_list_every_command |
| QA-HELP-003 | Given `dbqm --help` / When the epilog prints / Then every group title appears and every command in it is listed under that title | unit | all | tests/cli/test_help_shape.py::test_the_epilog_lists_every_command_under_its_group_title |
| QA-HELP-004 | Given `dbqm --help` / Then `run` and `tui` are each listed with their own catalogue help string | unit | all | tests/cli/test_help_shape.py::test_a_command_is_listed_with_its_own_help_string |
| QA-HELP-005 | Given `dbqm --help` / Then it carries the examples, the exit-code table and where to learn more | unit | all | tests/cli/test_help_shape.py::test_the_help_carries_examples_exit_codes_and_where_to_learn_more |
| QA-HELP-006 | Given `dbqm --help` / Then `-V`/`--version` is documented, even though it is answered in `main.py` before argparse runs | unit | all | tests/cli/test_help_shape.py::test_the_version_flag_is_documented |
| QA-HELP-007 | Given `dbqm --help` at the reference width of 120 columns, in either language / Then no line is wider than 120 characters | unit | all | tests/cli/test_help_shape.py::test_no_line_is_wider_than_the_reference_width |
| QA-HELP-020 | Given `dbqm --help` at the reference width / Then every command's summary appears whole, none cut by the shortening budget | unit | all | tests/cli/test_help_shape.py::test_no_command_summary_is_truncated |
| QA-HELP-008 | Given every example in `EXAMPLES` / Then each starts with `dbqm` and names a real command from `COMMAND_MAP` | unit | all | tests/cli/test_help_shape.py::test_every_example_starts_with_dbqm_and_names_a_real_command |
| QA-HELP-009 | Given `COMMAND_MAP` / Then `tui` is a dispatched command, the same as any other | unit | all | tests/cli/test_tui_command.py::test_tui_is_a_dispatched_command |
| QA-HELP-010 | Given stdin is not a terminal / When `dbqm tui` runs / Then exit 2, stdout empty, `-f json`'s `error.code == "usage"`, and the app never opens | unit | all | tests/cli/test_tui_command.py::test_it_refuses_a_non_terminal_stdin_instead_of_opening |
| QA-HELP-011 | Given stdin is a terminal / When `dbqm tui` runs / Then `DBQMApp().run()` is reached | unit | all | tests/cli/test_tui_command.py::test_it_opens_the_app_on_a_terminal |
| QA-HELP-012 | Given a bare `dbqm` / When it runs with no arguments / Then the help prints on stdout with nothing on stderr, carries the notice on where the interface went, and lists the grouped help (`run-group`, `describe-cli`) | unit | all | tests/cli/test_tui_command.py::test_the_bare_invocation_prints_the_help |
| QA-HELP-019 | Given `dbqm` (main entry point) / When it runs with no arguments / Then the help prints, `DBQMApp.run` is never called, and exit is 0 | unit | all | tests/test_cli.py::TestMainEntryPoint::test_main_no_args_prints_the_help_and_never_opens_the_tui |
| QA-HELP-020 | Given `dbqm --help` / Then the notice on where the interactive interface went appears above the grouped command list | unit | all | tests/cli/test_help_shape.py::test_the_help_says_where_the_interface_went |
| QA-HELP-013 | Given `dbqm ru` / When dispatched / Then exit 2, stdout empty, and stderr names `run` as the one it probably meant | unit | all | tests/cli/test_unknown_command.py::test_a_near_miss_names_the_command |
| QA-HELP-014 | Given `dbqm run-grou` / When dispatched / Then exit 2 and `run-group` is named | unit | all | tests/cli/test_unknown_command.py::test_a_near_miss_of_a_hyphenated_command |
| QA-HELP-015 | Given `dbqm zzzzzz`, a name nothing is close to / When dispatched / Then exit 2 and argparse's own `invalid choice` list is what prints, not a wrong guess | unit | all | tests/cli/test_unknown_command.py::test_nothing_close_falls_through_to_argparse |
| QA-HELP-016 | Given a real command (`dbqm list connections -f json`) / Then the near-miss check never fires and exit is 0 | unit | all | tests/cli/test_unknown_command.py::test_a_real_command_is_untouched |
| QA-HELP-017 | Given a subcommand of a group (`dbqm connection list -f json`) / Then `argv[0]` is already in `COMMAND_MAP`, the check returns early, and exit is 0 | unit | all | tests/cli/test_unknown_command.py::test_a_subcommand_of_a_group_is_untouched |
| QA-HELP-018 | Given `dbqm --help` (a flag, not a name) / Then the near-miss check never mistakes it for a command and exit is 0 with the help on stdout | unit | all | tests/cli/test_unknown_command.py::test_a_flag_is_not_mistaken_for_a_command |
