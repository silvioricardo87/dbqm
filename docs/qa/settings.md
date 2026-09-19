# QA — settings (`CFG`)

`dbqm config list|get <key>|set <key> <value> [-f table|json]`

The keys are the fields of `dbqm.models.settings.Settings`; `set` parses
the value by the field's type (a bool takes `true/false`, `1/0`, `yes/no`)
and refuses what does not fit, leaving the stored value alone. An unknown
key is `not_found` and the message lists the valid ones. Envelope and exit
codes: [output-contract.md](output-contract.md).

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-CFG-001 | Given a fresh config / When `dbqm config list -f json` / Then `data` has exactly the keys of `Settings` with their default values (`audit_log_enabled == false`, `theme == "plano-escuro"`, `create_export_subdirs == true`) | functional | all | tests/functional/test_config.py::test_list_returns_every_key_with_its_default |
| QA-CFG-002 | Given `audit_log_enabled` / When `dbqm config set audit_log_enabled true -f json` then `config get audit_log_enabled -f json` / Then the set returns `value == true` (a JSON boolean, not the string) and the get reads `true` back | functional | all | tests/functional/test_config.py::test_set_a_bool_then_get_returns_a_real_bool |
| QA-CFG-003 | Given `audit_log_enabled == true` / When `config set audit_log_enabled talvez -f json` / Then exit 2, `validation`, `Invalid value for "audit_log_enabled": "talvez". Use true/false, 1/0 or yes/no.` and the get still reads `true` | functional | all | tests/functional/test_config.py::test_a_bad_value_is_refused_and_the_old_one_stays |
| QA-CFG-004 | Given a key that does not exist / When `config set nao_existe 1 -f json` / Then exit 2, `not_found`, a message starting with `Key "nao_existe" does not exist. Valid keys:` and listing every key of `Settings` | functional | all | tests/functional/test_config.py::test_an_unknown_key_names_the_valid_ones |
| QA-CFG-005 | Given `theme` / When `config set theme inexistente -f json` / Then exit 2, `validation`, `Theme "inexistente" does not exist. Valid themes: plano-claro, plano-escuro.` | functional | all | tests/functional/test_config.py::test_a_theme_that_does_not_exist_is_refused |
| QA-CFG-006 | Given `config get nao_existe -f json` / When run / Then exit 2, `not_found` — the same token the set uses | functional | all | tests/functional/test_config.py::test_get_of_an_unknown_key_is_not_found |
| QA-CFG-007 | Given `theme == "plano-escuro"` / When `config set theme plano-claro -f json` then `config list -f json` / Then `theme == "plano-claro"` and no other key changed | functional | all | tests/functional/test_config.py::test_set_a_string_changes_only_that_key |
