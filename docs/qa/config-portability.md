# QA — config portability (`PORT`)

`dbqm export-config --password <password>|--password-stdin [--no-connections] [--no-queries] [--no-groups]`
then `dbqm import-config <file.dbqm> --password <password>|--password-stdin`.

The bundle is a JSON file under `exports/configs/`; connection passwords
inside it are encrypted with the bundle password, everything else is
plain. Import adds what is not there yet and **skips by name** what is,
counting each. Envelope and exit codes: [output-contract.md](output-contract.md).

The tests pass `--password` on the command line because there is no shell
history to leak into; a person should use `--password-stdin`.

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-PORT-001 | Given `local`, a query, a group and a template / When `dbqm export-config --password s3gredo -f json` / Then exit 0 and `data.path` is an existing `.dbqm` under the export folder | functional | all | tests/functional/test_portability.py::test_export_writes_a_bundle |
| QA-PORT-002 | Given the bundle and an **empty** config (the connection, query, group and template files removed) / When `dbqm import-config <bundle> --password s3gredo -f json` / Then `data == {"connections":1,"queries":2,"groups":1,"templates":1,"skipped":0}` and `connection show local`, `query show qa`, `query show qb`, `group show g1`, `template show t1` all answer, each by its name | functional | all | tests/functional/test_portability.py::test_import_into_an_empty_config_round_trips_every_kind_by_name |
| QA-PORT-003 | Given the imported connection / When `dbqm test local -f json` / Then it answers — the file path survived the trip | functional | all | tests/functional/test_portability.py::test_an_imported_connection_still_answers |
| QA-PORT-004 | Given everything already present / When `import-config <bundle>` runs again / Then exit 0 and `skipped == 5`, with nothing duplicated in the listings | functional | all | tests/functional/test_portability.py::test_import_over_an_existing_config_skips_by_name |
| QA-PORT-005 | Given the wrong password and an empty config / When `import-config <bundle> --password errada -f json` / Then exit 2, `validation`, a message starting with `Could not import:` and no connection created | functional | all | tests/functional/test_portability.py::test_a_wrong_password_imports_nothing |
| QA-PORT-006 | Given a path that does not exist / When `import-config nao.dbqm --password x -f json` / Then exit 2, `not_found`, `File "nao.dbqm" not found.` | functional | all | tests/functional/test_portability.py::test_a_missing_bundle_is_not_found |
| QA-PORT-008 | Given `--no-connections --no-queries --no-groups` / When `dbqm export-config ... -f json` / Then exit 2, `usage`, `Nothing to export: ...` and no `.dbqm` written — it used to write a bundle carrying nothing but its own salt and call that a successful export | functional | all | tests/functional/test_portability.py::test_excluding_everything_is_refused |
| QA-PORT-007 | Given `--no-connections` / When `export-config --no-connections --password s3gredo` is imported into an empty config / Then `connections == 0` and the rest imports | functional | all | tests/functional/test_portability.py::test_no_connections_leaves_them_out |
