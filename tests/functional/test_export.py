"""docs/qa/export.md — what is inside an exported file, per command and
format. The existence of the file and the exit code are proven where the
command is; these open the file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dbqm.core import paths
from dbqm.models.group import load_groups, save_groups
from tests.functional.conftest import envelope

ACTIVE = "SELECT id, name FROM customers WHERE status = 'A' ORDER BY id"
ORDERS = "SELECT id, value FROM orders ORDER BY id"


@pytest.fixture
def active(local_db, capsys) -> str:
    code, _ = envelope(["query", "add", "ativos", "--connection", "local", "--sql", ACTIVE, "-f", "json"], capsys)
    assert code == 0
    return "ativos"


@pytest.fixture
def orders(local2_db, capsys) -> str:
    for name, conn in (("ped_local", "local"), ("ped_local2", "local2")):
        code, _ = envelope(["query", "add", name, "--connection", conn, "--sql", ORDERS, "-f", "json"], capsys)
        assert code == 0
    code, _ = envelope(
        ["group", "add", "orders", "--query", "ped_local", "--query", "ped_local2",
         "--join-key", "id", "--compare-column", "value", "-f", "json"],
        capsys,
    )
    assert code == 0
    return "orders"


def _exported(argv: list[str], capsys, expected_code: int = 0) -> tuple[Path, dict]:
    code, body = envelope([*argv, "-f", "json"], capsys)
    assert code == expected_code, body
    return Path(body["data"]["exported"]), body["data"]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# QA-EXPORT-001
def test_run_csv_has_a_header_and_one_line_per_row(active, capsys):
    path, _ = _exported(["run", active, "-e", "csv"], capsys)
    lines = _text(path).splitlines()
    assert lines[0] == "id,name"
    assert lines[1:] == ["1,Ana", "3,Caio"]


# QA-EXPORT-002
def test_run_json_carries_columns_and_rows(active, capsys):
    path, _ = _exported(["run", active, "-e", "json"], capsys)
    content = json.loads(_text(path))
    plano = json.dumps(content)
    assert "id" in plano and "name" in plano
    assert "Ana" in plano and "Caio" in plano
    assert "Bia" not in plano


# QA-EXPORT-003
def test_run_txt_carries_the_rows(active, capsys):
    path, _ = _exported(["run", active, "-e", "txt"], capsys)
    text = _text(path)
    assert "id" in text and "name" in text
    assert "Ana" in text and "Caio" in text


# QA-EXPORT-004
def test_run_html_is_a_table(active, capsys):
    path, _ = _exported(["run", active, "-e", "html"], capsys)
    html = _text(path)
    assert "<table" in html
    assert "name" in html and "Ana" in html


# QA-EXPORT-005
@pytest.mark.parametrize("fmt", ["csv", "json", "txt", "html"])
def test_sql_export_content_per_format(local_db, capsys, fmt):
    path, data = _exported(["sql", "SELECT id, name FROM customers", "local", "-e", fmt], capsys)
    assert data["format"] == fmt
    text = _text(path)
    if fmt == "csv":
        assert text.splitlines()[0] == "id,name"
    elif fmt == "json":
        assert "Ana" in json.dumps(json.loads(text))
    elif fmt == "html":
        assert "<table" in text
    assert "Ana" in text


# QA-EXPORT-006
@pytest.mark.parametrize("fmt", ["csv", "json", "txt", "html"])
def test_run_group_export_content_per_format(orders, capsys, fmt):
    path, data = _exported(["run-group", orders, "-e", fmt], capsys, expected_code=5)
    assert data["format"] == fmt
    text = _text(path)
    if fmt == "json":
        assert "value" in json.dumps(json.loads(text))
    elif fmt == "html":
        assert "<table" in text
    assert "value" in text


# QA-EXPORT-007
@pytest.mark.parametrize("fmt", ["csv", "json", "txt"])
def test_run_group_flat_content_per_format(orders, capsys, fmt):
    path, _ = _exported(["run-group", orders, "--flat", "-e", fmt], capsys, expected_code=5)
    assert path.name.startswith("flat_")
    assert "value" in _text(path)


# QA-EXPORT-008
@pytest.mark.parametrize("fmt", ["csv", "json", "txt", "html"])
def test_multi_export_content_per_format(local2_db, capsys, fmt):
    path, data = _exported(["multi", ORDERS, "-c", "local", "-c", "local2", "-e", fmt], capsys, expected_code=5)
    assert data["join_key"] == "id"
    text = _text(path)
    if fmt == "html":
        assert "<table" in text
    assert "value" in text


# QA-EXPORT-009
def test_every_export_lands_under_the_export_dir(active, orders, capsys):
    exported_paths = [
        _exported(["run", active, "-e", "csv"], capsys)[0],
        _exported(["sql", "SELECT 1 AS um", "local", "-e", "json"], capsys)[0],
        _exported(["run-group", orders, "-e", "html"], capsys, expected_code=5)[0],
        _exported(["multi", ORDERS, "-c", "local", "-c", "local2", "-e", "txt"], capsys, expected_code=5)[0],
    ]
    base = Path(paths.EXPORTS_DIR).resolve()
    for path in exported_paths:
        assert base in path.resolve().parents, path
        assert Path.cwd().resolve() not in path.resolve().parents


# QA-EXPORT-010
def test_run_group_export_carries_a_shared_params_default(local2_db, capsys):
    """`shared_params` defaults have no `group add` flag -- only the TUI's
    group-run screen sets them -- so this group is built directly through
    the model, the way `tests/ops/test_compare.py` does for the same fix.

    Before the `ops/compare` refactor, `cmd_run_group` filled the default
    into its own `param_values` and threaded that filled copy through to
    the export; the fix carries it on `Comparison.params` instead. Both the
    exported file name and its JSON body embed parameters, so both are
    checked here.
    """
    filtered = "SELECT id, value FROM orders WHERE id >= :minimum ORDER BY id"
    for name, conn in (("ped_local_f", "local"), ("ped_local2_f", "local2")):
        code, _ = envelope(["query", "add", name, "--connection", conn, "--sql", filtered, "-f", "json"], capsys)
        assert code == 0
    code, _ = envelope(
        ["group", "add", "orders_default", "--query", "ped_local_f", "--query", "ped_local2_f",
         "--join-key", "id", "--compare-column", "value", "-f", "json"],
        capsys,
    )
    assert code == 0

    groups = load_groups()
    for g in groups:
        if g.name == "orders_default":
            g.shared_params = {"minimum": "10"}
    save_groups(groups)

    path, _ = _exported(["run-group", "orders_default", "-e", "json"], capsys, expected_code=5)
    assert "minimum-10" in path.name
    content = json.loads(_text(path))
    assert content["params"] == {"minimum": "10"}
