# QA — templates (`TPL`)

`dbqm template add <name> --content <text>|--content-file <file> [--description ...]`,
then `update`, `show`, `rm`, `list`.

A template is a named piece of SQL text with `{{field}}` placeholders; the
TUI fills the fields when a group is built from one. The CLI half is pure
curation — no database is touched — so every row here is engine `all` and
runs with nothing but a config directory. Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-TPL-001 | Given no template / When `dbqm template add t1 --content "SELECT * FROM {{tabela}}" --description td -f json` then `template show t1 -f json` / Then `data == {"name":"t1","created":true}` and the show carries `content == "SELECT * FROM {{tabela}}"`, `description == "td"` | functional | all | tests/functional/test_template.py::test_add_then_show |
| QA-TPL-002 | Given `t1` / When `template add t1 --content x -f json` / Then exit 2, `validation`, `Template "t1" already exists.` and the original `content` survives | functional | all | tests/functional/test_template.py::test_add_refuses_a_duplicate_and_keeps_the_original |
| QA-TPL-003 | Given a file holding the content / When `template add t2 --content-file <file> -f json` / Then `show t2` carries exactly the file's text | functional | all | tests/functional/test_template.py::test_content_file_is_read |
| QA-TPL-004 | Given `t1` with description `td` / When `template update t1 --description nova -f json` then `show` / Then `updated == true`, `description == "nova"` and `content` untouched | functional | all | tests/functional/test_template.py::test_update_changes_only_what_it_is_given |
| QA-TPL-005 | Given a name that is not registered / When `template update nope --description x -f json` / Then exit 2, `not_found` | functional | all | tests/functional/test_template.py::test_update_of_an_unknown_name_is_not_found |
| QA-TPL-006 | Given `t1` / When `template list -f json` / Then `[{"name":"t1","description":"td"}]` | functional | all | tests/functional/test_template.py::test_list_shows_name_and_description |
| QA-TPL-007 | Given stdin that is not a terminal / When `template rm t1 -f json` without `--yes` / Then exit 2, `usage`, `Use --yes to remove without confirming.` and `t1` survives | functional | all | tests/functional/test_template.py::test_rm_without_yes_off_a_tty_is_refused |
| QA-TPL-008 | Given `t1` / When `template rm t1 --yes -f json` / Then `removed == true` and `show t1` is `not_found` | functional | all | tests/functional/test_template.py::test_rm_with_yes_removes_it |
