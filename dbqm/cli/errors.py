"""Exit codes and the machine tokens that map onto them.

Two axes, deliberately not the same. `ExitCode` is what the shell sees and what
a script branches on, so it stays small and stable. The token in
`error.code` is finer — `usage`, `not_found` and `validation` all exit 2,
because a caller wants one number while a reader wants to know which of the
three happened.

Both live here so they cannot drift apart.

`USAGE` and `CONNECTION_FAILED` were published by the `connection` group in
1.22.0. Their numbers are a contract already in the wild.
"""
from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    #: dbqm itself failed — an unhandled path, not the user's input.
    UNEXPECTED = 1
    #: Bad invocation, a name that does not exist, or a value that fails validation.
    USAGE = 2
    #: The database did not answer.
    CONNECTION_FAILED = 3
    #: The statement reached the driver and was rejected, or failed running.
    SQL_ERROR = 4
    #: A comparison ran to completion and did not match.
    DIVERGENT = 5


ERROR_CODES: dict[str, ExitCode] = {
    "usage": ExitCode.USAGE,
    "not_found": ExitCode.USAGE,
    "validation": ExitCode.USAGE,
    "connection_failed": ExitCode.CONNECTION_FAILED,
    "sql_error": ExitCode.SQL_ERROR,
    "divergent": ExitCode.DIVERGENT,
    "unexpected": ExitCode.UNEXPECTED,
}


def exit_for(code: str) -> ExitCode:
    """The exit code for a machine token.

    Raises `KeyError` on an unknown token, on purpose: an invented code is a
    bug in dbqm, not a condition to degrade around.
    """
    return ERROR_CODES[code]
