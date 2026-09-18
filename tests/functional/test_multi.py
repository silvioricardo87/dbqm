"""docs/qa/multi.md — one SQL across `local` and `local2`.

The two files differ in pedido 13 only, so `clientes` agrees and `pedidos`
diverges; every refusal is checked to have happened before anything ran,
by reading the data back afterwards.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.functional.conftest import envelope, invoke

PED = "SELECT id, valor FROM pedidos ORDER BY id"
CLI = "SELECT id, nome FROM clientes ORDER BY id"


# QA-MULTI-001
def test_two_connections_that_agree_exit_0(local2_db, capsys):
    code, body = envelope(["multi", CLI, "-c", "local", "-c", "local2", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "multi"
    assert body["data"]["join_key"] == "id"
    assert body["data"]["all_match"] is True
    assert body["data"]["comparisons"] == [{
        "column": "nome", "total_keys": 3, "equal_count": 3,
        "diff_count": 0, "absent_count": 0, "normalized_count": 0,
        "duplicate_rows": {},
    }]


# QA-MULTI-002
def test_two_connections_that_differ_exit_5(local2_db, capsys):
    code, body = envelope(["multi", PED, "-c", "local", "-c", "local2", "-f", "json"], capsys)
    assert code == 5
    assert body["ok"] is True
    assert body["data"]["all_match"] is False
    assert body["data"]["comparisons"] == [{
        "column": "valor", "total_keys": 4, "equal_count": 3,
        "diff_count": 1, "absent_count": 0, "normalized_count": 0,
        "duplicate_rows": {},
    }]


# QA-MULTI-003
def test_key_overrides_the_join_column_and_is_reported(local2_db, capsys):
    code, body = envelope(
        ["multi", "SELECT id, valor, cliente_id FROM pedidos", "-c", "local", "-c", "local2",
         "--key", "cliente_id", "-f", "json"],
        capsys,
    )
    assert code == 5
    assert body["data"]["join_key"] == "cliente_id"
    assert [c["column"] for c in body["data"]["comparisons"]] == ["id", "valor"]


# QA-MULTI-004
def test_a_key_that_is_not_common_is_validation(local2_db, capsys):
    code, body = envelope(["multi", PED, "-c", "local", "-c", "local2", "--key", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == "Coluna de chave 'nope' nao e comum a todas as conexoes."


# QA-MULTI-005
def test_the_same_connection_twice_is_refused(local_db, capsys):
    code, body = envelope(["multi", PED, "-c", "local", "-c", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == (
        "Conexao 'local' repetida. Informe pelo menos duas conexoes distintas com -c/--connection."
    )


# QA-MULTI-006
def test_one_connection_is_refused(local_db, capsys):
    code, body = envelope(["multi", PED, "-c", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "Informe pelo menos duas conexoes com -c/--connection."


# QA-MULTI-007
def test_a_non_query_is_refused_before_any_connection_opens(local2_db, capsys):
    code, body = envelope(["multi", "DELETE FROM pedidos", "-c", "local", "-c", "local2", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "multi compara resultados de consultas (SELECT ou EXPLAIN); recebido: DELETE."
    for conn in ("local", "local2"):
        code, contagem = envelope(["sql", "SELECT COUNT(*) FROM pedidos", conn, "-f", "json"], capsys)
        assert code == 0 and contagem["data"]["rows"] == [[4]]


# QA-MULTI-008
def test_one_missing_file_is_connection_failed_naming_it(local_db, broken_db, capsys):
    code, body = envelope(["multi", PED, "-c", "local", "-c", "broken", "-f", "json"], capsys)
    assert code == 3
    assert body["error"]["code"] == "connection_failed"
    assert body["error"]["message"] == "Falha na conexao 'broken': unable to open database file"


# QA-MULTI-009
def test_an_unregistered_name_is_not_found(local_db, capsys):
    code, body = envelope(["multi", PED, "-c", "local", "-c", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Conexao 'nope' nao encontrada."


# QA-MULTI-010
def test_export_html_writes_and_keeps_the_verdict(local2_db, tmp_path, capsys):
    code, body = envelope(["multi", PED, "-c", "local", "-c", "local2", "-e", "html", "-f", "json"], capsys)
    assert code == 5
    assert body["data"]["format"] == "html"
    assert body["data"]["join_key"] == "id"
    exported = Path(body["data"]["exported"])
    assert exported.suffix == ".html"
    assert tmp_path in exported.parents
    assert "<table" in exported.read_text(encoding="utf-8")


# QA-MULTI-011
def test_flat_with_html_is_refused(local2_db, capsys):
    code, body = envelope(["multi", PED, "-c", "local", "-c", "local2", "--flat", "-e", "html", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"].startswith("--flat nao tem versao HTML.")


# QA-MULTI-012
def test_a_single_common_column_has_nothing_to_compare(local2_db, capsys):
    code, body = envelope(["multi", "SELECT id FROM pedidos", "-c", "local", "-c", "local2", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == "Coluna 'id' e a unica comum a todas as conexoes; nao ha coluna para comparar."


# QA-MULTI-013
def test_every_failing_connection_is_named(local2_db, capsys):
    code, body = envelope(["multi", "SELECT * FROM nao_existe", "-c", "local", "-c", "local2", "-f", "json"], capsys)
    assert code == 4
    assert body["error"]["code"] == "sql_error"
    assert body["error"]["message"] == (
        "Erro na consulta em 'local': no such table: nao_existe; "
        "Erro na consulta em 'local2': no such table: nao_existe"
    )


# QA-MULTI-014
def test_table_format_prints_the_verdict_with_the_same_exit(local2_db, capsys):
    code, out, err = invoke(["multi", PED, "-c", "local", "-c", "local2"], capsys)
    assert code == 5
    assert "DIVERGENTE" in out and "chave: id" in out
    assert err == ""


POR_CLIENTE = "SELECT cliente_id AS id, valor FROM pedidos ORDER BY id"


# QA-MULTI-015
def test_a_repeated_derived_key_is_reported(local2_db, capsys):
    """`multi` derives its key from whatever columns the connections have
    in common, so an ambiguous one is easier to hit here than in a group
    whose key a person curated."""
    code, out, _ = invoke(
        ["multi", POR_CLIENTE, "-c", "local", "-c", "local2", "-f", "json"], capsys,
    )
    body = json.loads(out)
    assert body["data"]["join_key"] == "id"
    assert body["warnings"] == [
        "Key 'id' has repeated values in 'local': 2 row(s) left out of the comparison.",
        "Key 'id' has repeated values in 'local2': 2 row(s) left out of the comparison.",
    ]
    assert body["data"]["comparisons"][0]["duplicate_rows"] == {"local": 2, "local2": 2}
    assert code == 5


# QA-MULTI-016
def test_a_unique_derived_key_warns_about_nothing(local2_db, capsys):
    code, out, _ = invoke(["multi", CLI, "-c", "local", "-c", "local2", "-f", "json"], capsys)
    assert code == 0
    assert "warnings" not in json.loads(out)


# QA-MULTI-017
def test_a_param_the_statement_never_binds_is_refused(local2_db, capsys):
    code, body = envelope(
        ["multi", CLI, "-c", "local", "-c", "local2", "-p", "naoexiste=1", "-f", "json"], capsys,
    )
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == "O SQL nao usa o parametro 'naoexiste'."


# QA-MULTI-018
def test_a_missing_sql_file_says_so(local2_db, tmp_path, capsys):
    caminho = tmp_path / "nao_existe.sql"
    code, body = envelope(
        ["multi", str(caminho), "-c", "local", "-c", "local2", "-f", "json"], capsys,
    )
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == f"Arquivo '{caminho}' nao encontrado."
