"""The MCP server: dbqm's operations as tools an AI client calls directly.

A second front end over `dbqm/ops/`, beside the CLI. Every tool calls the
same `ops` function the CLI command of the same name calls, and returns the
CLI's envelope (`{"ok", "command", "data"}` or `{"ok": false, "error":
{"code", "message", "exit"}}`) as structured content, so a consumer of one
already understands the other. `tests/design/test_mcp_parity.py` enforces
the pairing.

Only `server.py` imports the SDK; `options.py` and `policy.py` are plain
Python so `dbqm mcp` can be parsed and refused with a clear message when
the `mcp` extra is not installed. Transport is stdio only: under it stdout
is the protocol channel, and nothing here writes to it.
"""
from __future__ import annotations
