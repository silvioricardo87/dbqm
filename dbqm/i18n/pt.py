"""Portuguese — a translation of `en.py`.

Carries no accents, which is this project's long-standing rule for anything
a user reads on screen: the terminals dbqm runs in are not all trusted to
render them, and a label that renders as mojibake reads worse than one
without a tilde.

Every key here must exist in `en.py`, with the same placeholders. The guard
in `tests/design/test_i18n_policy.py` says so, because a translation that
drifts from the source is how a `{nome}` turns into a literal `{nome}` on
someone's screen.
"""
from __future__ import annotations

from typing import Final

TEXTOS: Final[dict[str, str]] = {
    # -- connection_builder ------------------------------------------------
    "connection.name_required": "Nome obrigatorio.",
    "connection.type_required": "Selecione o tipo de banco.",
    "connection.type_invalid": "Tipo de banco invalido: {tipo}. Use um de: {validos}.",
    "connection.oracle_mode_invalid": "Modo Oracle invalido: {modo}. Use um de: {validos}.",
    "connection.sqlite_database_required": "Informe o arquivo do banco SQLite (ou :memory:).",
    "connection.sqlite_field_unused": "SQLite nao usa {campo}; deixe em branco.",
    "connection.sqlite_password_unused": "SQLite nao usa senha; deixe em branco.",

    # -- config ------------------------------------------------------------
    "config.language_invalid": 'Idioma "{idioma}" nao existe. Idiomas validos: {validos}.',

    # -- read_only ---------------------------------------------------------
    "read_only.refused": (
        "Conexao '{nome}' e somente leitura. Use --force-write para enviar assim mesmo."
    ),
    "read_only.multiple_statements": (
        "Conexao '{nome}' e somente leitura e o comando tem mais de um "
        "statement, que nao podem ser verificados separadamente. Use "
        "--force-write para enviar assim mesmo."
    ),
    "read_only.explain_executes": (
        "Conexao '{nome}' e somente leitura e este EXPLAIN executa o comando "
        "que explica. Use --force-write para enviar assim mesmo."
    ),
}
