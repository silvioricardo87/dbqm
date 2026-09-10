"""Connection rules shared by the TUI and the CLI.

Validation, per-engine defaults, password encryption and create-versus-update
semantics used to live inside `ui/screens/connections.py`, where only the TUI
could reach them — `core/` must never import `ui/`. They live here now, and both
front ends call them.

The messages `validate` returns are read by a user, so they are Portuguese
without accents, like every other label in the program. They are *returned*
rather than raised: the TUI shows them with `notify(severity="error")` and the
CLI prints them and picks an exit code, and that choice is not this module's
business.
"""
from __future__ import annotations

DB_TYPES: tuple[str, ...] = ("oracle", "sqlserver", "postgresql", "mysql")
ORACLE_MODES: tuple[str, ...] = ("direct", "tns")

DEFAULT_PORTS: dict[str, int] = {
    "oracle": 1521,
    "sqlserver": 1433,
    "postgresql": 5432,
    "mysql": 3306,
}

# Only where localhost is a real default. Oracle and SQL Server have no
# sensible default host, which is why the TUI pre-fills these two alone.
DEFAULT_HOSTS: dict[str, str] = {
    "postgresql": "localhost",
    "mysql": "localhost",
}


def _text(values: dict, key: str) -> str:
    return str(values.get(key) or "").strip()


def validate(values: dict) -> list[str]:
    """Every problem with `values`, as user-facing messages. Empty means valid.

    Deliberately silent about a blank host, port, user or password: the TUI
    saves all of those blank today, and making the CLI stricter than the UI
    would reject connections the user is allowed to have. `--test` is how you
    find out a connection does not answer.
    """
    errors: list[str] = []

    if not _text(values, "name"):
        errors.append("Nome obrigatorio.")

    db_type = _text(values, "db_type")
    if not db_type:
        errors.append("Selecione o tipo de banco.")
    elif db_type not in DB_TYPES:
        errors.append(
            f"Tipo de banco invalido: {db_type}. "
            f"Use um de: {', '.join(DB_TYPES)}."
        )

    mode = _text(values, "mode")
    if db_type == "oracle" and mode and mode not in ORACLE_MODES:
        errors.append(
            f"Modo Oracle invalido: {mode}. Use um de: {', '.join(ORACLE_MODES)}."
        )

    return errors
