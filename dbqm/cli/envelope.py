"""The single JSON shape every command emits under `-f json`.

    {"ok": true,  "command": "connection.show", "data": {...}}
    {"ok": false, "command": "connection.show",
     "error": {"code": "not_found", "message": "...", "exit": 2}}

Success goes to stdout, failure to stderr, and **stdout stays empty on
failure**. That is the rule the whole contract exists for: before it,
`connection show inexistente -f json` printed Portuguese prose to stdout and a
consumer's `| jq` died on it.

`error.message` stays Portuguese without accents, like every other string a
user reads. `error.code` is the English token a program branches on — never
the sentence, which is free to be reworded.
"""
from __future__ import annotations

import json
import sys
from typing import Any, NoReturn, TextIO

from dbqm.cli.errors import exit_for


def _write(stream: TextIO, payload: dict[str, Any]) -> None:
    json.dump(payload, stream, indent=2, ensure_ascii=False, default=str)
    stream.write("\n")


def ok(command: str, data: Any, *, warnings: list[str] | None = None) -> None:
    """Emit a successful result on stdout.

    `warnings` carries what used to be printed loose next to the result — the
    "N conjuntos de resultado retornados" note, for instance — so it reaches a
    consumer as data instead of as prose mixed into the stream.
    """
    payload: dict[str, Any] = {"ok": True, "command": command, "data": data}
    if warnings:
        payload["warnings"] = warnings
    _write(sys.stdout, payload)


def fail(command: str, code: str, message: str, *, detail: str = "") -> NoReturn:
    """Emit a failure on stderr and exit with the code that token maps to."""
    saida = exit_for(code)
    erro: dict[str, Any] = {"code": code, "message": message, "exit": int(saida)}
    if detail:
        erro["detail"] = detail
    _write(sys.stderr, {"ok": False, "command": command, "error": erro})
    sys.exit(int(saida))
