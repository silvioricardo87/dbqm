"""A read-only connection is read-only on the SERVER, where the engine allows.

Until now the guard lived in `check_read_only`: dbqm classified the SQL
and refused to send what could write. That stops a mistake typed into
dbqm and nothing else -- a routine that writes internally, a DDL that
commits itself, a second client on the same handle. `get_connection` now
also tells the server, so the refusal comes from the database.

SQLite is the one engine that runs here, so it carries the end-to-end
proof: a write sent STRAIGHT TO THE HANDLE, past every dbqm check, is
refused by the engine. The other engines are proven by what dbqm says to
them, through a handle that records it.
"""
import sqlite3
from dataclasses import replace

import pytest

import dbqm.core.db_manager as dbm
from dbqm.core.db_manager import READ_ONLY_SESSION, get_connection
from dbqm.models.connection import Connection


# ---------------------------------------------------------------------------
# SQLite: the server refuses, not dbqm
# ---------------------------------------------------------------------------

def _sqlite(tmp_path, read_only: bool) -> Connection:
    db = tmp_path / "ro.db"
    # `with sqlite3.connect(...)` commits; it does NOT close. A handle left
    # to the garbage collector raises `ResourceWarning` at some later point,
    # and with `filterwarnings = error` that lands as an unraisable failure
    # on whichever test happens to be running -- it was the config-port
    # fold test, two modules away.
    c = sqlite3.connect(db)
    try:
        c.execute("CREATE TABLE t (id INTEGER)")
        c.commit()
    finally:
        c.close()
    return Connection(name="local", db_type="sqlite", user="", password="",
                      database=str(db), read_only=read_only)


def test_a_write_past_every_dbqm_check_is_refused_by_the_engine(tmp_path, tmp_config_dir):
    """The whole point: no `check_read_only` in sight, and it still fails."""
    db = get_connection(_sqlite(tmp_path, read_only=True))
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("INSERT INTO t VALUES (1)")
        # And reading is untouched.
        assert db.execute("SELECT COUNT(*) FROM t").fetchone() == (0,)
    finally:
        db.close()


def test_a_writable_connection_is_not_pinned(tmp_path, tmp_config_dir):
    db = get_connection(_sqlite(tmp_path, read_only=False))
    try:
        db.execute("INSERT INTO t VALUES (1)")
        assert db.execute("PRAGMA query_only").fetchone() == (0,)
    finally:
        db.close()


def test_force_write_is_the_transient_copy_and_it_writes(tmp_path, tmp_config_dir):
    """`cmd_sql` resolves `--force-write` as `replace(conn, read_only=False)`
    and hands that copy to `core/`. The pin keys on the same flag, so the
    copy that may write is the copy that is not pinned -- no plumbing."""
    conn = _sqlite(tmp_path, read_only=True)
    db = get_connection(replace(conn, read_only=False))
    try:
        db.execute("INSERT INTO t VALUES (1)")
        db.commit()
    finally:
        db.close()
    # The stored connection is still read-only; only the copy was not.
    assert conn.read_only is True


# ---------------------------------------------------------------------------
# The other engines: what dbqm tells them, through a handle that records it
# ---------------------------------------------------------------------------

class _Recorder:
    """A driver handle that remembers every statement it was given."""

    def __init__(self, refuse: bool = False):
        self.executed: list[str] = []
        self.closed = False
        self._refuse = refuse

    def cursor(self):
        return _RecorderCursor(self)

    def close(self):
        self.closed = True


class _RecorderCursor:
    def __init__(self, owner):
        self._owner = owner
        self.closed = False

    def execute(self, sql, *a, **k):
        if self._owner._refuse:
            raise RuntimeError("the server said no")
        self._owner.executed.append(sql)

    def close(self):
        self.closed = True


def _conn(db_type: str, read_only: bool) -> Connection:
    return Connection(name="c", db_type=db_type, host="h", user="u",
                      password="", read_only=read_only)


@pytest.mark.parametrize("db_type", ["postgresql", "mysql", "oracle"])
def test_each_engine_gets_its_own_statement(monkeypatch, db_type):
    handle = _Recorder()
    monkeypatch.setattr(dbm, f"get_{db_type}_connection", lambda conn: handle)
    db = get_connection(_conn(db_type, read_only=True))
    assert db is handle
    assert handle.executed == [READ_ONLY_SESSION[db_type]]


@pytest.mark.parametrize("db_type", ["postgresql", "mysql", "oracle"])
def test_nothing_is_sent_when_the_connection_may_write(monkeypatch, db_type):
    handle = _Recorder()
    monkeypatch.setattr(dbm, f"get_{db_type}_connection", lambda conn: handle)
    get_connection(_conn(db_type, read_only=False))
    assert handle.executed == []


def test_sql_server_has_no_statement_and_is_not_pretended_to(monkeypatch):
    """The asymmetry is real and it is kept visible: SQL Server has no
    session-level read-only, so nothing is sent and the docs say so."""
    assert "sqlserver" not in READ_ONLY_SESSION
    handle = _Recorder()
    monkeypatch.setattr(dbm, "get_sqlserver_connection", lambda conn: handle)
    get_connection(_conn("sqlserver", read_only=True))
    assert handle.executed == []


def test_a_server_that_refuses_the_pin_fails_the_connect_and_closes_the_handle(monkeypatch):
    """A read-only connection the server cannot make read-only is not
    something to fall back from in silence: the error propagates, and the
    handle that was opened is not leaked."""
    handle = _Recorder(refuse=True)
    monkeypatch.setattr(dbm, "get_postgresql_connection", lambda conn: handle)
    with pytest.raises(RuntimeError, match="the server said no"):
        get_connection(_conn("postgresql", read_only=True))
    assert handle.closed is True
