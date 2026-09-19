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

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-RO-001 | Given `ro` / When `dbqm sql "UPDATE customers SET status='X' WHERE id=1" ro -f json` / Then exit 2, `error.code == "read_only"`, the message `Connection 'ro' is read-only. Use --force-write to send it anyway.` and the row still reads `A` | functional | all | tests/functional/test_read_only.py::test_an_update_is_refused_and_nothing_changes |
| QA-RO-002 | Given `ro` / When the same UPDATE runs with `--force-write --commit` / Then exit 0, `rows_affected == 1` and the row reads `X` on a following call | functional | all | tests/functional/test_read_only.py::test_force_write_lifts_the_guard_for_one_call |
| QA-RO-003 | Given `ro` / When `dbqm sql "SELECT name FROM customers WHERE id=1" ro -f json` / Then exit 0 and `data.rows == [["Ana"]]` | functional | all | tests/functional/test_read_only.py::test_a_select_passes |
| QA-RO-004 | Given `ro` / When `dbqm sql "SELECT id FROM customers" ro --explain -f json` / Then exit 0 and `data.plan` is not empty | functional | all | tests/functional/test_read_only.py::test_explain_passes |
| QA-RO-005 | Given `ro` / When `dbqm sql "EXPLAIN QUERY PLAN SELECT id FROM customers" ro -f json` (SQLite's native EXPLAIN, written by hand) / Then exit 0 — the guard recognises `QUERY PLAN` as an EXPLAIN that only reads | functional | sqlite | tests/functional/test_read_only.py::test_a_hand_written_explain_query_plan_passes |
| QA-RO-006 | Given `ro` / When `dbqm sql "SELECT 1; DROP TABLE customers" ro -f json` / Then exit 2, `read_only`, a message carrying `more than one statement`, and `customers` still exists | functional | all | tests/functional/test_read_only.py::test_two_statements_are_refused_by_count |
| QA-RO-007 | Given `ro` / When `INSERT`, `DELETE`, `CREATE TABLE`, `DROP TABLE` / Then each is `read_only`, exit 2 | functional | all | tests/functional/test_read_only.py::test_every_write_verb_is_refused |
| QA-RO-008 | Given `ro` and an UPDATE **without** `--commit` / When run / Then the refusal is `read_only`, not `usage` — the guard speaks before the question about `--commit` | functional | all | tests/functional/test_read_only.py::test_the_read_only_refusal_comes_before_the_commit_one |
| QA-RO-009 | Given `local` (writable) / When `--force-write` is passed on an UPDATE with `--commit` / Then it is a no-op: exit 0, the same as without the flag | functional | all | tests/functional/test_read_only.py::test_force_write_on_a_writable_connection_changes_nothing |
| QA-RO-010 | Given `ro` and a saved query whose SQL is an UPDATE / When `dbqm run atualiza -c ro -f json` / Then exit 2, `error.code == "usage"`, the message `Only SELECT statements are allowed.` and the row still reads `A` — `run` has no write path on any connection, which is why it has no `--force-write` | functional | all | tests/functional/test_read_only.py::test_run_of_a_writing_query_is_refused |
| QA-RO-011 | Given a read-only Oracle connection / When `dbqm sql "EXPLAIN PLAN FOR DELETE FROM t" <ro-oracle> -f json` / Then `read_only`, with the message `this EXPLAIN runs the command it explains` | manual | oracle | — |

## Manual (Oracle)

QA-RO-011 — `EXPLAIN ... DELETE` is refused on every engine by the same code
path (`tests/core/test_read_only.py::TestExplainThatExecutes` proves the
guard itself with mocks); this row is the end-to-end confirmation on an
engine where `EXPLAIN PLAN FOR` is the native form.

```
dbqm sql "EXPLAIN PLAN FOR DELETE FROM t" <ro-oracle-connection> -f json
# exit 2
# "error": {"code": "read_only", "message": "Connection '<name>' is read-only and this EXPLAIN runs the command it explains. Use --force-write to send it anyway.", "exit": 2}
```
