"""A typo gets the command it probably meant, not the list of all of them."""
from __future__ import annotations

from dbqm.i18n import t
from tests.functional.conftest import invoke


def test_a_near_miss_names_the_command(tmp_config_dir, capsys):
    code, out, err = invoke(["ru"], capsys)
    assert code == 2
    assert out == ""
    assert err.strip() == t("cli.unknown_command", name="ru", suggestion="run")


def test_a_near_miss_of_a_hyphenated_command(tmp_config_dir, capsys):
    code, _, err = invoke(["run-grou"], capsys)
    assert code == 2
    assert "run-group" in err


def test_nothing_close_falls_through_to_argparse(tmp_config_dir, capsys):
    """No guess is better than a wrong guess: argparse still lists the
    choices, which is the right answer when nothing is close."""
    code, _, err = invoke(["zzzzzz"], capsys)
    assert code == 2
    assert "invalid choice" in err


def test_a_real_command_is_untouched(tmp_config_dir, capsys):
    code, _, _ = invoke(["list", "connections", "-f", "json"], capsys)
    assert code == 0


def test_a_subcommand_of_a_group_is_untouched(tmp_config_dir, capsys):
    """`argv[0]` is `connection`, which is in `COMMAND_MAP`: the check
    returns early and never reaches into the subcommand at all."""
    code, _, _ = invoke(["connection", "list", "-f", "json"], capsys)
    assert code == 0


def test_a_flag_is_not_mistaken_for_a_command(tmp_config_dir, capsys):
    """`invoke` folds `SystemExit` into its return value (see
    `tests/functional/conftest.py::invoke`), so `--help` does not raise
    here -- it returns exit 0 with the help text on stdout. The point is
    that the new check never fires for an argument starting with `-`."""
    code, out, err = invoke(["--help"], capsys)
    assert code == 0
    assert out != ""
