# QA — the Oracle Instant Client installer (`OCLI`)

`dbqm oracle-client available|list|install <versao>|rm <nome> [--yes] [-f table|json]`

Downloads an Oracle Instant Client for the host platform from Oracle's
CDN into dbqm's clients directory, lists what is installed, removes one.
`install` is a **real download** of tens of megabytes; the row says so.
Under `-f json` the download progress goes to stderr so stdout stays the
envelope. Everything but the network and the archive is unit-tested with
mocks in `tests/test_cli.py::TestCmdOracleClient` and
`tests/core/test_oracle_client_installer.py`; each row names its unit test.

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-OCLI-001 | Dado esta maquina / Quando `dbqm oracle-client available -f json` / Entao exit 0 e a lista tem ao menos um pacote com `version` e uma URL em `oracle.com` · unit: `tests/test_cli.py::TestCmdOracleClient::test_available_table_format_prints_the_catalog`, `tests/core/test_oracle_client_installer.py::TestCatalog::test_urls_target_oracle_cdn` | manual | oracle | — |
| QA-OCLI-002 | Dado nada instalado / Quando `dbqm oracle-client list -f json` / Entao exit 0 e `data == []` · unit: `tests/test_cli.py::TestCmdOracleClient::test_list_on_a_machine_with_none_installed` | manual | oracle | — |
| QA-OCLI-003 | Dado uma versao de `available` / Quando `dbqm oracle-client install <versao> -f json` (**baixa de verdade**) / Entao exit 0, o progresso sai no stderr, stdout e o envelope com o diretorio instalado, e `list` passa a mostra-lo com a versao · unit: `tests/test_cli.py::TestCmdOracleClient::test_install_calls_through_with_the_named_version`, `::test_install_progress_goes_to_stderr_under_json_leaving_stdout_the_envelope` | manual | oracle | — |
| QA-OCLI-004 | Dado o client instalado / Quando `install` da mesma versao de novo / Entao exit 2, `usage`, o diretorio ja existe e nada e sobrescrito · unit: `tests/test_cli.py::TestCmdOracleClient::test_install_on_a_dir_that_already_exists_is_usage` | manual | oracle | — |
| QA-OCLI-005 | Dado o client instalado / Quando `dbqm oracle-client rm <nome> -f json` sem `--yes` fora de um terminal e depois com `--yes` / Entao a primeira e `usage` e nada e apagado; a segunda remove e `list` volta a `[]` · unit: `tests/test_cli.py::TestCmdOracleClient::test_rm_without_yes_and_without_a_tty_is_usage_and_deletes_nothing`, `::test_rm_with_yes_removes` | manual | oracle | — |
| QA-OCLI-006 | Dado uma versao que nao esta no catalogo / Quando `install nao-existe -f json` / Entao exit 2, `usage` · unit: `tests/test_cli.py::TestCmdOracleClient::test_install_on_an_unknown_version_is_usage` | manual | oracle | — |

## Manual — the script

```
dbqm oracle-client available -f json
# exit 0 · "data": [{"version": "...", "url": "https://download.oracle.com/...", ...}, ...]
dbqm oracle-client list -f json
# exit 0 · "data": []
dbqm oracle-client install <versao> -f json 2>progress.log
# real download; exit 0; stdout is one envelope; progress.log has the progress lines
dbqm oracle-client list -f json
# exit 0 · one entry with the version
dbqm oracle-client install <versao> -f json
# exit 2 · "code": "usage" (directory exists)
dbqm oracle-client rm <nome> -f json < /dev/null
# exit 2 · "code": "usage" · still listed
dbqm oracle-client rm <nome> --yes -f json
# exit 0 · list → []
dbqm oracle-client install nao-existe -f json
# exit 2 · "code": "usage"
```
