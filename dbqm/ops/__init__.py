"""The operations layer: what dbqm does, as functions that return values.

One function per thing a front end can ask for -- list a table's rows, run a
saved query, compare a statement across connections. Each takes typed
arguments, returns the `core/` result object, and raises `OperationError`
with the machine token `cli/errors.py` publishes in `error.code`. Nothing
here prints, exits, or reads `argparse`.

The CLI renders what comes back; the MCP server (when the `mcp` extra is
installed) serialises it. Both call the same function, so the two cannot
disagree about what a command does. `ops/` imports `core/` and `models/`
and never `cli/`, `ui/` or `mcp/`.

Modules are imported qualified (`from dbqm.ops import compare`), never
star-imported: the name says which layer a call reaches.
"""
from __future__ import annotations
