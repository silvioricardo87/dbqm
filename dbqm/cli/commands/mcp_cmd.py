"""`dbqm mcp`: serve the operations to an AI client over stdio.

The SDK is imported inside the command, not at the top: `dbqm.mcp.options`
is plain Python and always importable, `dbqm.mcp.server` needs the `mcp`
extra. Without it the command fails on stderr with the install line and
exit 2 -- the same shape as `driver.not_installed`.

Nothing here writes to stdout: from the moment the server starts, stdout
is the protocol channel, and a stray line would corrupt the first frame.
"""
from __future__ import annotations

import argparse

from dbqm.i18n import t
from dbqm.cli.envelope import fail
from dbqm.mcp.options import ServerOptions


def cmd_mcp(args: argparse.Namespace) -> None:
    try:
        from dbqm.mcp import server as mcp_server
    except ImportError:
        fail("mcp", "usage", t("mcp.not_installed"))
    options = ServerOptions(
        allow_write=bool(args.allow_write),
        connections=frozenset(args.connection) if args.connection else None,
    )
    mcp_server.run(options)
