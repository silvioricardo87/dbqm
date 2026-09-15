"""Parameter and password helpers shared by the CLI commands."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from typing import Literal, overload

from rich.markup import escape

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
            message = f"Parametro invalido (use chave=valor): {p}"
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
                        help="Tipo de banco: oracle, sqlserver, postgresql ou mysql")
    parser.add_argument("--mode", help="Modo Oracle: direct ou tns (padrao: direct)")
    parser.add_argument("--host", help="Host do servidor")
    parser.add_argument("--port", help="Porta (padrao: a do tipo de banco)")
    parser.add_argument("--service", dest="service_name",
                        help="Service name (Oracle, modo direct)")
    parser.add_argument("--database", help="Nome do banco (SQL Server/PostgreSQL/MySQL)")
    parser.add_argument("--tns-path", dest="tns_path",
                        help="Caminho do tnsnames.ora (Oracle, modo tns)")
    parser.add_argument("--tns-name", dest="tns_name",
                        help="Entrada do tnsnames.ora (Oracle, modo tns)")
    parser.add_argument("--user", help="Usuario do banco")
    parser.add_argument("--description", help="Anotacao livre sobre a conexao")
    senha = parser.add_mutually_exclusive_group()
    senha.add_argument("--password-stdin", action="store_true", dest="password_stdin",
                       help="Ler a senha de uma linha na entrada padrao")
    senha.add_argument("--no-password", action="store_true", dest="no_password",
                       help="Gravar sem senha (ou, em update, apagar a guardada)")
    grupo_ro = parser.add_mutually_exclusive_group()
    grupo_ro.add_argument("--read-only", dest="read_only", action="store_true",
                          default=None,
                          help="Marcar a conexao como somente leitura")
    grupo_ro.add_argument("--no-read-only", dest="read_only",
                          action="store_false",
                          help="Permitir escrita nesta conexao")
    parser.add_argument("--test", action="store_true", dest="test_before_save",
                        help="Testar a conexao antes de gravar; se falhar, nao grava")
    parser.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")


def _add_query_fields(parser: argparse.ArgumentParser) -> None:
    """The query fields, shared by `query add` and `query update`.

    Nothing here is `required`: a missing `--sql`/`--connection` is reported
    by `query_builder.validate`, the same way `_add_connection_fields` defers
    to `connection_builder.validate`. `--sql` and `--sql-file` are mutually
    exclusive -- only one way to say what the query runs.
    """
    parser.add_argument("--connection", help="Nome da conexao associada")
    sql_grupo = parser.add_mutually_exclusive_group()
    sql_grupo.add_argument("--sql", help="SQL da consulta")
    sql_grupo.add_argument("--sql-file", dest="sql_file",
                           help="Arquivo contendo o SQL da consulta")
    parser.add_argument("--description", help="Anotacao livre sobre a consulta")
    parser.add_argument("--folder", help="Pasta da consulta")
    fav_grupo = parser.add_mutually_exclusive_group()
    fav_grupo.add_argument("--favorite", dest="is_favorite", action="store_true",
                           default=None, help="Marcar como favorita")
    fav_grupo.add_argument("--no-favorite", dest="is_favorite", action="store_false",
                           help="Desmarcar como favorita")
    parser.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help="Formato de saida")


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
        message = "Use --password-stdin ou --password, nao os dois."
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
                " Use --no-password para gravar sem senha."
                if getattr(args, "no_password", None) is not None
                else ""
            )
            message = f"Senha vazia na entrada padrao.{dica}"
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

    message = f"Senha nao informada. Use --password-stdin ou defina {env_var}."
    if fmt == "json":
        fail(command, "usage", message)
    console.print(f"[ds.op.failure]{message}[/ds.op.failure]")
    sys.exit(int(exit_for("usage")))
