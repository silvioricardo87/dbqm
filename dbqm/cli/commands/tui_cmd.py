"""`dbqm tui`: open the interactive interface from the CLI's own surface.

`dbqm` with no arguments already opens it. This command exists so the
interface has a NAME: something `--help` lists, `describe-cli` reports, a
launcher pins, and a future default could point at without anyone having
to guess what the bare invocation used to mean.

It refuses under a non-terminal stdin for the reason the four `rm`
confirmations refuse there (`connection.py`, `saved.py`, `oracle_client.py`):
a prompt nobody can answer is worse than a refusal. For a fullscreen app
the same reasoning is stronger -- it hung until something killed it.
"""
from __future__ import annotations

import argparse

from dbqm.i18n import t
from dbqm.cli.envelope import fail
from dbqm.cli.terminal import has_a_console


def cmd_tui(args: argparse.Namespace) -> None:
    """Open the TUI, or refuse if there is no terminal to open it on."""
    if not has_a_console():
        fail("tui", "usage", t("tui.needs_a_terminal"))

    # Imported here, not at module scope: `dbqm.ui` pulls Textual, and no
    # other CLI command pays for that import.
    from dbqm.core.paths import ensure_dirs
    from dbqm.ui.app import DBQMApp

    ensure_dirs()
    DBQMApp().run()
