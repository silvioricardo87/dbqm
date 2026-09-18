# QA — routines: `call` (`CALL`)

`dbqm call <PACOTE.ROTINA|ROTINA> <conexao> [-p k=v]... [--commit] [-f table|json]`

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

| ID | Cenario | Camada | Engine | Teste |
|---|---|---|---|---|
| QA-CALL-001 | Dado `qa_pkg.soma` com IN `a`,`b` e OUT `r` / Quando `dbqm call qa_pkg.soma <ora> -p a=2 -p b=3 -f json` / Entao exit 0, `data.success == true`, `data.out_values == {"R": "5"}` e `warnings == ["somou"]` -- so o que a rotina imprimiu · unit: `tests/test_cli.py::TestCmdCall::test_a_package_routine_resolves_through_list_package_routines` | manual | oracle | — |
| QA-CALL-002 | Dado a funcao avulsa `qa_triplo` / Quando `dbqm call qa_triplo <ora> -p n=4 -f json` / Entao `data.return_value == "12"` e nenhum `warnings` · unit: `tests/test_cli.py::TestCmdCall::test_a_standalone_function_is_re_tagged_before_execute_routine` | manual | oracle | — |
| QA-CALL-003 | Dado `qa_pkg.dobro` / Quando `-p n=5 -f json` / Entao `data.return_value == "10"` e nenhum `warnings` · unit: `tests/test_cli.py::TestCmdCall::test_json_carries_the_result_shape` | manual | oracle | — |
| QA-CALL-004 | Dado `qa_grava` sem `--commit` / Quando `dbqm call qa_grava <ora> -p v=1 -f json` e depois `dbqm sql "SELECT COUNT(*) FROM qa_log" <ora> -f json` / Entao `data.committed == false` e a contagem nao mudou · unit: `tests/test_cli.py::TestCmdCall::test_without_commit_the_transaction_is_rolled_back` | manual | oracle | — |
| QA-CALL-005 | Dado `qa_grava` com `--commit` / Quando `dbqm call qa_grava <ora> -p v=1 --commit -f json` e a mesma contagem / Entao `data.committed == true` e a contagem subiu 1; em `-f table` a saida diz qual dos dois aconteceu · unit: `tests/test_cli.py::TestCmdCall::test_with_commit_the_transaction_is_committed`, `::test_the_table_output_says_which_happened` | manual | oracle | — |
| QA-CALL-006 | Dado uma conexao Oracle `read_only` / Quando `dbqm call qa_pkg.dobro <ora-ro> -p n=1 -f json` / Entao exit 2, `read_only`, mensagem `Connection '<name>' is read-only and a routine can write whatever the command text says. ...` · unit: `tests/test_cli.py::TestCmdCall::test_a_read_only_connection_is_refused` | manual | oracle | — |
| QA-CALL-007 | Dado `qa_pkg.soma` sem `-p b` / Quando executado / Entao exit 2, `validation`, `Required parameter missing: B.` · unit: `tests/test_cli.py::TestCmdCall::test_a_missing_required_parameter_is_a_validation_error` | manual | oracle | — |
| QA-CALL-008 | Dado `-p x=1` que a rotina nao declara / Quando `dbqm call qa_pkg.dobro <ora> -p n=1 -p x=1 -f json` / Entao exit 2, `validation`, `Parameter "x" does not exist in routine "DOBRO".` · unit: `tests/test_cli.py::TestCmdCall::test_an_undeclared_parameter_is_a_validation_error` | manual | oracle | — |
| QA-CALL-009 | Dado um nome avulso que nao existe / Quando `dbqm call nao_existe <ora> -f json` / Entao exit 4, `sql_error`, mensagem com `PLS-00201` · unit: `tests/test_cli.py::TestCmdCall::test_a_bare_name_that_does_not_exist_exits_four` | manual | oracle | — |
| QA-CALL-011 | Dado uma rotina que imprime ela mesma `DBMS_OUTPUT.PUT_LINE('RETURN=nao sou o retorno')` e retorna 7 / Quando chamada / Entao `data.return_value == "7"` e a linha impressa fica em `warnings`, intacta · unit: `tests/core/test_object_browser.py::TestExecuteRoutineHandsValuesBack::test_a_routine_printing_RETURN_no_longer_shadows_the_real_one` | manual | oracle | — |
| QA-CALL-012 | Dado uma rotina avulsa de **outro** schema que o usuario pode executar / Quando `dbqm call outra_proc <ora> -p a=1 -f json` / Entao os parametros sao resolvidos e a chamada roda -- `all_arguments` era filtrado por `owner = USER`, entao ela voltava sem parametro nenhum, indistinguivel de uma rotina sem argumentos · unit: `tests/core/test_object_browser.py::TestGetStandaloneRoutineInfo::test_the_owner_comes_from_all_objects_not_from_USER` | manual | oracle | — |
| QA-CALL-013 | Dado a tela **Executar Rotina** da TUI com `qa_grava` e a caixa `Confirmar alteracoes (commit)` desmarcada / Quando executada / Entao o painel diz `Transacao desfeita (rollback) -- nada foi gravado.` e a contagem em `qa_log` nao muda | manual | oracle | — |
| QA-CALL-014 | Dado a mesma tela com a caixa marcada / Quando executada / Entao o painel diz `Transacao confirmada (commit).` e a contagem sobe 1 -- ate a 2.10.0 a tela nunca commitava e dizia "Executado com sucesso" sobre trabalho que o driver descartava | manual | oracle | — |
| QA-CALL-015 | Dado a mesma tela e uma rotina com OUT param / Quando executada / Entao o painel traz a secao `Output parameters:` com `R = 5` | manual | oracle | — |
| QA-CALL-010 | Dado uma rotina de pacote que nao existe / Quando `dbqm call qa_pkg.nada <ora> -f json` / Entao exit 2, `not_found` (o spec do pacote lista as rotinas) · unit: `tests/test_cli.py::TestCmdCall::test_a_routine_that_does_not_exist_is_not_found` | manual | oracle | — |

## Manual (Oracle) — the script

```
dbqm call qa_pkg.soma <ora> -p a=2 -p b=3 -f json
# exit 0 · "warnings": ["somou"]
# "data": {"success": true, "committed": false, "out_values": {"R": "5"}, ...}

dbqm call qa_triplo <ora> -p n=4 -f json
# exit 0 · no "warnings" · "data": {"return_value": "12", "out_values": {}, ...}

# the TUI screen, for QA-CALL-013..015: Ferramentas -> Executar Rotina
#   caixa desmarcada -> "Transacao desfeita (rollback) -- nada foi gravado."
#   caixa marcada    -> "Transacao confirmada (commit)."
#   OUT param        -> secao "Parametros de saida:" com "R = 5"

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
