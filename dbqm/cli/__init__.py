"""Command-line interface for non-interactive execution of dbqm operations."""
from __future__ import annotations

import argparse
import difflib
import sys
import textwrap
from typing import Generator

from dbqm._version import __version__
from dbqm.i18n import t
from dbqm.cli.commands import config_cmd as _config_commands
from dbqm.cli.commands import connection as _connection_commands
from dbqm.cli.commands import describe_cli as _describe_cli_commands
from dbqm.cli.commands import oracle_client as _oracle_client_commands
from dbqm.cli.commands import saved as _saved_commands
from dbqm.cli.commands import schema as _schema_commands
from dbqm.cli.commands.config_bundle import cmd_export_config, cmd_import_config
from dbqm.cli.commands.config_cmd import cmd_config
from dbqm.cli.commands.connection import cmd_connection
from dbqm.cli.commands.describe_cli import cmd_describe_cli
from dbqm.cli.commands.inspect import cmd_ddl, cmd_history, cmd_list, cmd_test
from dbqm.cli.commands.mcp_cmd import cmd_mcp
from dbqm.cli.commands.oracle_client import cmd_oracle_client
from dbqm.cli.commands.query import cmd_call, cmd_multi, cmd_run, cmd_run_group, cmd_sql
from dbqm.cli.commands.saved import cmd_group, cmd_query, cmd_template
from dbqm.cli.commands.schema import cmd_describe, cmd_objects, cmd_rows
from dbqm.cli.commands.tui_cmd import cmd_tui
from dbqm.cli.errors import exit_for
from dbqm.cli.params import (
    _add_connection_fields,
    _add_group_fields,
    _add_query_fields,
    _add_template_fields,
    _parse_params,
    resolve_password,
)
from dbqm.cli.render import _print_query_result, console, rich_theme

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

#: Every command, under the heading it is listed beneath. A command in no
#: group -- or in two -- fails `test_every_command_is_in_exactly_one_group`,
#: because the epilog is the only place the help lists commands now and a
#: command missing from it would be invisible.
COMMAND_GROUPS: dict[str, tuple[str, ...]] = {
    "cli.group.run": ("run", "run-group", "multi", "sql", "call"),
    "cli.group.explore": ("test", "objects", "describe", "rows", "ddl"),
    "cli.group.curate": ("list", "connection", "query", "group", "template"),
    "cli.group.configure": ("config", "oracle-client", "export-config", "import-config"),
    "cli.group.interfaces": ("tui", "mcp", "describe-cli", "history"),
}

#: Not catalogue keys, deliberately: a command line is not a sentence. It
#: has to be identical in every language to stay copy-pasteable, and every
#: flag in it is verified by `test_every_example_starts_with_dbqm_and_...`
#: plus the parser itself. A `multi` example needs a query with at least
#: two selected columns: `multi` compares the non-key columns across
#: connections, and a one-column result set leaves nothing to compare, so
#: it always exits 2.
EXAMPLES: tuple[str, ...] = (
    'dbqm connection add prod --type mysql --host db --user app --password-stdin',
    'dbqm sql "SELECT 1" prod -f json',
    'dbqm objects prod --type TABLE',
    'dbqm run monthly-invoices -p month=2026-09 -f json',
    'dbqm multi "SELECT id, total FROM orders" -c prod -c staging',
    'dbqm tui',
)


class _Help(argparse.RawDescriptionHelpFormatter):
    """Keeps the epilog's own layout, and lets it own the command list.

    Without the override argparse prints all 23 commands flat under
    "positional arguments" and the epilog prints them again, grouped.
    """

    def _iter_indented_subactions(
        self, action: argparse.Action,
    ) -> Generator[argparse.Action, None, None]:
        if isinstance(action, argparse._SubParsersAction):
            return
        yield from super()._iter_indented_subactions(action)


def _epilog(subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser]) -> str:
    """The grouped command list, the examples and the pointers.

    Built from the parser that dispatches, never from a second hand-typed
    list: each command's line carries the same `help=` string `--help` and
    `describe-cli` already show, read the way `describe_cli` reads it.
    """
    help_by_name = {
        choice_action.dest: choice_action.help or ""
        for choice_action in subparsers_action._choices_actions
    }
    width = max(len(name) for names in COMMAND_GROUPS.values() for name in names)
    # 4 spaces of indent, the name, two spaces: what is left of 80 columns
    # is the budget for the help string, so no line wraps in a default
    # terminal.
    budget = 80 - (4 + width + 2)
    lines = [t("cli.epilog.commands")]
    for title, names in COMMAND_GROUPS.items():
        lines.append("")
        lines.append(f"  {t(title)}")
        for name in names:
            summary = textwrap.shorten(help_by_name.get(name, ""), width=budget, placeholder=" ...")
            lines.append(f"    {name.ljust(width)}  {summary}")
    lines.extend(["", t("cli.epilog.examples"), ""])
    lines.extend(f"  {example}" for example in EXAMPLES)
    lines.extend(["", t("cli.epilog.exit_codes"), "", t("cli.epilog.learn_more")])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dbqm",
        description=f'{t("cli.description")}\n\n{t("cli.tui_moved")}',
        formatter_class=_Help,
    )
    parser.add_argument("-V", "--version", action="version", version=f"dbqm {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>",
                                       help=t("cli.command_placeholder"))
    # `cmd_describe_cli` (in `dbqm.cli.commands.describe_cli`) walks this same
    # action to describe every command below -- the same reference, so every
    # `add_parser` call from here on is visible to it without a second list.
    _describe_cli_commands._subparsers_action = subparsers

    # --- run ---
    p_run = subparsers.add_parser("run", help=t("help.cmd.run"))
    p_run.add_argument("query", help=t("help.query_rm.name"))
    p_run.add_argument("-c", "--connection", help=t("help.run.connection"))
    p_run.add_argument("-p", "--param", action="append", metavar=t("metavar.key_value"),
                       help=t("help.sql.param"))
    p_run.add_argument("-f", "--format", choices=["table", "json", "csv", "raw"], default="table",
                       help=t("help.run.format"))
    p_run.add_argument("-e", "--export", choices=["csv", "json", "txt", "html"],
                       help=t("help.sql.export"))

    # --- run-group ---
    p_grp = subparsers.add_parser("run-group", help=t("help.cmd.run_group"))
    p_grp.add_argument("group", help=t("help.group_rm.name"))
    p_grp.add_argument("-p", "--param", action="append", metavar=t("metavar.key_value"),
                       help=t("help.grp.param"))
    p_grp.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help=t("help.describe_cli.format"))
    p_grp.add_argument("-e", "--export", choices=["csv", "json", "txt", "html"],
                       help=t("help.multi.export"))
    p_grp.add_argument("--flat", action="store_true",
                       help=t("help.multi.flat"))

    # --- multi ---
    p_multi = subparsers.add_parser(
        "multi", help=t("help.cmd.multi"))
    p_multi.add_argument("sql", help=t("help.multi.sql"))
    p_multi.add_argument("-c", "--connection", action="append", metavar="NOME",
                         help=t("help.multi.connection"))
    p_multi.add_argument("-p", "--param", action="append", metavar=t("metavar.key_value"),
                         help=t("help.sql.param"))
    p_multi.add_argument("--key", help=t("help.multi.key"))
    p_multi.add_argument("-f", "--format", choices=["table", "json"], default="table",
                         help=t("help.describe_cli.format"))
    p_multi.add_argument("-e", "--export", choices=["csv", "json", "txt", "html"],
                         help=t("help.multi.export"))
    p_multi.add_argument("--flat", action="store_true",
                         help=t("help.multi.flat"))

    # --- sql ---
    p_sql = subparsers.add_parser(
        "sql",
        help=t("help.cmd.sql"),
    )
    p_sql.add_argument(
        "sql",
        help=(
            t("help.sql.sql")
        ),
    )
    p_sql.add_argument("connection", help=t("help.conn_rm.name"))
    p_sql.add_argument("-p", "--param", action="append", metavar=t("metavar.key_value"),
                       help=t("help.sql.param"))
    p_sql.add_argument("-f", "--format", choices=["table", "json", "csv", "raw"], default="table",
                       help=t("help.sql.format"))
    p_sql.add_argument("-e", "--export", choices=["csv", "json", "txt", "html"],
                       help=t("help.sql.export"))
    p_sql.add_argument("--commit", action="store_true",
                       help=t("help.sql.commit"))
    p_sql.add_argument("--force-write", dest="force_write", action="store_true",
                       help=t("help.sql.force_write"))
    p_sql.add_argument("--explain", action="store_true",
                       help=(
                           t("help.sql.explain")
                       ))

    # --- call ---
    p_call = subparsers.add_parser(
        "call", help=t("help.cmd.call"))
    p_call.add_argument("routine", help=t("help.call.routine"))
    p_call.add_argument("connection", help=t("help.conn_rm.name"))
    p_call.add_argument("-p", "--param", action="append", metavar=t("metavar.key_value"),
                        help=t("help.call.param"))
    p_call.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help=t("help.describe_cli.format"))
    p_call.add_argument("--commit", action="store_true",
                        help=t("help.call.commit"))

    # --- test ---
    p_test = subparsers.add_parser("test", help=t("help.cmd.test"))
    p_test.add_argument("connection", nargs="?", default="__all__",
                        help=t("help.test.connection"))
    p_test.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help=t("help.describe_cli.format"))

    # --- list ---
    p_list = subparsers.add_parser("list", help=t("help.cmd.list"))
    p_list.add_argument("resource", choices=["connections", "queries", "groups"],
                        help=t("help.list.resource"))
    p_list.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help=t("help.describe_cli.format"))

    # --- ddl ---
    p_ddl = subparsers.add_parser("ddl", help=t("help.cmd.ddl"))
    p_ddl.add_argument("object", help=t("help.describe.object"))
    p_ddl.add_argument("connection", help=t("help.conn_rm.name"))
    p_ddl.add_argument("--stdout", action="store_true",
                       help=t("help.ddl.stdout"))
    p_ddl.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help=t("help.describe_cli.format"))

    # --- objects ---
    p_objects = subparsers.add_parser("objects", help=t("help.cmd.objects"))
    p_objects.add_argument("connection", help=t("help.conn_rm.name"))
    p_objects.add_argument("--type", choices=_schema_commands.OBJECT_TYPES,
                           default="TABLE", help=t("help.objects.type"))
    p_objects.add_argument("-f", "--format", choices=["table", "json"],
                           default="table", help=t("help.describe_cli.format"))

    # --- describe ---
    p_describe = subparsers.add_parser("describe", help=t("help.cmd.describe"))
    p_describe.add_argument("object", help=t("help.describe.object"))
    p_describe.add_argument("connection", help=t("help.conn_rm.name"))
    p_describe.add_argument("-f", "--format", choices=["table", "json"],
                            default="table", help=t("help.describe_cli.format"))

    # --- rows ---
    p_rows = subparsers.add_parser("rows", help=t("help.cmd.rows"))
    p_rows.add_argument("table", help=t("help.rows.table"))
    p_rows.add_argument("connection", help=t("help.conn_rm.name"))
    p_rows.add_argument("--limit", type=int, default=100,
                        help=t("help.rows.limit"))
    p_rows.add_argument("--offset", type=int, default=0,
                        help=t("help.rows.offset"))
    p_rows.add_argument("-f", "--format", choices=["table", "json", "csv", "raw"],
                        default="table", help=t("help.describe_cli.format"))

    # --- export-config ---
    p_exp = subparsers.add_parser("export-config", help=t("help.cmd.export_config"))
    p_exp.add_argument("--password",
                       help=t("help.imp.password"))
    p_exp.add_argument("--password-stdin", action="store_true", dest="password_stdin",
                       help=t("help.imp.password_stdin"))
    p_exp.add_argument("--no-connections", action="store_true", help=t("help.exp.no_connections"))
    p_exp.add_argument("--no-queries", action="store_true", help=t("help.exp.no_queries"))
    p_exp.add_argument("--no-groups", action="store_true", help=t("help.exp.no_groups"))
    p_exp.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help=t("help.describe_cli.format"))

    # --- import-config ---
    p_imp = subparsers.add_parser("import-config", help=t("help.cmd.import_config"))
    p_imp.add_argument("file", help=t("help.imp.file"))
    p_imp.add_argument("--password",
                       help=t("help.imp.password"))
    p_imp.add_argument("--password-stdin", action="store_true", dest="password_stdin",
                       help=t("help.imp.password_stdin"))
    p_imp.add_argument("-f", "--format", choices=["table", "json"], default="table",
                       help=t("help.describe_cli.format"))

    # --- history ---
    p_hist = subparsers.add_parser("history", help=t("help.cmd.history"))
    p_hist.add_argument("-n", "--limit", type=int, help=t("help.hist.limit"))
    p_hist.add_argument("-f", "--format", choices=["table", "json"], default="table",
                        help=t("help.describe_cli.format"))
    p_hist.add_argument("--clear", action="store_true", help=t("help.hist.clear"))

    # --- config ---
    p_config = subparsers.add_parser(
        "config",
        help=t("help.cmd.config"),
    )
    # `cmd_config` (in `dbqm.cli.commands.config_cmd`) reads this back to
    # print the group's own help on a bare `dbqm config`.
    _config_commands._config_parser = p_config
    config_sub = p_config.add_subparsers(dest="subcommand")

    p_config_list = config_sub.add_parser("list", help=t("help.cmd.config.list"))
    p_config_list.add_argument("-f", "--format", choices=["table", "json"],
                               default="table", help=t("help.describe_cli.format"))

    p_config_get = config_sub.add_parser("get", help=t("help.cmd.config.get"))
    p_config_get.add_argument("key", help=t("help.config_set.key"))
    p_config_get.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help=t("help.describe_cli.format"))

    p_config_set = config_sub.add_parser("set", help=t("help.cmd.config.set"))
    p_config_set.add_argument("key", help=t("help.config_set.key"))
    p_config_set.add_argument("value", help=t("help.config_set.value"))
    p_config_set.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help=t("help.describe_cli.format"))

    # --- connection ---
    p_conn = subparsers.add_parser(
        "connection",
        help=t("help.cmd.connection"),
    )
    # `cmd_connection` (in `dbqm.cli.commands.connection`) reads this back to
    # print the group's own help on a bare `dbqm connection`.
    _connection_commands._connection_parser = p_conn
    conn_sub = p_conn.add_subparsers(dest="subcommand")

    p_conn_add = conn_sub.add_parser("add", help=t("help.cmd.conn.add"))
    p_conn_add.add_argument("name", help=t("help.conn_rm.name"))
    _add_connection_fields(p_conn_add)

    p_conn_update = conn_sub.add_parser("update", help=t("help.cmd.conn.update"))
    p_conn_update.add_argument("name", help=t("help.conn_rm.name"))
    _add_connection_fields(p_conn_update)

    p_conn_show = conn_sub.add_parser("show", help=t("help.cmd.conn.show"))
    p_conn_show.add_argument("name", help=t("help.conn_rm.name"))
    p_conn_show.add_argument("-f", "--format", choices=["table", "json"],
                             default="table", help=t("help.describe_cli.format"))

    p_conn_rm = conn_sub.add_parser("rm", help=t("help.cmd.conn.rm"))
    p_conn_rm.add_argument("name", help=t("help.conn_rm.name"))
    p_conn_rm.add_argument("--yes", action="store_true",
                           help=t("help.oc_rm.yes"))
    p_conn_rm.add_argument("-f", "--format", choices=["table", "json"],
                           default="table", help=t("help.describe_cli.format"))

    p_conn_list = conn_sub.add_parser("list", help=t("help.cmd.conn.list"))
    p_conn_list.add_argument("-f", "--format", choices=["table", "json"],
                             default="table", help=t("help.describe_cli.format"))

    # --- query ---
    p_query = subparsers.add_parser(
        "query",
        help=t("help.cmd.query"),
    )
    # `cmd_query` (in `dbqm.cli.commands.saved`) reads this back to print the
    # group's own help on a bare `dbqm query`.
    _saved_commands._query_parser = p_query
    query_sub = p_query.add_subparsers(dest="subcommand")

    p_query_add = query_sub.add_parser("add", help=t("help.cmd.query.add"))
    p_query_add.add_argument("name", help=t("help.query_rm.name"))
    _add_query_fields(p_query_add)

    p_query_update = query_sub.add_parser("update", help=t("help.cmd.query.update"))
    p_query_update.add_argument("name", help=t("help.query_rm.name"))
    _add_query_fields(p_query_update)

    p_query_show = query_sub.add_parser("show", help=t("help.cmd.query.show"))
    p_query_show.add_argument("name", help=t("help.query_rm.name"))
    p_query_show.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help=t("help.describe_cli.format"))

    p_query_rm = query_sub.add_parser("rm", help=t("help.cmd.query.rm"))
    p_query_rm.add_argument("name", help=t("help.query_rm.name"))
    p_query_rm.add_argument("--yes", action="store_true",
                            help=t("help.oc_rm.yes"))
    p_query_rm.add_argument("-f", "--format", choices=["table", "json"],
                            default="table", help=t("help.describe_cli.format"))

    p_query_list = query_sub.add_parser("list", help=t("help.cmd.query.list"))
    p_query_list.add_argument("--connection", help=t("help.query_list.connection"))
    p_query_list.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help=t("help.describe_cli.format"))

    # --- group ---
    p_group = subparsers.add_parser(
        "group",
        help=t("help.cmd.group"),
    )
    # `cmd_group` (in `dbqm.cli.commands.saved`) reads this back to print the
    # group's own help on a bare `dbqm group`.
    _saved_commands._group_parser = p_group
    group_sub = p_group.add_subparsers(dest="subcommand")

    p_group_add = group_sub.add_parser("add", help=t("help.cmd.group.add"))
    p_group_add.add_argument("name", help=t("help.group_rm.name"))
    _add_group_fields(p_group_add)

    p_group_update = group_sub.add_parser("update", help=t("help.cmd.group.update"))
    p_group_update.add_argument("name", help=t("help.group_rm.name"))
    _add_group_fields(p_group_update)

    p_group_show = group_sub.add_parser("show", help=t("help.cmd.group.show"))
    p_group_show.add_argument("name", help=t("help.group_rm.name"))
    p_group_show.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help=t("help.describe_cli.format"))

    p_group_rm = group_sub.add_parser("rm", help=t("help.cmd.group.rm"))
    p_group_rm.add_argument("name", help=t("help.group_rm.name"))
    p_group_rm.add_argument("--yes", action="store_true",
                            help=t("help.oc_rm.yes"))
    p_group_rm.add_argument("-f", "--format", choices=["table", "json"],
                            default="table", help=t("help.describe_cli.format"))

    p_group_list = group_sub.add_parser("list", help=t("help.cmd.group.list"))
    p_group_list.add_argument("-f", "--format", choices=["table", "json"],
                              default="table", help=t("help.describe_cli.format"))

    # --- template ---
    p_template = subparsers.add_parser(
        "template",
        help=t("help.cmd.template"),
    )
    # `cmd_template` (in `dbqm.cli.commands.saved`) reads this back to print
    # the group's own help on a bare `dbqm template`.
    _saved_commands._template_parser = p_template
    template_sub = p_template.add_subparsers(dest="subcommand")

    p_template_add = template_sub.add_parser("add", help=t("help.cmd.template.add"))
    p_template_add.add_argument("name", help=t("help.template_rm.name"))
    _add_template_fields(p_template_add)

    p_template_update = template_sub.add_parser("update", help=t("help.cmd.template.update"))
    p_template_update.add_argument("name", help=t("help.template_rm.name"))
    _add_template_fields(p_template_update)

    p_template_show = template_sub.add_parser("show", help=t("help.cmd.template.show"))
    p_template_show.add_argument("name", help=t("help.template_rm.name"))
    p_template_show.add_argument("-f", "--format", choices=["table", "json"],
                                 default="table", help=t("help.describe_cli.format"))

    p_template_rm = template_sub.add_parser("rm", help=t("help.cmd.template.rm"))
    p_template_rm.add_argument("name", help=t("help.template_rm.name"))
    p_template_rm.add_argument("--yes", action="store_true",
                               help=t("help.oc_rm.yes"))
    p_template_rm.add_argument("-f", "--format", choices=["table", "json"],
                               default="table", help=t("help.describe_cli.format"))

    p_template_list = template_sub.add_parser("list", help=t("help.cmd.template.list"))
    p_template_list.add_argument("-f", "--format", choices=["table", "json"],
                                 default="table", help=t("help.describe_cli.format"))

    # --- oracle-client ---
    p_oc = subparsers.add_parser(
        "oracle-client",
        help=t("help.cmd.oracle_client"),
    )
    # `cmd_oracle_client` (in `dbqm.cli.commands.oracle_client`) reads this
    # back to print the group's own help on a bare `dbqm oracle-client`.
    _oracle_client_commands._oracle_client_parser = p_oc
    oc_sub = p_oc.add_subparsers(dest="subcommand")

    p_oc_list = oc_sub.add_parser("list", help=t("help.cmd.oc.list"))
    p_oc_list.add_argument("-f", "--format", choices=["table", "json"], default="table",
                           help=t("help.describe_cli.format"))

    p_oc_available = oc_sub.add_parser(
        "available", help=t("help.cmd.oc.available"))
    p_oc_available.add_argument("-f", "--format", choices=["table", "json"], default="table",
                                help=t("help.describe_cli.format"))

    p_oc_install = oc_sub.add_parser("install", help=t("help.cmd.oc.install"))
    p_oc_install.add_argument("version", help=t("help.oc_install.version"))
    p_oc_install.add_argument("-f", "--format", choices=["table", "json"], default="table",
                              help=t("help.describe_cli.format"))

    p_oc_rm = oc_sub.add_parser("rm", help=t("help.cmd.oc.rm"))
    p_oc_rm.add_argument("name", help=t("help.oc_rm.name"))
    p_oc_rm.add_argument("--yes", action="store_true",
                         help=t("help.oc_rm.yes"))
    p_oc_rm.add_argument("-f", "--format", choices=["table", "json"], default="table",
                         help=t("help.describe_cli.format"))

    # --- tui ---
    subparsers.add_parser("tui", help=t("help.cmd.tui"))

    # --- mcp ---
    p_mcp = subparsers.add_parser("mcp", help=t("help.cmd.mcp"))
    p_mcp.add_argument("--allow-write", action="store_true", help=t("help.mcp.allow_write"))
    p_mcp.add_argument("--connection", action="append", metavar="NAME",
                       help=t("help.mcp.connection"))

    # --- describe-cli ---
    p_describe_cli = subparsers.add_parser(
        "describe-cli",
        help=t("help.cmd.describe_cli"),
    )
    p_describe_cli.add_argument("-f", "--format", choices=["table", "json"], default="table",
                                help=t("help.describe_cli.format"))

    # After every `add_parser`, so the epilog sees the whole set.
    parser.epilog = _epilog(subparsers)
    return parser


COMMAND_MAP = {
    "run": cmd_run,
    "run-group": cmd_run_group,
    "multi": cmd_multi,
    "sql": cmd_sql,
    "call": cmd_call,
    "test": cmd_test,
    "list": cmd_list,
    "ddl": cmd_ddl,
    "export-config": cmd_export_config,
    "import-config": cmd_import_config,
    "history": cmd_history,
    "config": cmd_config,
    "connection": cmd_connection,
    "query": cmd_query,
    "group": cmd_group,
    "template": cmd_template,
    "oracle-client": cmd_oracle_client,
    "objects": cmd_objects,
    "describe": cmd_describe,
    "rows": cmd_rows,
    "tui": cmd_tui,
    "mcp": cmd_mcp,
    "describe-cli": cmd_describe_cli,
}


def _resolve_the_language() -> None:
    """`DBQM_LANG`, else the stored setting, else English.

    A settings file that cannot be read must not stop a command from running:
    the language is the least important thing about this invocation.
    """
    from dbqm.i18n import resolve_language

    try:
        from dbqm.models.settings import load_settings

        resolve_language(load_settings().language)
    except Exception:
        resolve_language("")


def print_the_help() -> None:
    """`dbqm` with no arguments: the help, on stdout, exit 0.

    Until 3.0.0 the bare invocation opened the interactive interface, and
    a guard had to stop it doing that onto a pipe -- measured, it hung
    until the caller's timeout killed it. The interface moved to
    `dbqm tui` and this prints instead, so there is no console to require
    and nothing to refuse. The notice at the top of the help is what a
    long-time user reads on their first bare `dbqm` after upgrading.
    """
    _resolve_the_language()
    build_parser().print_help()


def _refuse_an_unknown_command(argv: list[str]) -> None:
    """Name the near miss before argparse names all twenty-three choices.

    `dbqm ru` used to answer with the whole choice list, twice. argparse
    learned to suggest in Python 3.14; the floor here is 3.10, so the
    suggestion is made from the same map that dispatches. Silence when
    nothing is close: argparse's list is the right answer then.

    Not routed through `envelope.fail`: the format flag belongs to a
    command, and there is no command here. Plain text on stderr, exit 2,
    stdout empty -- the same shape argparse itself uses.
    """
    if not argv or argv[0].startswith("-") or argv[0] in COMMAND_MAP:
        return
    near = difflib.get_close_matches(argv[0], list(COMMAND_MAP), n=1, cutoff=0.6)
    if not near:
        return
    print(t("cli.unknown_command", name=argv[0], suggestion=near[0]), file=sys.stderr)
    sys.exit(int(exit_for("usage")))


def run_cli(argv: list[str] | None = None) -> bool:
    """Parse CLI args and execute command. Returns True if a command was handled."""
    # Before the parser: `--help` renders flag descriptions, which are
    # user-facing text like any other.
    _resolve_the_language()
    _refuse_an_unknown_command(list(argv) if argv is not None else sys.argv[1:])

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        return False

    handler = COMMAND_MAP.get(args.command)
    if handler:
        handler(args)
        return True

    return False
