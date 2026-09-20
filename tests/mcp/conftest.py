"""The MCP tests need the `mcp` extra; without it the whole folder skips.

The fixtures are the functional ones: a real SQLite file, a registered
connection, nothing patched."""
from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from tests.functional.conftest import (  # noqa: E402,F401
    broken_db,
    envelope,
    invoke,
    local2_db,
    local_db,
    read_only_db,
    register_connection,
    seed_sqlite,
)
