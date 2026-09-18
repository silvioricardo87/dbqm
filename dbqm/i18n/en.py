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
    "query.sql_required": 'Give the SQL.',
    "query.name_required": 'Give the query a name.',
    "query.connection_required": 'Choose a connection.',
    "query.connection_not_found": 'Connection "{nome}" not found.',
    "group.name_required": 'Give the group a name.',
    "group.two_queries_required": 'Choose at least 2 queries.',
    "group.query_not_found": 'Query "{nome}" not found.',
    "group.query_repeated": 'Query "{nome}" is repeated. A group compares distinct queries.',
    "group.join_key_required": 'Give the join column.',
    "template.name_required": 'Give the template a name.',
    "template.content_required": 'Template content cannot be empty.',
    "crypto.password_unreadable": "The stored password cannot be read: the key in .dbqm_key does not match it. Write it again with 'dbqm connection update <name> --password-stdin'.",
    "bundle.too_large": 'File exceeds the maximum size of {mb} MB.',
    "driver.not_installed": 'The driver for {banco} ({pacote}) is not installed in this environment ({plataforma}). Install it with `pip install {pacote}` if a wheel exists for your platform; on Windows ARM this driver publishes none and is left out by default.',
    "oracle_client.dir_missing": 'Directory does not exist: {caminho}',
    "oracle_client.not_a_dir": 'That path is not a directory: {caminho}',
    "oracle_client.no_oci_dll": 'oci.dll not found in {caminho} nor in {pasta_bin}: the directory does not look like an Oracle Client.',
    "oracle_client.unusable": 'The Oracle Instant Client configured in dbqm cannot be used. {problema}\nFix the path in Config > Oracle Instant Client.',
    "connection.unknown_db_type": 'Unknown database type: {tipo}',
    "connection.test_ok": 'Connection "{nome}" OK! ({segundos}s)\n  Version: {versao}',
    "connection.connect_failed": 'Could not connect: {erro}',
    "object.invalid_name": 'Invalid object name: {nome}',
    "engine.packages_oracle_only": 'Packages only exist on Oracle. This connection is {tipo}.',
    "engine.sqlite_no_routines": 'SQLite has no stored routines.',
    "engine.packages_and_routines_oracle_only": 'Packages and routines only exist on Oracle. This connection is {tipo}.',
    "engine.routines_oracle_only": 'Stored routines only exist on Oracle. This connection is {tipo}.',
    "read_only.routine_refused": "Connection '{nome}' is read-only and a routine can write whatever the command text says. Clear 'Read-only' on the connection to run it.",
    "read_only.package_compile_refused": "Connection '{nome}' is read-only and compiling a package is always DDL. Clear 'Read-only' on the connection to compile.",
    "sql.select_only": 'Only SELECT statements are allowed.',
    "sql.unsupported_type": 'Unsupported SQL type. Use SELECT, INSERT, UPDATE, DELETE, DDL (CREATE/ALTER/DROP...) or EXPLAIN PLAN.',
    "sql.explain_unsupported": '--explain is not supported for {tipo} yet.',
    "sql.result_sets_returned": '{quantidade} result sets returned; showing the last one.',
    "sql.result_set_shape": '{indice}: {linhas} row(s), columns: {colunas}',
    "group.no_comparable_columns": 'The queries returned no comparable columns.',
    "group.duplicate_key_rows": "Key '{chave}' has repeated values in '{lado}': {linhas} row(s) left out of the comparison.",
    "ddl.object_not_found": "Object '{nome}' not found.",
    "ddl.routine_not_in_body": "Routine '{rotina}' not found in the body of '{pacote}'.",
    "ddl.routine_not_found_or_denied": "Routine '{nome}' not found, or you do not have permission to read it.",
    "ddl.extract_failed": 'Could not extract: {erro}',
    "ddl.extract_failed_object": 'Could not extract {nome}: {erro}',
    "ddl.type_unsupported": "Type '{tipo}' is not supported for extraction.",
    "ddl.engine_unsupported": 'DDL extraction is not supported for {tipo}.',
    "group.summary_column": 'Column: {coluna}',
    "group.summary_equal": '  Equal:        {n}',
    "group.summary_normalized": '  Equal (norm): {n}',
    "group.summary_different": '  Different:    {n}',
    "group.summary_absent": '  Absent:       {n}',
    "sql.explain_takes_the_query_only": 'Pass the query only (no EXPLAIN PLAN FOR) when using --explain.',
    "oracle_client.thin_mode_unsupported": 'Thin mode is not supported by this server (DPY-3015). A compatible Oracle Instant Client is required to use thick mode.\nSet the path in Config > Oracle Instant Client (the same screen downloads and installs one).\nDownload: {url}',
    "oracle_client.thin_mode_detail": '\n\n[!] The Oracle Instant Client did not load - dbqm is in thin mode.\n    Reason: {motivo}\n    Set the path in Config > Oracle Instant Client.',
}
