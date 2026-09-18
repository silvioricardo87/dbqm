# QA — ad-hoc SQL (`SQL`)

Ate a 2.9.0 `-e/--export` era aceito e ignorado em tudo que nao fosse
SELECT (o bloco de export mora dentro do ramo SELECT). Agora um comando
que nao retorna linhas recusa a flag, e recusa **antes de executar**.

`dbqm sql <sql|arquivo.sql> <conexao> [-p k=v] [-f table|json|csv|raw] [-e csv|json|txt|html] [--commit] [--force-write] [--explain]`

Runs one statement against a named connection. The seed every row below
counts on is `tests/functional/conftest.py::SEED`: `clientes` (3 rows: Ana/A,
Bia/I, Caio/A), `pedidos` (4 rows), a unique index `ix_clientes_nome`, a view
`v_ativos`. Envelope shape and exit codes: [output-contract.md](output-contract.md).
Read-only refusals: [read-only-guard.md](read-only-guard.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-SQL-001 | Dado a conexao `local` / Quando `dbqm sql "SELECT id, nome FROM clientes ORDER BY id" local -f json` / Entao exit 0, `data.rows` sao as 3 linhas do seed, `data.columns == ["id","nome"]` e `data.sql_type == "SELECT"` | functional | all | tests/functional/test_sql.py::test_select_returns_the_seed_rows |
| QA-SQL-002 | Dado `-p id=2` / Quando `dbqm sql "SELECT nome FROM clientes WHERE id = :id" local -p id=2 -f json` / Entao exit 0 e `data.rows == [["Bia"]]` — o bind chegou ao driver | functional | all | tests/functional/test_sql.py::test_a_param_reaches_the_statement |
| QA-SQL-003 | Dado um UPDATE sem `--commit` / Quando `dbqm sql "UPDATE clientes SET status='X' WHERE id=1" local -f json` / Entao exit 2, `error.code == "usage"`, mensagem `DML requires --commit to confirm the operation.` e a linha continua `A` numa leitura seguinte | functional | all | tests/functional/test_sql.py::test_dml_without_commit_is_refused_before_running |
| QA-SQL-004 | Dado o mesmo UPDATE com `--commit` / Quando executado e depois `dbqm sql "SELECT status FROM clientes WHERE id=1" local -f json` numa segunda chamada / Entao a primeira retorna `rows_affected == 1` e `committed == true`, a segunda le `X` | functional | all | tests/functional/test_sql.py::test_dml_with_commit_persists_for_the_next_call |
| QA-SQL-005 | Dado um `CREATE TABLE auditoria (id INTEGER)` / Quando executado e depois `dbqm objects local --type TABLE -f json` / Entao a primeira retorna `sql_type == "DDL"` e exit 0, a segunda lista `auditoria` | functional | all | tests/functional/test_sql.py::test_ddl_creates_a_table_that_objects_then_lists |
| QA-SQL-006 | Dado um DDL que o driver rejeita (`CREATE TABLE clientes (id INTEGER)`, ja existe) / Quando executado com `-f json` / Entao exit 4, `error.code == "sql_error"` e a mensagem do driver (`table clientes already exists`) | functional | all | tests/functional/test_sql.py::test_a_ddl_the_driver_rejects_is_sql_error |
| QA-SQL-007 | Dado `--explain` / Quando `dbqm sql "SELECT id FROM clientes" local --explain -f json` / Entao exit 0 e `data.plan` e uma lista nao vazia de strings mencionando `clientes` | functional | all | tests/functional/test_sql.py::test_explain_returns_a_plan |
| QA-SQL-008 | Dado uma tabela que nao existe / Quando `dbqm sql "SELECT * FROM nao_existe" local -f json` / Entao exit 4, `error.code == "sql_error"` e `error.message == "no such table: nao_existe"` (a mensagem do driver, nao uma parafrase) | functional | all | tests/functional/test_sql.py::test_a_statement_the_driver_rejects_is_sql_error |
| QA-SQL-009 | Dado um verbo que o dbqm nao reconhece (`SELEC 1`) / Quando executado / Entao exit 2 e `error.code == "usage"` (o core recusa antes de enviar ao driver; nao e `sql_error`) | functional | all | tests/functional/test_sql.py::test_an_unknown_verb_is_usage_not_sql_error |
| QA-SQL-010 | Dado um arquivo `consulta.sql` contendo `SELECT COUNT(*) AS n FROM pedidos` / Quando `dbqm sql <caminho> local -f json` / Entao o arquivo e lido e `data.rows == [[4]]` | functional | all | tests/functional/test_sql.py::test_a_sql_file_path_is_read |
| QA-SQL-011 | Dado `-e csv`, `-e json`, `-e txt`, `-e html` / Quando `dbqm sql "SELECT id, nome FROM clientes" local -e <fmt> -f json` / Entao exit 0, `data.exported` aponta para um arquivo existente com a extensao do formato (`.htm` para html), `data.format == <fmt>`, e o conteudo traz `Ana` | functional | all | tests/functional/test_sql.py::test_export_writes_a_file_per_format |
| QA-SQL-012 | Dado `-p semigual` / Quando `dbqm sql "SELECT 1" local -p semigual -f json` / Entao exit 2, `usage`, mensagem `Invalid parameter (use key=value): semigual` | functional | all | tests/functional/test_sql.py::test_a_param_without_equals_is_usage |
| QA-SQL-013 | Dado uma conexao inexistente / Quando `dbqm sql "SELECT 1" nope -f json` / Entao exit 2, `not_found`, mensagem `Connection "nope" not found.` | functional | all | tests/functional/test_sql.py::test_an_unknown_connection_is_not_found |
| QA-SQL-014 | Dado `-f table` (padrao) / Quando `dbqm sql "SELECT nome FROM clientes WHERE id=1" local` / Entao exit 0 e `Ana` aparece no stdout | functional | all | tests/functional/test_sql.py::test_table_format_prints_the_rows |
| QA-SQL-016 | Dado `-e csv` num UPDATE / Quando `dbqm sql "UPDATE clientes SET status='X' WHERE id=1" local --commit -e csv -f json` / Entao exit 2, `usage`, `--export needs a command that returns rows; UPDATE does not return any.`, a linha continua `A` e nenhum arquivo foi escrito — a recusa vem antes de executar | functional | all | tests/functional/test_sql.py::test_export_on_a_dml_is_refused_before_the_write |
| QA-SQL-017 | Dado `-e json` num DDL / Quando `dbqm sql "CREATE TABLE auditoria (id INTEGER)" local -e json -f json` / Entao exit 2, `usage`, `... DDL nao retorna.` e `objects` nao lista `auditoria` | functional | all | tests/functional/test_sql.py::test_export_on_a_ddl_is_refused_and_nothing_is_created |
| QA-SQL-018 | Dado `-e csv` num SELECT / Quando executado / Entao exit 0 e o arquivo existe — a guarda nomeia tipos de comando, nao a flag | functional | all | tests/functional/test_sql.py::test_a_select_still_exports |
| QA-SQL-019 | Dado `--explain -e csv` / Quando `dbqm sql "SELECT id FROM clientes" local --explain -e csv -f json` / Entao exit 0 e o arquivo traz o cabecalho `plan` e o plano — um plano e um conjunto de resultado, e este ramo retorna antes da guarda | functional | all | tests/functional/test_sql.py::test_explain_exports_the_plan |
| QA-SQL-020 | Dado a conexao `ro` e `UPDATE ... --commit -e csv` / Quando executado / Entao exit 2 e `read_only` — a conexao recusar vem antes de qualquer problema de flag | functional | all | tests/functional/test_sql.py::test_the_read_only_refusal_comes_before_the_export_one |
| QA-SQL-021 | Dado a tela **SQL Avulso** da TUI com a conexao `local` / Quando um SELECT e executado pelo botao Executar / Entao a barra de informacao mostra `3 registros` e a tabela traz 3 linhas | functional | all | tests/ui/test_functional_screens.py::test_adhoc_executes_a_select_and_shows_the_rows |
| QA-SQL-022 | Dado `-p naoexiste=1` num SQL que nao usa esse bind / Quando executado / Entao exit 2, `validation`, `The SQL does not use the parameter "naoexiste".` | functional | all | tests/functional/test_sql.py::test_a_param_the_statement_never_binds_is_refused |
| QA-SQL-023 | Dado um caminho terminado em `.sql` que nao existe / Quando `dbqm sql caminho.sql local -f json` / Entao exit 2, `not_found`, `File "<path>" not found.` — antes era lido como SQL e voltava `Tipo de SQL nao suportado` | functional | all | tests/functional/test_sql.py::test_a_missing_sql_file_says_so |
| QA-SQL-015 | Dado um bloco PL/SQL anonimo com DBMS_OUTPUT / Quando `dbqm sql "BEGIN DBMS_OUTPUT.PUT_LINE('oi'); END;" <oracle> -f json` / Entao `data.sql_type == "PLSQL"` e `warnings == ["oi"]` | manual | oracle | — |

## Manual (Oracle)

QA-SQL-015 — DBMS_OUTPUT capture only exists on Oracle. The mocked CLI tests
prove the CLI forwards `output_lines` as `warnings`; this row is what proves
the driver side.

```
dbqm sql "BEGIN DBMS_OUTPUT.PUT_LINE('oi'); END;" <conexao-oracle> -f json
# exit 0
# "data": {"sql_type": "PLSQL", ...}, "warnings": ["oi"]
```
