# QA — schema discovery (`DISC`)

`dbqm objects <conexao> [--type TABLE|VIEW|PACKAGE|ROUTINE]`,
`dbqm describe <objeto> <conexao>`, `dbqm rows <tabela> <conexao> [--limit N] [--offset N]`.

What an agent runs before writing SQL against a database it has not seen:
the names, then one object's columns/keys/indexes, then a page of rows.
A type the engine does not have is `usage` and the message names the
engine. Seed: `clientes` (PK `id`, unique index `ix_clientes_nome`),
`pedidos` (FK `cliente_id -> clientes.id`), view `v_ativos`. Envelope and
exit codes: [output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-DISC-001 | Dado `local` / Quando `dbqm objects local -f json` (tipo padrao TABLE) / Entao exit 0, `data.obj_type == "TABLE"` e `data.objects == ["clientes","pedidos"]` | functional | all | tests/functional/test_discovery.py::test_objects_lists_the_seed_tables |
| QA-DISC-002 | Dado `local` / Quando `dbqm objects local --type VIEW -f json` / Entao `data.objects == ["v_ativos"]` | functional | all | tests/functional/test_discovery.py::test_objects_lists_the_seed_view |
| QA-DISC-003 | Dado `local` (sqlite) / Quando `dbqm objects local --type PACKAGE -f json` / Entao exit 2, `usage`, `Packages only exist on Oracle. This connection is sqlite.` | functional | sqlite | tests/functional/test_discovery.py::test_packages_on_sqlite_is_usage_naming_the_engine |
| QA-DISC-004 | Dado `local` (sqlite) / Quando `dbqm objects local --type ROUTINE -f json` / Entao exit 2, `usage`, `SQLite has no stored routines.` | functional | sqlite | tests/functional/test_discovery.py::test_routines_on_sqlite_is_usage |
| QA-DISC-005 | Dado `clientes` / Quando `dbqm describe clientes local -f json` / Entao `data.object_type == "TABLE"`, colunas `id` (`is_pk == true`, `INTEGER`), `nome` (`nullable == false`, `TEXT`), `status`; e `data.indexes == [{"name":"ix_clientes_nome","columns":["nome"],"is_unique":true}]` | functional | all | tests/functional/test_discovery.py::test_describe_reports_pk_nullability_and_the_unique_index |
| QA-DISC-006 | Dado `pedidos` / Quando `dbqm describe pedidos local -f json` / Entao a coluna `cliente_id` traz `fk_ref == "clientes.id"` | functional | all | tests/functional/test_discovery.py::test_describe_reports_the_foreign_key |
| QA-DISC-007 | Dado `v_ativos` / Quando `dbqm describe v_ativos local -f json` / Entao `data.object_type == "VIEW"`, colunas `id` e `nome`, e `data.sql_definition` comeca por `CREATE VIEW v_ativos` | functional | all | tests/functional/test_discovery.py::test_describe_a_view_brings_its_definition |
| QA-DISC-008 | Dado um nome que nao existe / Quando `dbqm describe nao_existe local -f json` / Entao exit 2, `not_found`, `"nao_existe" is neither a table nor a view in local.` | functional | all | tests/functional/test_discovery.py::test_describe_of_an_unknown_object_is_not_found |
| QA-DISC-009 | Dado `-f table` / Quando `dbqm describe clientes local` / Entao exit 0 e `PK`, `ix_clientes_nome` e `UNIQUE` aparecem no stdout | functional | all | tests/functional/test_discovery.py::test_describe_table_format_prints_keys_and_indexes |
| QA-DISC-010 | Dado `clientes` / Quando `dbqm rows clientes local -f json` / Entao `data.rows` sao as 3 linhas do seed, `row_count == 3`, `total_count == 3`, `limit == 100`, `offset == 0` | functional | all | tests/functional/test_discovery.py::test_rows_returns_the_seed |
| QA-DISC-011 | Dado `--limit 2` e depois `--limit 2 --offset 2` / Quando executados / Entao a primeira traz Ana e Bia com `total_count == 3`; a segunda traz so Caio, `row_count == 1`, `offset == 2` | functional | all | tests/functional/test_discovery.py::test_rows_pages_with_limit_and_offset |
| QA-DISC-012 | Dado `--limit 0` ou `--offset -1` / Quando executados / Entao exit 2, `usage`, `--limit must be greater than zero.` / `--offset cannot be negative.` | functional | all | tests/functional/test_discovery.py::test_rows_refuses_a_bad_page |
| QA-DISC-013 | Dado uma tabela que nao existe / Quando `dbqm rows nao_existe local -f json` / Entao exit 2, `not_found`, `Table "nao_existe" not found in local.` | functional | all | tests/functional/test_discovery.py::test_rows_of_an_unknown_table_is_not_found |
| QA-DISC-014 | Dado `-f csv` / Quando `dbqm rows clientes local -f csv` / Entao o stdout comeca por `id,nome,status` e tem uma linha por registro | functional | all | tests/functional/test_discovery.py::test_rows_csv_prints_a_header_and_the_rows |
| QA-DISC-015 | Dado uma conexao nao registrada / Quando `dbqm objects nope -f json` / Entao exit 2, `not_found`, `Connection "nope" not found.` | functional | all | tests/functional/test_discovery.py::test_objects_of_an_unknown_connection_is_not_found |
| QA-DISC-016 | Dado uma conexao Oracle com um package / Quando `dbqm objects <oracle> --type PACKAGE -f json` e `--type ROUTINE` / Entao os nomes de `ALL_OBJECTS` do owner | manual | oracle | — |

## Manual (Oracle)

QA-DISC-016 — the Oracle catalogue arms (`ALL_OBJECTS`, `ALL_PROCEDURES`)
are unit-tested with mocks in `tests/core/test_object_browser.py`; this is
the confirmation against a real dictionary.

```
dbqm objects <conexao-oracle> --type PACKAGE -f json
# "data": {"obj_type": "PACKAGE", "objects": ["PKG_...", ...]}
dbqm objects <conexao-oracle> --type ROUTINE -f json
# "data": {"obj_type": "ROUTINE", "objects": ["PROC_...", "FN_...", ...]}
```
