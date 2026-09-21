"""What `dbqm --help` has to show, and what it may not.

argparse's default at 23 commands is a 188-character brace blob printed in
the usage line, again under "positional arguments", and again on every
invalid choice. These tests pin the shape that replaced it.
"""
from __future__ import annotations

import shlex
from itertools import chain

import pytest

from dbqm.cli import COMMAND_GROUPS, COMMAND_MAP, EXAMPLES, build_parser
from dbqm.i18n import DEFAULT_LANGUAGE, available_languages, set_language, t


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


def test_the_help_says_where_the_interface_went(help_text):
    """The maintainer asked for this near the top: someone who has typed
    `dbqm` for years must learn the new way without reading a manual."""
    from dbqm.i18n import t

    notice = t("cli.tui_moved")
    assert notice in help_text
    # Above the command list, not buried under it.
    assert help_text.index(notice) < help_text.index(t("cli.epilog.commands"))


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


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_no_line_is_wider_than_eighty_columns(monkeypatch, language):
    """Measured once per language, not just the English the `help_text`
    fixture defaults to: Portuguese sits at exactly 80 columns today, and
    nothing about translating a help string suggests it could not go over.
    """
    monkeypatch.setenv("COLUMNS", "80")
    set_language(language)
    try:
        help_text = build_parser().format_help()
    finally:
        set_language(DEFAULT_LANGUAGE)
    wide = [line for line in help_text.splitlines() if len(line) > 80]
    assert not wide, (language, wide)


def test_every_example_starts_with_dbqm_and_names_a_real_command():
    for example in EXAMPLES:
        parts = example.split()
        assert parts[0] == "dbqm", example
        assert parts[1] in COMMAND_MAP, example


def test_every_example_parses_against_the_real_parser():
    """Catches a malformed flag or a missing required argument -- not the
    semantic case of a `multi` example with a single column, which the
    parser has no way to know is wrong."""
    parser = build_parser()
    for example in EXAMPLES:
        tokens = shlex.split(example)[1:]
        try:
            parser.parse_args(tokens)
        except SystemExit as exc:
            pytest.fail(f"{example!r} did not parse: exit {exc.code}")
