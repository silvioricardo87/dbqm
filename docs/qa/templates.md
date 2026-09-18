# QA — templates (`TPL`)

`dbqm template add <nome> --content <texto>|--content-file <arquivo> [--description ...]`,
then `update`, `show`, `rm`, `list`.

A template is a named piece of SQL text with `{{campo}}` placeholders; the
TUI fills the fields when a group is built from one. The CLI half is pure
curation — no database is touched — so every row here is engine `all` and
runs with nothing but a config directory. Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-TPL-001 | Dado nenhum template / Quando `dbqm template add t1 --content "SELECT * FROM {{tabela}}" --description td -f json` e depois `template show t1 -f json` / Entao `data == {"name":"t1","created":true}` e o show traz `content == "SELECT * FROM {{tabela}}"`, `description == "td"` | functional | all | tests/functional/test_template.py::test_add_then_show |
| QA-TPL-002 | Dado `t1` / Quando `template add t1 --content x -f json` / Entao exit 2, `validation`, `Template "t1" already exists.` e o `content` original continua | functional | all | tests/functional/test_template.py::test_add_refuses_a_duplicate_and_keeps_the_original |
| QA-TPL-003 | Dado um arquivo com o conteudo / Quando `template add t2 --content-file <arquivo> -f json` / Entao `show t2` traz exatamente o texto do arquivo | functional | all | tests/functional/test_template.py::test_content_file_is_read |
| QA-TPL-004 | Dado `t1` com descricao `td` / Quando `template update t1 --description nova -f json` e depois `show` / Entao `updated == true`, `description == "nova"` e `content` intacto | functional | all | tests/functional/test_template.py::test_update_changes_only_what_it_is_given |
| QA-TPL-005 | Dado um nome nao registrado / Quando `template update nope --description x -f json` / Entao exit 2, `not_found` | functional | all | tests/functional/test_template.py::test_update_of_an_unknown_name_is_not_found |
| QA-TPL-006 | Dado `t1` / Quando `template list -f json` / Entao `[{"name":"t1","description":"td"}]` | functional | all | tests/functional/test_template.py::test_list_shows_name_and_description |
| QA-TPL-007 | Dado stdin que nao e terminal / Quando `template rm t1 -f json` sem `--yes` / Entao exit 2, `usage`, `Use --yes to remove without confirming.` e `t1` continua | functional | all | tests/functional/test_template.py::test_rm_without_yes_off_a_tty_is_refused |
| QA-TPL-008 | Dado `t1` / Quando `template rm t1 --yes -f json` / Entao `removed == true` e `show t1` e `not_found` | functional | all | tests/functional/test_template.py::test_rm_with_yes_removes_it |
