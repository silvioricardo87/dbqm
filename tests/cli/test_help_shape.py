"""What `dbqm --help` has to show, and what it may not.

argparse's default at 23 commands is a 188-character brace blob printed in
the usage line, again under "positional arguments", and again on every
invalid choice. These tests pin the shape that replaced it.
"""
from __future__ import annotations

from itertools import chain

import pytest

from dbqm.cli import COMMAND_GROUPS, COMMAND_MAP, EXAMPLES, build_parser
from dbqm.i18n import t


@pytest.fixture
def help_text(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("COLUMNS", "80")
    return build_parser().format_help()


def test_every_command_is_in_exactly_one_group():
    """A command added without a group would vanish from the epilog, which
    is the only place the help lists commands now."""
    grouped = list(chain.from_iterable(COMMAND_GROUPS.values()))
    assert sorted(grouped) == sorted(COMMAND_MAP)
    assert len(grouped) == len(set(grouped))


def test_the_usage_line_does_not_list_every_command(help_text):
    usage = help_text.split("\n\n")[0]
    assert "run-group" not in usage
    assert "<command>" in usage


def test_the_epilog_lists_every_command_under_its_group_title(help_text):
    for title, names in COMMAND_GROUPS.items():
        assert t(title) in help_text, title
        for name in names:
            assert f"\n    {name} " in help_text or f"\n    {name}  " in help_text, name


def test_a_command_is_listed_with_its_own_help_string(help_text):
    assert t("help.cmd.run") in help_text
    assert t("help.cmd.tui") in help_text


def test_the_help_carries_examples_exit_codes_and_where_to_learn_more(help_text):
    assert t("cli.epilog.examples") in help_text
    for example in EXAMPLES:
        assert example in help_text
    assert t("cli.epilog.exit_codes") in help_text
    assert t("cli.epilog.learn_more") in help_text


def test_the_version_flag_is_documented(help_text):
    """It is answered in `main.py` before argparse ever runs, which is why
    it was invisible here."""
    assert "--version" in help_text and "-V" in help_text


def test_no_line_is_wider_than_eighty_columns(help_text):
    wide = [line for line in help_text.splitlines() if len(line) > 80]
    assert not wide, wide


def test_every_example_starts_with_dbqm_and_names_a_real_command():
    for example in EXAMPLES:
        parts = example.split()
        assert parts[0] == "dbqm", example
        assert parts[1] in COMMAND_MAP, example
