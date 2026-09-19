"""docs/qa/config-portability.md — export-config, then import-config into
a config directory that has been emptied.

"Empty" means the four config files are removed after the export, not a
second fixture: the paths every module reads were pointed at this
directory once, and what matters is that nothing is registered when the
import runs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dbqm.core import paths
from tests.functional.conftest import envelope, invoke

SENHA = "s3gredo"


def _empty_the_config() -> None:
    for arquivo in (paths.CONNECTIONS_FILE, paths.QUERIES_FILE, paths.GROUPS_FILE, paths.TEMPLATES_FILE):
        Path(arquivo).unlink(missing_ok=True)


@pytest.fixture
def curated(local_db, capsys) -> None:
    """`local` plus two queries, one group and one template -- one of
    every kind a bundle carries."""
    for nome in ("qa", "qb"):
        code, _ = envelope(
            ["query", "add", nome, "--connection", "local", "--sql", "SELECT id FROM clientes", "-f", "json"], capsys,
        )
        assert code == 0
    code, _ = envelope(["group", "add", "g1", "--query", "qa", "--query", "qb", "--join-key", "id", "-f", "json"], capsys)
    assert code == 0
    code, _ = envelope(["template", "add", "t1", "--content", "SELECT {{c}}", "-f", "json"], capsys)
    assert code == 0


@pytest.fixture
def bundle(curated, capsys) -> Path:
    code, body = envelope(["export-config", "--password", SENHA, "-f", "json"], capsys)
    assert code == 0
    return Path(body["data"]["path"])


def _names(kind: str, capsys) -> list[str]:
    code, body = envelope([kind, "list", "-f", "json"], capsys)
    assert code == 0
    return [item["name"] for item in body["data"]]


# QA-PORT-001
def test_export_writes_a_bundle(curated, tmp_path, capsys):
    code, body = envelope(["export-config", "--password", SENHA, "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "export-config"
    caminho = Path(body["data"]["path"])
    assert caminho.suffix == ".dbqm"
    assert caminho.is_file()
    assert tmp_path in caminho.parents


# QA-PORT-002
def test_import_into_an_empty_config_round_trips_every_kind_by_name(bundle, capsys):
    _empty_the_config()
    assert _names("connection", capsys) == []
    code, body = envelope(["import-config", str(bundle), "--password", SENHA, "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"connections": 1, "queries": 2, "groups": 1, "templates": 1, "skipped": 0}
    for argv in (
        ["connection", "show", "local"], ["query", "show", "qa"], ["query", "show", "qb"],
        ["group", "show", "g1"], ["template", "show", "t1"],
    ):
        code, body = envelope([*argv, "-f", "json"], capsys)
        assert code == 0, argv
        assert body["data"]["name"] == argv[2]


# QA-PORT-003
def test_an_imported_connection_still_answers(bundle, capsys):
    _empty_the_config()
    code, _ = envelope(["import-config", str(bundle), "--password", SENHA, "-f", "json"], capsys)
    assert code == 0
    code, body = envelope(["sql", "SELECT COUNT(*) FROM clientes", "local", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["rows"] == [[3]]


# QA-PORT-004
def test_import_over_an_existing_config_skips_by_name(bundle, capsys):
    code, body = envelope(["import-config", str(bundle), "--password", SENHA, "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"connections": 0, "queries": 0, "groups": 0, "templates": 0, "skipped": 5}
    assert _names("connection", capsys) == ["local"]
    assert _names("query", capsys) == ["qa", "qb"]
    assert _names("group", capsys) == ["g1"]
    assert _names("template", capsys) == ["t1"]


# QA-PORT-005
def test_a_wrong_password_imports_nothing(bundle, capsys):
    _empty_the_config()
    code, body = envelope(["import-config", str(bundle), "--password", "errada", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"].startswith("Could not import:")
    assert _names("connection", capsys) == []


# QA-PORT-006
def test_a_missing_bundle_is_not_found(tmp_config_dir, tmp_path, capsys):
    caminho = str(tmp_path / "nao.dbqm")
    code, out, err = invoke(["import-config", caminho, "--password", "x", "-f", "json"], capsys)
    assert code == 2
    assert out == ""
    erro = json.loads(err)["error"]
    assert erro["code"] == "not_found"
    assert erro["message"] == f'File "{caminho}" not found.'


# QA-PORT-007
def test_no_connections_leaves_them_out(curated, capsys):
    code, body = envelope(["export-config", "--no-connections", "--password", SENHA, "-f", "json"], capsys)
    assert code == 0
    bundle = body["data"]["path"]
    _empty_the_config()
    code, body = envelope(["import-config", bundle, "--password", SENHA, "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"connections": 0, "queries": 2, "groups": 1, "templates": 1, "skipped": 0}
    assert _names("connection", capsys) == []


# QA-PORT-008
def test_excluding_everything_is_refused(curated, capsys):
    """It wrote a bundle carrying nothing but its own salt and called it a
    successful export."""
    code, body = envelope(
        ["export-config", "--no-connections", "--no-queries", "--no-groups",
         "--password", SENHA, "-f", "json"],
        capsys,
    )
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == (
        "Nothing to export: --no-connections, --no-queries and --no-groups "
        "leave out everything the bundle carries."
    )
    assert not list(Path(paths.EXPORTS_DIR).rglob("*.dbqm"))
