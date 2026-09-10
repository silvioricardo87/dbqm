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

from dbqm.core.crypto import encrypt
from dbqm.models.connection import Connection

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


def _port(raw: object, db_type: str) -> int | None:
    """The given port, or the engine's default when blank or unparsable.

    Mirrors the TUI's `_int_val`, which also falls back rather than refusing:
    a typo in a port is not worth losing the rest of the form over.
    """
    default = DEFAULT_PORTS.get(db_type)
    text = str(raw or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def build(values: dict, existing: Connection | None = None) -> Connection:
    """A `Connection` from raw form/CLI values. Assumes `validate` passed.

    Never mutates `existing`; it is read for the two things an update must
    carry over — the stored password and `created_at`.
    """
    db_type = _text(values, "db_type")
    mode = _text(values, "mode")
    if db_type == "oracle" and not mode:
        mode = "direct"

    # Start every engine-specific field at None and fill only the ones this
    # engine actually has. `Connection.to_dict()` drops None, so a field that
    # stopped applying disappears from the JSON instead of lingering stale.
    fields: dict = {
        "mode": None, "tns_path": None, "tns_name": None,
        "host": None, "port": None, "service_name": None, "database": None,
    }
    if db_type == "oracle":
        fields["mode"] = mode
        if mode == "tns":
            fields["tns_path"] = _text(values, "tns_path")
            fields["tns_name"] = _text(values, "tns_name")
        else:
            fields["host"] = _text(values, "host") or DEFAULT_HOSTS.get(db_type, "")
            fields["port"] = _port(values.get("port"), db_type)
            fields["service_name"] = _text(values, "service_name")
    else:
        fields["host"] = _text(values, "host") or DEFAULT_HOSTS.get(db_type, "")
        fields["port"] = _port(values.get("port"), db_type)
        fields["database"] = _text(values, "database")

    # Keyed on PRESENCE, not emptiness: an absent key means "keep what is
    # stored", a present one means "set it to this" — which is the only way
    # `connection update --no-password` can clear a password. Not stripped:
    # a password may legitimately end in a space.
    if "password" in values:
        raw_password = values["password"] or ""
        password = encrypt(raw_password) if raw_password else ""
    elif existing is not None:
        password = existing.password
    else:
        password = ""

    conn = Connection(
        name=_text(values, "name"),
        db_type=db_type,
        user=_text(values, "user"),
        password=password,
        description=_text(values, "description"),
        **fields,
    )
    if existing is not None:
        conn.created_at = existing.created_at
        # Carried, not set: the field is dead code today (see B1 in the
        # backlog), and dropping it here would be a silent data loss if it
        # ever starts being used.
        conn.windows_auth = existing.windows_auth
    return conn
