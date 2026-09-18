"""Parameter and password helpers shared by the CLI commands."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from typing import Literal, overload

from rich.markup import escape

from dbqm.i18n import t
from dbqm.cli.envelope import fail
from dbqm.cli.errors import exit_for
from dbqm.cli.render import console


def _parse_params(param_list: list[str] | None, args: argparse.Namespace | None = None,
                   command: str = "params") -> dict[str, str]:
    """Parse key=value parameter pairs from CLI arguments.

    `args`/`command` let a malformed `-p` speak the envelope under `-f json`
    the same way every other bad-input path does. Both are optional so the
    direct unit tests (which pass neither) keep exercising `table`'s branch
    unchanged.
    """
    if not param_list:
        return {}
    fmt = getattr(args, "format", "table")
    params = {}
    for p in param_list:
        if "=" not in p:
            message = t("param.invalid", texto=p)
            if fmt == "json":
                fail(command, "usage", message)
            console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
            sys.exit(int(exit_for("usage")))
        key, value = p.split("=", 1)
        params[key.strip()] = value.strip()
    return params


def _add_connection_fields(parser: argparse.ArgumentParser) -> None:
    """The connection fields, shared by `connection add` and `connection update`.

    Nothing here is `required` and `--type` carries no `choices`: a missing or
    invalid value is reported by `connection_builder.validate`, so the user
    meets one error vocabulary instead of argparse's next to dbqm's.
    """
    parser.add_argument("--type", dest="db_type",
                        help=t("help.connection.type"))
    parser.add_argument("--mode", help=t("help.connection.mode"))
    parser.add_argument("--host", help=t("help.connection.host"))
    parser.add_argument("--port", help=t("help.connection.port"))
    parser.add_argument("--service", dest="service_name",
                        help=t("help.connection.service"))
    parser.add_argument("--database", help=t("help.connection.database"))
    parser.add_argument("--tns-path", dest="tns_path",
                        help=t("help.connection.tns_path"))
    parser.add_argument("--tns-name", dest="tns_name",
                        help=t("help.connection.tns_name"))
    parser.add_argument("--user", help=t("help.connection.user"))
    parser.add_argument("--description", help=t("help.connection.description"))
    senha = parser.add_mutually_exclusive_group()
    senha.add_argument("--password-stdin", action="store_true", dest="password_stdin",
                       help=t("help.connection.password_stdin"))
    senha.add_argument("--no-password", action="store_true", dest="no_password",
                       help=t("help.connection.no_password"))
    grupo_ro = parser.add_mutually_exclusive_group()
    grupo_ro.add_argument("--read-only", dest="read_only", action="store_true",
                          default=None,
                          help=t("help.connection.read_only"))
    grupo_ro.add_argument("--no-read-only", dest="read_only",
                          action="store_false",
                          help=t("help.connection.no_read_only"))
    parser.add_argument("--test", action="store_true", dest="test_before_save",
                        help=t("help.connection.test"))
    parser.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help=t("help.template.format"))


def _add_query_fields(parser: argparse.ArgumentParser) -> None:
    """The query fields, shared by `query add` and `query update`.

    Nothing here is `required`: a missing `--sql`/`--connection` is reported
    by `query_builder.validate`, the same way `_add_connection_fields` defers
    to `connection_builder.validate`. `--sql` and `--sql-file` are mutually
    exclusive -- only one way to say what the query runs.
    """
    parser.add_argument("--connection", help=t("help.query.connection"))
    sql_grupo = parser.add_mutually_exclusive_group()
    sql_grupo.add_argument("--sql", help=t("help.query.sql"))
    sql_grupo.add_argument("--sql-file", dest="sql_file",
                           help=t("help.query.sql_file"))
    parser.add_argument("--description", help=t("help.query.description"))
    parser.add_argument("--folder", help=t("help.query.folder"))
    fav_grupo = parser.add_mutually_exclusive_group()
    fav_grupo.add_argument("--favorite", dest="is_favorite", action="store_true",
                           default=None, help=t("help.query.favorite"))
    fav_grupo.add_argument("--no-favorite", dest="is_favorite", action="store_false",
                           help=t("help.query.no_favorite"))
    parser.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help=t("help.template.format"))


def _add_group_fields(parser: argparse.ArgumentParser) -> None:
    """The group fields, shared by `group add` and `group update`.

    Nothing here is `required`: a missing name/queries/join-key is reported
    by `group_builder.validate`, the same way `_add_query_fields` defers to
    `query_builder.validate`. `--query` and `--compare-column` repeat (a
    group needs at least two queries to compare); `--join-key` takes a
    single value -- there is only one join column. Ad-hoc (Multi-Exec)
    groups are out of scope here: `adhoc_sql`/`connections` have no flag,
    but `group_builder.build` still preserves them on an `update` of a
    group that already has them.
    """
    parser.add_argument("--query", dest="query", action="append", metavar=t("metavar.name"),
                        help=t("help.group.query"))
    parser.add_argument("--compare-column", dest="compare_column", action="append",
                        metavar=t("metavar.column"), help=t("help.group.compare_column"))
    parser.add_argument("--join-key", dest="join_key", help=t("help.group.join_key"))
    parser.add_argument("--description", help=t("help.group.description"))
    parser.add_argument("--folder", help=t("help.group.folder"))
    parser.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help=t("help.template.format"))


def _add_template_fields(parser: argparse.ArgumentParser) -> None:
    """The template fields, shared by `template add` and `template update`.

    Nothing here is `required`: a missing name/content is reported by
    `template_builder.validate`, the same way `_add_query_fields` defers to
    `query_builder.validate`. `--content` and `--content-file` are mutually
    exclusive -- only one way to say what the template holds, mirroring
    `--sql`/`--sql-file`.
    """
    content_grupo = parser.add_mutually_exclusive_group()
    content_grupo.add_argument("--content", help=t("help.template.content"))
    content_grupo.add_argument("--content-file", dest="content_file",
                               help=t("help.template.content_file"))
    parser.add_argument("--description", help=t("help.template.description"))
    parser.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help=t("help.template.format"))


@overload
def resolve_password(
    args: argparse.Namespace, env_var: str, prompt: str, *, required: Literal[True],
    use_env: bool = True, command: str = "password",
) -> str: ...
@overload
def resolve_password(
    args: argparse.Namespace, env_var: str, prompt: str, *, required: bool,
    use_env: bool = True, command: str = "password",
) -> str | None: ...
def resolve_password(
    args: argparse.Namespace, env_var: str, prompt: str, *, required: bool,
    use_env: bool = True, command: str = "password",
) -> str | None:
    """The password for this command, from the first source that has one.

    Order: `--password-stdin`, `--password` (only where the command has it),
    then `env_var` — unless `use_env` is False, in which case the environment
    is never consulted. `connection update` passes `use_env=False`: its whole
    contract is that a flag not given on THIS command line changes nothing,
    and an ambient `DBQM_PASSWORD` exported for an unrelated `add` is not
    something the user said on this command; `--password-stdin` or
    `--no-password` remain the only ways to change a stored password.
    `add`, `export-config` and `import-config` keep reading the environment
    (`use_env` defaults to True).

    If none of the sources hit and the value is `required`, prompt — but only
    on a TTY, because `getpass` on a pipe blocks forever, which is exactly how
    an agent hangs. An optional password with no source returns None and
    never prompts.

    An empty read from `--password-stdin` is always an error, regardless of
    `required`: a closed/empty pipe is far more often a broken script than an
    intended empty password, and silently falling through would mean `update`
    clears a stored password without `--no-password` ever being said.

    `command` names the caller for the envelope (`connection.add`,
    `export-config`, ...) so a source-of-password failure under `-f json`
    speaks it too, the same way `_fail_or_print` does elsewhere — `args`
    without a `format` attribute (the direct unit tests) falls back to
    `table`'s unchanged prose-and-`sys.exit` branch.
    """
    from_stdin = getattr(args, "password_stdin", False)
    # `args.password`, where the parser defines it, is a plain string
    # argument (argparse's `--password`). `argparse.Namespace` is untyped
    # so `getattr` returns `Any`; the annotation states what the value
    # actually is instead of letting that `Any` leak into the return type.
    direct: str | None = getattr(args, "password", None)
    fmt = getattr(args, "format", "table")

    if from_stdin and direct:
        message = t("password.both_sources")
        if fmt == "json":
            fail(command, "usage", message)
        console.print(f"[ds.op.failure]{message}[/ds.op.failure]")
        sys.exit(int(exit_for("usage")))

    if from_stdin:
        # Only the line terminator comes off: a password may end in a space.
        value = sys.stdin.readline().rstrip("\r\n")
        if not value:
            # Point at `--no-password` only where it exists. The flag is on
            # the `connection` parsers and not on the config-bundle ones, and
            # the parser itself is the source of that fact — a hand-kept list
            # of which command has which flag is a second truth waiting to
            # drift.
            dica = (
                t("password.no_password_hint")
                if getattr(args, "no_password", None) is not None
                else ""
            )
            message = t("password.empty_on_stdin") + dica
            if fmt == "json":
                fail(command, "usage", message)
            console.print(f"[ds.op.failure]{message}[/ds.op.failure]")
            sys.exit(int(exit_for("usage")))
        return value
    if direct:
        return direct

    if use_env:
        from_env = os.environ.get(env_var)
        if from_env:
            return from_env

    if not required:
        return None

    if sys.stdin.isatty():
        return getpass.getpass(prompt)

    message = t("password.not_given", variavel=env_var)
    if fmt == "json":
        fail(command, "usage", message)
    console.print(f"[ds.op.failure]{message}[/ds.op.failure]")
    sys.exit(int(exit_for("usage")))
