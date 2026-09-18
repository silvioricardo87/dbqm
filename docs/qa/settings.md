# QA — settings (`CFG`)

`dbqm config list|get <chave>|set <chave> <valor> [-f table|json]`

The keys are the fields of `dbqm.models.settings.Settings`; `set` parses
the value by the field's type (a bool takes `true/false`, `1/0`, `sim/nao`)
and refuses what does not fit, leaving the stored value alone. An unknown
key is `not_found` and the message lists the valid ones. Envelope and exit
codes: [output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-CFG-001 | Dado um config novo / Quando `dbqm config list -f json` / Entao `data` tem exatamente as chaves de `Settings` com os valores padrao (`audit_log_enabled == false`, `theme == "plano-escuro"`, `create_export_subdirs == true`) | functional | all | tests/functional/test_config.py::test_list_returns_every_key_with_its_default |
| QA-CFG-002 | Dado `audit_log_enabled` / Quando `dbqm config set audit_log_enabled true -f json` e depois `config get audit_log_enabled -f json` / Entao o set devolve `value == true` (booleano JSON, nao a string) e o get le `true` de volta | functional | all | tests/functional/test_config.py::test_set_a_bool_then_get_returns_a_real_bool |
| QA-CFG-003 | Dado `audit_log_enabled == true` / Quando `config set audit_log_enabled talvez -f json` / Entao exit 2, `validation`, `Invalid value for "audit_log_enabled": "talvez". Use true/false, 1/0 or yes/no.` e o get continua `true` | functional | all | tests/functional/test_config.py::test_a_bad_value_is_refused_and_the_old_one_stays |
| QA-CFG-004 | Dado uma chave que nao existe / Quando `config set nao_existe 1 -f json` / Entao exit 2, `not_found`, mensagem comecando por `Key "nao_existe" does not exist. Valid keys:` e listando todas as chaves de `Settings` | functional | all | tests/functional/test_config.py::test_an_unknown_key_names_the_valid_ones |
| QA-CFG-005 | Dado `theme` / Quando `config set theme inexistente -f json` / Entao exit 2, `validation`, `Theme "inexistente" does not exist. Valid themes: plano-claro, plano-escuro.` | functional | all | tests/functional/test_config.py::test_a_theme_that_does_not_exist_is_refused |
| QA-CFG-006 | Dado `config get nao_existe -f json` / Quando executado / Entao exit 2, `not_found` — o mesmo token do set | functional | all | tests/functional/test_config.py::test_get_of_an_unknown_key_is_not_found |
| QA-CFG-007 | Dado `theme == "plano-escuro"` / Quando `config set theme plano-claro -f json` e depois `config list -f json` / Entao `theme == "plano-claro"` e nenhuma outra chave mudou | functional | all | tests/functional/test_config.py::test_set_a_string_changes_only_that_key |
