"""English — the source language.

A key's text here is the definition of what that string means. Every other
catalogue is a translation of this one, and `tests/design/test_i18n_policy.py`
fails when a translation has a key this file does not, or uses a placeholder
this file does not define.

Keys are `area.thing`, lowercase, dotted. The area is where the string is
read from, not where it is stored: `connection.*` is what the user is told
about a connection, whichever module happens to raise it.
"""
from __future__ import annotations

from typing import Final

TEXTOS: Final[dict[str, str]] = {
    # -- connection_builder: what makes a connection valid -----------------
    "connection.name_required": "Name is required.",
    "connection.type_required": "Choose a database type.",
    "connection.type_invalid": "Invalid database type: {tipo}. Use one of: {validos}.",
    "connection.oracle_mode_invalid": "Invalid Oracle mode: {modo}. Use one of: {validos}.",
    "connection.sqlite_database_required": "Give the SQLite database file (or :memory:).",
    "connection.sqlite_field_unused": "SQLite does not use {campo}; leave it blank.",
    "connection.sqlite_password_unused": "SQLite does not use a password; leave it blank.",

    # -- config ------------------------------------------------------------
    "config.language_invalid": 'Language "{idioma}" does not exist. Valid languages: {validos}.',

    # -- read_only: the guard, and why it refused --------------------------
    "read_only.refused": (
        "Connection '{nome}' is read-only. Use --force-write to send it anyway."
    ),
    "read_only.multiple_statements": (
        "Connection '{nome}' is read-only and the command has more than one "
        "statement, which cannot be checked separately. Use --force-write to "
        "send it anyway."
    ),
    "read_only.explain_executes": (
        "Connection '{nome}' is read-only and this EXPLAIN runs the command it "
        "explains. Use --force-write to send it anyway."
    ),
}
