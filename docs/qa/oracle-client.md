# QA — the Oracle Instant Client installer (`OCLI`)

`dbqm oracle-client available|list|install <version>|rm <name> [--yes] [-f table|json]`

Downloads an Oracle Instant Client for the host platform from Oracle's
CDN into dbqm's clients directory, lists what is installed, removes one.
`install` is a **real download** of tens of megabytes; the row says so.
Under `-f json` the download progress goes to stderr so stdout stays the
envelope. Everything but the network and the archive is unit-tested with
mocks in `tests/test_cli.py::TestCmdOracleClient` and
`tests/core/test_oracle_client_installer.py`; each row names its unit test.

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-OCLI-001 | Given this machine / When `dbqm oracle-client available -f json` / Then exit 0 and the list carries at least one package with a `version` and a URL on `oracle.com` · unit: `tests/test_cli.py::TestCmdOracleClient::test_available_table_format_prints_the_catalog`, `tests/core/test_oracle_client_installer.py::TestCatalog::test_urls_target_oracle_cdn` | manual | oracle | — |
| QA-OCLI-002 | Given nothing installed / When `dbqm oracle-client list -f json` / Then exit 0 and `data == []` · unit: `tests/test_cli.py::TestCmdOracleClient::test_list_on_a_machine_with_none_installed` | manual | oracle | — |
| QA-OCLI-003 | Given a version from `available` / When `dbqm oracle-client install <version> -f json` (**a real download**) / Then exit 0, the progress goes to stderr, stdout is the envelope carrying the installed directory, and `list` starts showing it with its version · unit: `tests/test_cli.py::TestCmdOracleClient::test_install_calls_through_with_the_named_version`, `::test_install_progress_goes_to_stderr_under_json_leaving_stdout_the_envelope` | manual | oracle | — |
| QA-OCLI-004 | Given the client installed / When `install` runs again for the same version / Then exit 2, `usage`, the directory is still there and nothing is overwritten · unit: `tests/test_cli.py::TestCmdOracleClient::test_install_on_a_dir_that_already_exists_is_usage` | manual | oracle | — |
| QA-OCLI-005 | Given the client installed / When `dbqm oracle-client rm <name> -f json` runs without `--yes` off a terminal, then with `--yes` / Then the first is `usage` and deletes nothing; the second removes it and `list` goes back to `[]` · unit: `tests/test_cli.py::TestCmdOracleClient::test_rm_without_yes_and_without_a_tty_is_usage_and_deletes_nothing`, `::test_rm_with_yes_removes` | manual | oracle | — |
| QA-OCLI-006 | Given a version that is not in the catalogue / When `install nao-existe -f json` / Then exit 2, `usage` · unit: `tests/test_cli.py::TestCmdOracleClient::test_install_on_an_unknown_version_is_usage` | manual | oracle | — |

## Manual — the script

```
dbqm oracle-client available -f json
# exit 0 · "data": [{"version": "...", "url": "https://download.oracle.com/...", ...}, ...]
dbqm oracle-client list -f json
# exit 0 · "data": []
dbqm oracle-client install <version> -f json 2>progress.log
# real download; exit 0; stdout is one envelope; progress.log has the progress lines
dbqm oracle-client list -f json
# exit 0 · one entry with the version
dbqm oracle-client install <version> -f json
# exit 2 · "code": "usage" (directory exists)
dbqm oracle-client rm <name> -f json < /dev/null
# exit 2 · "code": "usage" · still listed
dbqm oracle-client rm <name> --yes -f json
# exit 0 · list → []
dbqm oracle-client install nao-existe -f json
# exit 2 · "code": "usage"
```
