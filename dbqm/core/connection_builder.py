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
from dbqm.i18n import t
from dbqm.models.connection import Connection, load_connections, save_connections

DB_TYPES: tuple[str, ...] = ("oracle", "sqlserver", "postgresql", "mysql", "sqlite")
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
        errors.append(t("connection.name_required"))

    db_type = _text(values, "db_type")
    if not db_type:
        errors.append(t("connection.type_required"))
    elif db_type not in DB_TYPES:
        errors.append(t("connection.type_invalid", type=db_type,
                        valid=", ".join(DB_TYPES)))

    mode = _text(values, "mode")
    if db_type == "oracle" and mode and mode not in ORACLE_MODES:
        errors.append(t("connection.oracle_mode_invalid", mode=mode,
                        valid=", ".join(ORACLE_MODES)))

    if db_type == "sqlite":
        # The whole configuration is one file. A host, port, user or mode
        # typed for it means the user has misunderstood what they are
        # connecting to, and saying so beats silently ignoring the field.
        if not _text(values, "database"):
            errors.append(t("connection.sqlite_database_required"))
        for campo in ("host", "port", "user", "mode"):
            if _text(values, campo):
                errors.append(t("connection.sqlite_field_unused", field=campo))
        if values.get("password"):
            errors.append(t("connection.sqlite_password_unused"))

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
    elif db_type == "sqlite":
        # One file, nothing else. Host and port stay None so `to_dict` drops
        # them, rather than storing an empty host that reads like a real one.
        fields["database"] = _text(values, "database")
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

    # Keyed on PRESENCE, like `password`: an absent key means "keep what is
    # stored". Without that, `connection update --host x` on a protected
    # connection would quietly unlock it.
    if "read_only" in values:
        read_only = bool(values["read_only"])
    elif existing is not None:
        read_only = existing.read_only
    else:
        read_only = False

    conn = Connection(
        name=_text(values, "name"),
        db_type=db_type,
        user=_text(values, "user"),
        password=password,
        description=_text(values, "description"),
        read_only=read_only,
        **fields,
    )
    if existing is not None:
        conn.created_at = existing.created_at
    return conn


def upsert(values: dict) -> tuple[Connection, bool]:
    """Save `values`, creating or replacing by name. Returns (connection, created).

    This is what the TUI's Salvar button means. The CLI does NOT use it: there,
    `add` on an existing name and `update` on a missing one have to be errors,
    so the command checks first and calls `build` itself.
    """
    connections = load_connections()
    name = _text(values, "name")
    index = next(
        (i for i, c in enumerate(connections) if c.name == name), None
    )
    existing = connections[index] if index is not None else None
    conn = build(values, existing)
    if index is None:
        connections.append(conn)
    else:
        connections[index] = conn
    save_connections(connections)
    return conn, index is None
