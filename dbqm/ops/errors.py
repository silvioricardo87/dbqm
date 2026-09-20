"""The one exception the operations layer raises."""
from __future__ import annotations


class OperationError(Exception):
    """A failure with the machine token the CLI publishes in `error.code`.

    `code` is a key of `dbqm.cli.errors.ERROR_CODES` -- `not_found`,
    `usage`, `validation`, `read_only`, `connection_failed`, `sql_error`,
    `unexpected`. The table itself lives in `cli/` because the exit code is
    the CLI's contract; `tests/design/test_ops_policy.py` asserts every
    token raised here is one the table knows.

    `message` is what a user reads: a catalogue string, or the driver's own
    sentence for a statement it rejected.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
