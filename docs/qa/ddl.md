# QA — ddl (`DDL`)

`dbqm ddl <objeto> <conexao> [--stdout] [-f table|json]`

Extracts the object's DDL: to a directory of `.sql` files under
`exports/ddl/<objeto>/<conexao>_<ts>/` by default, or to the output with
`--stdout`. A table brings its indexes (and triggers) along. Under
`-f json` the per-object progress goes to **stderr**, so stdout is the
envelope and nothing else. On SQLite the source is `sqlite_master`; on
Oracle it is `DBMS_METADATA` (manual row). Envelope and exit codes:
[output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-DDL-001 | Dado `clientes` / Quando `dbqm ddl clientes local --stdout -f json` / Entao exit 0, `data.path == null`, `data.objects` tem `clientes` (`TABLE`, ddl comecando por `CREATE TABLE clientes`) e `ix_clientes_nome` (`INDEX`, `CREATE UNIQUE INDEX ix_clientes_nome ON clientes(nome);`) | functional | all | tests/functional/test_ddl.py::test_stdout_returns_the_create_table_and_its_index |
| QA-DDL-002 | Dado `-f json` / Quando o comando termina / Entao stdout e so o envelope (parseia) e o progresso `[1/2] TABLE: clientes` foi para stderr | functional | all | tests/functional/test_ddl.py::test_json_keeps_the_progress_off_stdout |
| QA-DDL-003 | Dado `--stdout` sem `-f json` / Quando `dbqm ddl clientes local --stdout` / Entao `CREATE TABLE clientes` e `CREATE UNIQUE INDEX ix_clientes_nome` aparecem no stdout | functional | all | tests/functional/test_ddl.py::test_stdout_table_format_prints_the_ddl |
| QA-DDL-004 | Dado `v_ativos` / Quando `dbqm ddl v_ativos local --stdout -f json` / Entao um objeto `VIEW` cujo ddl e `CREATE VIEW v_ativos AS SELECT id, nome FROM clientes WHERE status = 'A';` | functional | all | tests/functional/test_ddl.py::test_a_view_is_extracted |
| QA-DDL-005 | Dado sem `--stdout` / Quando `dbqm ddl clientes local -f json` / Entao `data.path` e um diretorio existente sob a pasta de exports contendo um `.sql` com `CREATE TABLE clientes` | functional | all | tests/functional/test_ddl.py::test_without_stdout_a_sql_file_is_written |
| QA-DDL-006 | Dado um nome que nao existe / Quando `dbqm ddl nao_existe local -f json` / Entao exit 2, `not_found`, `Object 'nao_existe' not found.` | functional | all | tests/functional/test_ddl.py::test_an_unknown_object_is_not_found |
| QA-DDL-007 | Dado uma conexao nao registrada / Quando `dbqm ddl clientes nope -f json` / Entao exit 2, `not_found`, `Conexao 'nope' nao encontrada.` | functional | all | tests/functional/test_ddl.py::test_an_unknown_connection_is_not_found |
| QA-DDL-008 | Dado uma tabela Oracle / Quando `dbqm ddl <tabela> <oracle> --stdout -f json` / Entao o DDL vem de `DBMS_METADATA.GET_DDL` e inclui indices e constraints | manual | oracle | — |

## Manual (Oracle)

QA-DDL-008 — the Oracle extractor (`DBMS_METADATA`, dependents, grants)
is unit-tested with mocks in `tests/core/test_ddl_extractor.py`; this is
the run against a real dictionary. Before 2.9.0 the CLI ran this Oracle
SQL on every engine — found by the SQLite scenarios above.

```
dbqm ddl <TABELA> <conexao-oracle> --stdout -f json
# exit 0; stderr: "[1/N] TABLE: <TABELA>" ...
# "data": {"objects": [{"name": "<TABELA>", "obj_type": "TABLE", "ddl": "CREATE TABLE ..."}, ...], "path": null}
```
