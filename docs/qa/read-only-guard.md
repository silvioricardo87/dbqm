# QA — the read-only guard (`RO`)

A connection saved with `read_only=true` refuses anything that is not a
`SELECT` or an `EXPLAIN` of a `SELECT`, **before** the statement is sent.
`--force-write` lifts it for one `dbqm sql` call. The guard lives in
`dbqm/core/read_only.py` and every path that sends SQL calls it
(`execute_adhoc`, `execute_explain`, `execute_query`, `execute_across`).

Fixture: `ro` is a second connection on the same SQLite file as `local`
(`tests/functional/conftest.py::read_only_db`), so a refusal is proven by
reading the row back through `local` and finding it untouched. Envelope and
exit codes: [output-contract.md](output-contract.md).

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-RO-001 | Dado `ro` / Quando `dbqm sql "UPDATE clientes SET status='X' WHERE id=1" ro -f json` / Entao exit 2, `error.code == "read_only"`, mensagem `Conexao 'ro' e somente leitura. Use --force-write para enviar assim mesmo.` e a linha continua `A` | functional | all | tests/functional/test_read_only.py::test_an_update_is_refused_and_nothing_changes |
| QA-RO-002 | Dado `ro` / Quando o mesmo UPDATE com `--force-write --commit` / Entao exit 0, `rows_affected == 1` e a linha le `X` numa chamada seguinte | functional | all | tests/functional/test_read_only.py::test_force_write_lifts_the_guard_for_one_call |
| QA-RO-003 | Dado `ro` / Quando `dbqm sql "SELECT nome FROM clientes WHERE id=1" ro -f json` / Entao exit 0 e `data.rows == [["Ana"]]` | functional | all | tests/functional/test_read_only.py::test_a_select_passes |
| QA-RO-004 | Dado `ro` / Quando `dbqm sql "SELECT id FROM clientes" ro --explain -f json` / Entao exit 0 e `data.plan` nao vazio | functional | all | tests/functional/test_read_only.py::test_explain_passes |
| QA-RO-005 | Dado `ro` / Quando `dbqm sql "EXPLAIN QUERY PLAN SELECT id FROM clientes" ro -f json` (o EXPLAIN nativo do SQLite, escrito a mao) / Entao exit 0 — a guarda reconhece `QUERY PLAN` como um EXPLAIN que so le | functional | sqlite | tests/functional/test_read_only.py::test_a_hand_written_explain_query_plan_passes |
| QA-RO-006 | Dado `ro` / Quando `dbqm sql "SELECT 1; DROP TABLE clientes" ro -f json` / Entao exit 2, `read_only`, mensagem contendo `mais de um statement`, e `clientes` continua existindo | functional | all | tests/functional/test_read_only.py::test_two_statements_are_refused_by_count |
| QA-RO-007 | Dado `ro` / Quando `INSERT`, `DELETE`, `CREATE TABLE`, `DROP TABLE` / Entao cada um e `read_only` exit 2 | functional | all | tests/functional/test_read_only.py::test_every_write_verb_is_refused |
| QA-RO-008 | Dado `ro` e um UPDATE **sem** `--commit` / Quando executado / Entao a recusa e `read_only`, nao `usage` — a guarda fala antes da pergunta sobre `--commit` | functional | all | tests/functional/test_read_only.py::test_the_read_only_refusal_comes_before_the_commit_one |
| QA-RO-009 | Dado `local` (gravavel) / Quando `--force-write` num UPDATE com `--commit` / Entao e um no-op: exit 0 igual a sem a flag | functional | all | tests/functional/test_read_only.py::test_force_write_on_a_writable_connection_changes_nothing |
| QA-RO-010 | Dado `ro` e uma consulta salva cujo SQL e um UPDATE / Quando `dbqm run atualiza -c ro -f json` / Entao exit 2, `error.code == "usage"`, mensagem `Apenas comandos SELECT sao permitidos.` e a linha continua `A` — `run` nao tem caminho de escrita em conexao nenhuma, e por isso nao tem `--force-write` | functional | all | tests/functional/test_read_only.py::test_run_of_a_writing_query_is_refused |
| QA-RO-011 | Dado uma conexao Oracle somente leitura / Quando `dbqm sql "EXPLAIN PLAN FOR DELETE FROM t" <ro-oracle> -f json` / Entao `read_only` com a mensagem `este EXPLAIN executa o comando que explica` | manual | oracle | — |

## Manual (Oracle)

QA-RO-011 — `EXPLAIN ... DELETE` is refused on every engine by the same code
path (`tests/core/test_read_only.py::TestExplainThatExecutes` proves the
guard itself with mocks); this row is the end-to-end confirmation on an
engine where `EXPLAIN PLAN FOR` is the native form.

```
dbqm sql "EXPLAIN PLAN FOR DELETE FROM t" <conexao-oracle-ro> -f json
# exit 2
# "error": {"code": "read_only", "message": "Conexao '<nome>' e somente leitura e este EXPLAIN executa o comando que explica. Use --force-write para enviar assim mesmo.", "exit": 2}
```
