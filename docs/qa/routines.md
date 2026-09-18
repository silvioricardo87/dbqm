# QA — routines: `call` (`CALL`)

`dbqm call <PACKAGE.ROUTINE|ROUTINE> <connection> [-p k=v]... [--commit] [-f table|json]`

Runs a stored procedure or function through an anonymous block, binding
`-p` values to IN params, declaring variables for OUT/IN OUT ones and
handing them (and a function's return) back in `data.out_values` and
`data.return_value`. They travel through DBMS_OUTPUT under a marker
generated per execution, so `warnings` now holds only what the routine
itself printed -- until 2.10.0 the values arrived as bare `NOME=valor`
lines mixed into it, and a routine printing its own `RETURN=` shadowed
the real return value.
Without `--commit` the block is rolled back; with it, committed only if
the routine succeeded. **Oracle only**: on any other engine the refusal is
`usage` before a connection opens (QA-DISC-004's sibling; proven on SQLite
by `tests/test_cli.py::TestSqliteFromTheCli::test_call_refuses_sqlite_before_any_connection_opens`).

Every row here is `manual`: the suite has no Oracle. The orchestration —
which token, which message, commit versus rollback — is proven with mocks
in `tests/test_cli.py::TestCmdCall`, and each row names the unit test that
covers its CLI side, so the reader sees what a real Oracle adds: the
driver, `ALL_ARGUMENTS`, DBMS_OUTPUT and PLS-00201 itself.

Setup the script assumes, run once on the Oracle you have:

```sql
CREATE OR REPLACE PACKAGE qa_pkg AS
  PROCEDURE soma(a IN NUMBER, b IN NUMBER, r OUT NUMBER);
  FUNCTION dobro(n IN NUMBER) RETURN NUMBER;
END qa_pkg;
/
CREATE OR REPLACE PACKAGE BODY qa_pkg AS
  PROCEDURE soma(a IN NUMBER, b IN NUMBER, r OUT NUMBER) IS
  BEGIN r := a + b; DBMS_OUTPUT.PUT_LINE('somou'); END;
  FUNCTION dobro(n IN NUMBER) RETURN NUMBER IS BEGIN RETURN n * 2; END;
END qa_pkg;
/
CREATE OR REPLACE FUNCTION qa_triplo(n IN NUMBER) RETURN NUMBER IS BEGIN RETURN n * 3; END;
/
CREATE TABLE qa_log (id NUMBER);
CREATE OR REPLACE PROCEDURE qa_grava(v IN NUMBER) IS BEGIN INSERT INTO qa_log VALUES (v); END;
/
```

| ID | Scenario | Layer | Engine | Test |
|---|---|---|---|---|
| QA-CALL-001 | Given `qa_pkg.soma` with IN `a`, `b` and OUT `r` / When `dbqm call qa_pkg.soma <ora> -p a=2 -p b=3 -f json` / Then exit 0, `data.success == true`, `data.out_values == {"R": "5"}` and `warnings == ["somou"]` -- only what the routine printed · unit: `tests/test_cli.py::TestCmdCall::test_a_package_routine_resolves_through_list_package_routines` | manual | oracle | — |
| QA-CALL-002 | Given the standalone function `qa_triplo` / When `dbqm call qa_triplo <ora> -p n=4 -f json` / Then `data.return_value == "12"` and no `warnings` · unit: `tests/test_cli.py::TestCmdCall::test_a_standalone_function_is_re_tagged_before_execute_routine` | manual | oracle | — |
| QA-CALL-003 | Given `qa_pkg.dobro` / When `-p n=5 -f json` / Then `data.return_value == "10"` and no `warnings` · unit: `tests/test_cli.py::TestCmdCall::test_json_carries_the_result_shape` | manual | oracle | — |
| QA-CALL-004 | Given `qa_grava` without `--commit` / When `dbqm call qa_grava <ora> -p v=1 -f json` then `dbqm sql "SELECT COUNT(*) FROM qa_log" <ora> -f json` / Then `data.committed == false` and the count did not move · unit: `tests/test_cli.py::TestCmdCall::test_without_commit_the_transaction_is_rolled_back` | manual | oracle | — |
| QA-CALL-005 | Given `qa_grava` with `--commit` / When `dbqm call qa_grava <ora> -p v=1 --commit -f json` and the same count / Then `data.committed == true` and the count went up by 1; under `-f table` the output says which of the two happened · unit: `tests/test_cli.py::TestCmdCall::test_with_commit_the_transaction_is_committed`, `::test_the_table_output_says_which_happened` | manual | oracle | — |
| QA-CALL-006 | Given a `read_only` Oracle connection / When `dbqm call qa_pkg.dobro <ora-ro> -p n=1 -f json` / Then exit 2, `read_only`, the message `Connection '<name>' is read-only and a routine can write whatever the command text says. ...` · unit: `tests/test_cli.py::TestCmdCall::test_a_read_only_connection_is_refused` | manual | oracle | — |
| QA-CALL-007 | Given `qa_pkg.soma` without `-p b` / When run / Then exit 2, `validation`, `Required parameter missing: B.` · unit: `tests/test_cli.py::TestCmdCall::test_a_missing_required_parameter_is_a_validation_error` | manual | oracle | — |
| QA-CALL-008 | Given `-p x=1`, which the routine does not declare / When `dbqm call qa_pkg.dobro <ora> -p n=1 -p x=1 -f json` / Then exit 2, `validation`, `Parameter "x" does not exist in routine "DOBRO".` · unit: `tests/test_cli.py::TestCmdCall::test_an_undeclared_parameter_is_a_validation_error` | manual | oracle | — |
| QA-CALL-009 | Given a standalone name that does not exist / When `dbqm call nao_existe <ora> -f json` / Then exit 4, `sql_error`, a message carrying `PLS-00201` · unit: `tests/test_cli.py::TestCmdCall::test_a_bare_name_that_does_not_exist_exits_four` | manual | oracle | — |
| QA-CALL-011 | Given a routine that prints `DBMS_OUTPUT.PUT_LINE('RETURN=nao sou o retorno')` itself and returns 7 / When called / Then `data.return_value == "7"` and the printed line stays in `warnings`, untouched · unit: `tests/core/test_object_browser.py::TestExecuteRoutineHandsValuesBack::test_a_routine_printing_RETURN_no_longer_shadows_the_real_one` | manual | oracle | — |
| QA-CALL-012 | Given a standalone routine in **another** schema that the user may execute / When `dbqm call outra_proc <ora> -p a=1 -f json` / Then the parameters resolve and the call runs -- `all_arguments` was filtered by `owner = USER`, so it came back with no parameters at all, indistinguishable from a routine that takes none · unit: `tests/core/test_object_browser.py::TestGetStandaloneRoutineInfo::test_the_owner_comes_from_all_objects_not_from_USER` | manual | oracle | — |
| QA-CALL-013 | Given the TUI's **Run Routine** screen with `qa_grava` and the `Confirm the changes (commit)` box unticked / When run / Then the panel says `Transaction rolled back — nothing was written.` and the count in `qa_log` does not move | manual | oracle | — |
| QA-CALL-014 | Given the same screen with the box ticked / When run / Then the panel says `Transaction committed.` and the count goes up by 1 -- until 2.10.0 the screen never committed and said "Ran successfully" over work the driver was discarding | manual | oracle | — |
| QA-CALL-015 | Given the same screen and a routine with an OUT param / When run / Then the panel carries the `Output parameters:` section with `R = 5` | manual | oracle | — |
| QA-CALL-010 | Given a package routine that does not exist / When `dbqm call qa_pkg.nada <ora> -f json` / Then exit 2, `not_found` (the package spec lists its routines) · unit: `tests/test_cli.py::TestCmdCall::test_a_routine_that_does_not_exist_is_not_found` | manual | oracle | — |

## Manual (Oracle) — the script

```
dbqm call qa_pkg.soma <ora> -p a=2 -p b=3 -f json
# exit 0 · "warnings": ["somou"]
# "data": {"success": true, "committed": false, "out_values": {"R": "5"}, ...}

dbqm call qa_triplo <ora> -p n=4 -f json
# exit 0 · no "warnings" · "data": {"return_value": "12", "out_values": {}, ...}

# the TUI screen, for QA-CALL-013..015: Tools -> Run Routine
#   box unticked -> "Transaction rolled back — nothing was written."
#   box ticked   -> "Transaction committed."
#   OUT param    -> the "Output parameters:" section with "R = 5"

dbqm call qa_grava <ora> -p v=1 -f json && dbqm sql "SELECT COUNT(*) FROM qa_log" <ora> -f json
# "committed": false · count unchanged
dbqm call qa_grava <ora> -p v=1 --commit -f json && dbqm sql "SELECT COUNT(*) FROM qa_log" <ora> -f json
# "committed": true · count + 1

dbqm call qa_pkg.dobro <ora-ro> -p n=1 -f json
# exit 2 · "code": "read_only"
dbqm call qa_pkg.soma <ora> -p a=1 -f json
# exit 2 · "code": "validation" · "Required parameter missing: B."
dbqm call qa_pkg.dobro <ora> -p n=1 -p x=1 -f json
# exit 2 · "code": "validation" · "Parameter \"x\" does not exist in routine \"DOBRO\"."
dbqm call nao_existe <ora> -f json
# exit 4 · "code": "sql_error" · message contains PLS-00201
dbqm call qa_pkg.nada <ora> -f json
# exit 2 · "code": "not_found"
```
