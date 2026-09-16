# QA — config portability (`PORT`)

`dbqm export-config --password <senha>|--password-stdin [--no-connections] [--no-queries] [--no-groups]`
then `dbqm import-config <arquivo.dbqm> --password <senha>|--password-stdin`.

The bundle is a JSON file under `exports/configs/`; connection passwords
inside it are encrypted with the bundle password, everything else is
plain. Import adds what is not there yet and **skips by name** what is,
counting each. Envelope and exit codes: [output-contract.md](output-contract.md).

The tests pass `--password` on the command line because there is no shell
history to leak into; a person should use `--password-stdin`.

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-PORT-001 | Dado `local`, uma consulta, um grupo e um template / Quando `dbqm export-config --password s3gredo -f json` / Entao exit 0 e `data.path` e um `.dbqm` existente sob a pasta de exports | functional | all | tests/functional/test_portability.py::test_export_writes_a_bundle |
| QA-PORT-002 | Dado o bundle e um config **vazio** (arquivos de conexoes, consultas, grupos e templates removidos) / Quando `dbqm import-config <bundle> --password s3gredo -f json` / Entao `data == {"connections":1,"queries":2,"groups":1,"templates":1,"skipped":0}` e `connection show local`, `query show qa`, `query show qb`, `group show g1`, `template show t1` respondem, cada um pelo nome | functional | all | tests/functional/test_portability.py::test_import_into_an_empty_config_round_trips_every_kind_by_name |
| QA-PORT-003 | Dado a conexao importada / Quando `dbqm test local -f json` / Entao responde — o caminho do arquivo sobreviveu a viagem | functional | all | tests/functional/test_portability.py::test_an_imported_connection_still_answers |
| QA-PORT-004 | Dado tudo ja presente / Quando `import-config <bundle>` de novo / Entao exit 0 e `skipped == 5`, nada duplicado nas listas | functional | all | tests/functional/test_portability.py::test_import_over_an_existing_config_skips_by_name |
| QA-PORT-005 | Dado a senha errada e um config vazio / Quando `import-config <bundle> --password errada -f json` / Entao exit 2, `validation`, mensagem comecando por `Erro ao importar:` e nenhuma conexao foi criada | functional | all | tests/functional/test_portability.py::test_a_wrong_password_imports_nothing |
| QA-PORT-006 | Dado um caminho que nao existe / Quando `import-config nao.dbqm --password x -f json` / Entao exit 2, `not_found`, `Arquivo 'nao.dbqm' nao encontrado.` | functional | all | tests/functional/test_portability.py::test_a_missing_bundle_is_not_found |
| QA-PORT-007 | Dado `--no-connections` / Quando `export-config --no-connections --password s3gredo` e importado num config vazio / Entao `connections == 0` e o resto importa | functional | all | tests/functional/test_portability.py::test_no_connections_leaves_them_out |
