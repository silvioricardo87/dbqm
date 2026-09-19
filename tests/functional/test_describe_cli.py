"""docs/qa/self-description.md — the CLI describing itself. No database:
the parser is the thing under test."""
from __future__ import annotations

import pytest

from dbqm.cli import COMMAND_MAP
from tests.functional.conftest import envelope, invoke

CURATION = ("connection", "query", "group", "template")
VERBS = {"add", "update", "show", "rm", "list"}


@pytest.fixture
def described(tmp_config_dir, capsys) -> dict[str, dict]:
    code, body = envelope(["describe-cli", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "describe-cli"
    return {c["name"]: c for c in body["data"]["commands"]}


# QA-DESC-001
def test_every_dispatched_command_is_described(described):
    assert set(described) == set(COMMAND_MAP)


# QA-DESC-002
def test_the_four_curation_groups_list_their_subcommands_with_arguments(described):
    for group in CURATION:
        subs = {s["name"]: s for s in described[group]["subcommands"]}
        assert VERBS <= set(subs), group
        for verb in VERBS:
            assert subs[verb]["arguments"], f"{group} {verb} has no arguments"
            assert subs[verb]["arguments"][0]["flags"] == ["name"] or verb == "list"


# QA-DESC-003
def test_an_argument_carries_flags_required_and_choices(described):
    args = {tuple(a["flags"]): a for a in described["run"]["arguments"]}
    assert args[("query",)]["required"] is True
    assert ("-c", "--connection") in args
    assert ("-p", "--param") in args
    assert args[("-f", "--format")]["choices"] == ["table", "json", "csv", "raw"]
    assert args[("-f", "--format")]["required"] is False
    assert args[("-e", "--export")]["choices"] == ["csv", "json", "txt", "html"]


# QA-DESC-004
def test_a_leaf_has_no_subcommands_key(described):
    for leaf in ("run", "sql", "multi", "objects", "describe-cli"):
        assert "subcommands" not in described[leaf], leaf
    for group in CURATION:
        assert "subcommands" in described[group]


# QA-DESC-005
def test_table_format_names_every_command(tmp_config_dir, capsys):
    code, out, _ = invoke(["describe-cli"], capsys)
    assert code == 0
    for name in COMMAND_MAP:
        assert name in out, name


# QA-DESC-006
def test_sql_exposes_its_guard_flags(described):
    flags = {flag for a in described["sql"]["arguments"] for flag in a["flags"]}
    assert {"--commit", "--force-write", "--explain"} <= flags
