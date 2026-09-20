"""What `dbqm mcp` was started with."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServerOptions:
    """The two decisions the person who configures the client makes once.

    Neither can be changed by a tool call: a server started read-only stays
    read-only for its whole life, whatever the agent asks.
    """

    #: `--allow-write`: let a connection's own `read_only` flag decide, as
    #: the CLI does. Without it every connection is forced read-only.
    allow_write: bool = False
    #: `--connection NAME` (repeatable): the only connections the server
    #: exposes. `None` exposes every configured one.
    connections: frozenset[str] | None = None
