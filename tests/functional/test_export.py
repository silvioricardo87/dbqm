"""docs/qa/export.md — what is inside an exported file, per command and
format. The existence of the file and the exit code are proven where the
command is; these open the file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dbqm.core import paths
from tests.functional.conftest import envelope

ATIVOS = "SELECT id, nome FROM clientes WHERE status = 'A' ORDER BY id"
PED = "SELECT id, valor FROM pedidos ORDER BY id"


@pytest.fixture
def ativos(local_db, capsys) -> str:
    code, _ = envelope(["query", "add", "ativos", "--connection", "local", "--sql", ATIVOS, "-f", "json"], capsys)
    assert code == 0
    return "ativos"


@pytest.fixture
def pedidos(local2_db, capsys) -> str:
    for nome, conn in (("ped_local", "local"), ("ped_local2", "local2")):
        code, _ = envelope(["query", "add", nome, "--connection", conn, "--sql", PED, "-f", "json"], capsys)
        assert code == 0
    code, _ = envelope(
        ["group", "add", "pedidos", "--query", "ped_local", "--query", "ped_local2",
         "--join-key", "id", "--compare-column", "valor", "-f", "json"],
        capsys,
    )
    assert code == 0
    return "pedidos"


def _exported(argv: list[str], capsys, expected_code: int = 0) -> tuple[Path, dict]:
    code, body = envelope([*argv, "-f", "json"], capsys)
    assert code == expected_code, body
    return Path(body["data"]["exported"]), body["data"]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# QA-EXPORT-001
def test_run_csv_has_a_header_and_one_line_per_row(ativos, capsys):
    path, _ = _exported(["run", ativos, "-e", "csv"], capsys)
    linhas = _text(path).splitlines()
    assert linhas[0] == "id,nome"
    assert linhas[1:] == ["1,Ana", "3,Caio"]


# QA-EXPORT-002
def test_run_json_carries_columns_and_rows(ativos, capsys):
    path, _ = _exported(["run", ativos, "-e", "json"], capsys)
    conteudo = json.loads(_text(path))
    plano = json.dumps(conteudo)
    assert "id" in plano and "nome" in plano
    assert "Ana" in plano and "Caio" in plano
    assert "Bia" not in plano


# QA-EXPORT-003
def test_run_txt_carries_the_rows(ativos, capsys):
    path, _ = _exported(["run", ativos, "-e", "txt"], capsys)
    texto = _text(path)
    assert "id" in texto and "nome" in texto
    assert "Ana" in texto and "Caio" in texto


# QA-EXPORT-004
def test_run_html_is_a_table(ativos, capsys):
    path, _ = _exported(["run", ativos, "-e", "html"], capsys)
    html = _text(path)
    assert "<table" in html
    assert "nome" in html and "Ana" in html


# QA-EXPORT-005
@pytest.mark.parametrize("fmt", ["csv", "json", "txt", "html"])
def test_sql_export_content_per_format(local_db, capsys, fmt):
    path, data = _exported(["sql", "SELECT id, nome FROM clientes", "local", "-e", fmt], capsys)
    assert data["format"] == fmt
    texto = _text(path)
    if fmt == "csv":
        assert texto.splitlines()[0] == "id,nome"
    elif fmt == "json":
        assert "Ana" in json.dumps(json.loads(texto))
    elif fmt == "html":
        assert "<table" in texto
    assert "Ana" in texto


# QA-EXPORT-006
@pytest.mark.parametrize("fmt", ["csv", "json", "txt", "html"])
def test_run_group_export_content_per_format(pedidos, capsys, fmt):
    path, data = _exported(["run-group", pedidos, "-e", fmt], capsys, expected_code=5)
    assert data["format"] == fmt
    texto = _text(path)
    if fmt == "json":
        assert "valor" in json.dumps(json.loads(texto))
    elif fmt == "html":
        assert "<table" in texto
    assert "valor" in texto


# QA-EXPORT-007
@pytest.mark.parametrize("fmt", ["csv", "json", "txt"])
def test_run_group_flat_content_per_format(pedidos, capsys, fmt):
    path, _ = _exported(["run-group", pedidos, "--flat", "-e", fmt], capsys, expected_code=5)
    assert path.name.startswith("flat_")
    assert "valor" in _text(path)


# QA-EXPORT-008
@pytest.mark.parametrize("fmt", ["csv", "json", "txt", "html"])
def test_multi_export_content_per_format(local2_db, capsys, fmt):
    path, data = _exported(["multi", PED, "-c", "local", "-c", "local2", "-e", fmt], capsys, expected_code=5)
    assert data["join_key"] == "id"
    texto = _text(path)
    if fmt == "html":
        assert "<table" in texto
    assert "valor" in texto


# QA-EXPORT-009
def test_every_export_lands_under_the_export_dir(ativos, pedidos, capsys):
    caminhos = [
        _exported(["run", ativos, "-e", "csv"], capsys)[0],
        _exported(["sql", "SELECT 1 AS um", "local", "-e", "json"], capsys)[0],
        _exported(["run-group", pedidos, "-e", "html"], capsys, expected_code=5)[0],
        _exported(["multi", PED, "-c", "local", "-c", "local2", "-e", "txt"], capsys, expected_code=5)[0],
    ]
    base = Path(paths.EXPORTS_DIR).resolve()
    for caminho in caminhos:
        assert base in caminho.resolve().parents, caminho
        assert Path.cwd().resolve() not in caminho.resolve().parents
