"""The ops tests run against the functional fixtures: a real SQLite file and
a registered connection, nothing patched. Re-exported here so each module
under `tests/ops/` can ask for `local_db` by name."""
from __future__ import annotations

from tests.functional.conftest import (  # noqa: F401
    broken_db,
    envelope,
    local2_db,
    local_db,
    read_only_db,
    register_connection,
    seed_sqlite,
)
