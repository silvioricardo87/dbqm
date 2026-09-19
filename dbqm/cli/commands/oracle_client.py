"""`dbqm oracle-client list|available|install|rm`: manage Oracle Instant
Client installations from the CLI -- the one thing the TUI's Oracle Clients
screen (`dbqm.ui.screens.oracle_clients.OracleClientsScreen`) could do that
scripted use could not.

`install` is the only dbqm command that reaches the internet. Progress goes
to stderr under `-f json`, the same routing `cmd_ddl` uses for its
per-object progress, so the envelope on stdout stays parseable; under
`table` it stays dim text next to the human output, same as `cmd_ddl`.

A failed download or extraction is reported as `unexpected` (exit 1) -- the
only place in the whole CLI that uses that code, deliberately: it means
"something dbqm could not handle", not a usage mistake, and no database was
ever involved. An unsupported host (nothing catalogued for the detected
platform) is `usage` (exit 2) instead, naming the platform.

`rm` copies its confirmation from `_connection_rm`/`_query_rm`/`_group_rm`/
`_template_rm`: refuse under a non-terminal stdin instead of hanging on an
unanswerable prompt, and write the prompt to stderr so `input(prompt)`
never puts prose on the stream `-f json`'s envelope owns.
"""
from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from rich.markup import escape
from rich.table import Table

from dbqm.i18n import t
from dbqm.cli import deps
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.render import console
from dbqm.core.oracle_client_installer import ClientPackage, HostKey

# Set by `build_parser` (in `dbqm.cli`) so `cmd_oracle_client` can print the
# group's own help (list/available/install/rm) on a bare `dbqm oracle-client`,
# the same trick `connection._connection_parser` uses.
_oracle_client_parser: argparse.ArgumentParser | None = None


def _fail_or_print(
    args: argparse.Namespace, command: str, code: str, message: str,
) -> NoReturn:
    """Same branch point as `connection._fail_or_print`: `-f json` gets the
    envelope, `table` gets the same Rich failure text -- same exit code
    either way, only what gets printed (and where) differs.
    """
    if args.format == "json":
        fail(command, code, message)
    console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
    sys.exit(int(exit_for(code)))


def _oracle_client_list(args: argparse.Namespace) -> None:
    items = deps.list_installed_clients()

    if args.format == "json":
        data = [
            {"name": c.path.name, "path": str(c.path), "version": c.version}
            for c in items
        ]
        ok("oracle-client.list", data)
        return

    if not items:
        console.print(f'[ds.text.muted]{t("oracle_client.none_installed")}[/ds.text.muted]')
        return

    table = Table(title=t("oracle_client.list_title"))
    table.add_column(t("common.name"))
    table.add_column(t("oracle_client.version_column"))
    table.add_column(t("oracle_client.path_column"))
    for c in items:
        table.add_row(escape(c.path.name), escape(c.version or "-"), escape(str(c.path)))
    console.print(table)


def _available_or_fail(
    args: argparse.Namespace, command: str,
) -> tuple[HostKey, tuple[ClientPackage, ...]]:
    """The catalog entries for the detected host.

    An empty catalog is an unsupported host -- `usage` (exit 2), naming the
    platform via `host_platform_label` rather than leaving a caller to guess
    why an empty list came back.
    """
    host = deps.detect_host_platform()
    packages = deps.available_clients(host)
    if not packages:
        _fail_or_print(
            args, command, "usage",
            t("oracle_client.no_packages", platform=deps.host_platform_label(host)),
        )
    return host, packages


def _oracle_client_available(args: argparse.Namespace) -> None:
    host, packages = _available_or_fail(args, "oracle-client.available")

    if args.format == "json":
        data = [
            {"version": p.version, "os": p.os_key, "arch": p.arch_key,
             "archive_type": p.archive_type, "url": p.url}
            for p in packages
        ]
        ok("oracle-client.available", data)
        return

    table = Table(title=t("oracle_client.available_title",
                          platform=deps.host_platform_label(host)))
    table.add_column(t("oracle_client.version_column"))
    table.add_column(t("oracle_client.arch_column"))
    table.add_column(t("oracle_client.format_column"))
    for p in packages:
        table.add_row(p.version, p.arch_key, p.archive_type)
    console.print(table)


def _oracle_client_install(args: argparse.Namespace) -> None:
    command = "oracle-client.install"
    host, packages = _available_or_fail(args, command)

    pkg = next((p for p in packages if p.version == args.version), None)
    if pkg is None:
        versions = ", ".join(p.version for p in packages)
        _fail_or_print(
            args, command, "usage",
            t("oracle_client.version_unknown", version=args.version,
              platform=deps.host_platform_label(host), available=versions),
        )

    def on_progress(done: int, total: int | None) -> None:
        mb = done // (1024 * 1024)
        text = (t("oracle_client.downloading_pct",
                   percent=(done * 100) // total, mb=mb) if total
                 else t("oracle_client.downloading", mb=mb))
        if args.format == "json":
            print(text, file=sys.stderr)
        else:
            console.print(text, style="dim")

    try:
        path = deps.install_client(pkg, progress=on_progress)
    except FileExistsError as e:
        # A foreseeable precondition -- the target directory is already
        # occupied -- so it is on the user to remove it first, not a dbqm
        # bug. `usage`, not `unexpected`.
        _fail_or_print(args, command, "usage", str(e))
    except Exception as e:
        # A truncated archive, an unreachable CDN, a bad extraction -- from
        # here on it is something dbqm could not handle, not a usage mistake
        # and no database was ever involved. The only `unexpected` (exit 1)
        # this CLI uses, on purpose.
        _fail_or_print(args, command, "unexpected", str(e))

    if args.format == "json":
        ok(command, {"version": pkg.version, "path": str(path)})
        return
    console.print(escape(t("oracle_client.installed", version=pkg.version,
                           path=str(path))))


def _oracle_client_rm(args: argparse.Namespace) -> None:
    command = "oracle-client.rm"
    items = deps.list_installed_clients()
    item = next((c for c in items if c.path.name == args.name), None)
    if item is None:
        _fail_or_print(args, command, "not_found",
                        t("oracle_client.not_found_named", name=args.name))

    if not args.yes:
        # Refuse rather than prompt when there is no terminal: a script that
        # hangs on an unanswerable question is worse than one that fails.
        if not sys.stdin.isatty():
            _fail_or_print(args, command, "usage",
                            t("common.remove_needs_yes"))
        # The prompt goes to stderr: `input(prompt)` writes it to stdout,
        # which would put prose on the stream the envelope owns.
        print(t("oracle_client.confirm_remove", name=args.name), end="",
              file=sys.stderr, flush=True)
        answer = input().strip().lower()
        if answer not in t("common.yes_answers").split(","):
            if args.format == "json":
                ok(command, {"name": args.name, "removed": False})
            else:
                console.print(t("common.cancelled"))
            return

    deps.remove_client(item.path)
    if args.format == "json":
        ok(command, {"name": args.name, "removed": True})
        return
    console.print(escape(t("oracle_client.removed", name=args.name)))


_ORACLE_CLIENT_SUBCOMMANDS = {
    "list": _oracle_client_list,
    "available": _oracle_client_available,
    "install": _oracle_client_install,
    "rm": _oracle_client_rm,
}


def cmd_oracle_client(args: argparse.Namespace) -> None:
    """Manage Oracle Instant Client installations."""
    subcommand = getattr(args, "subcommand", None)
    handler = _ORACLE_CLIENT_SUBCOMMANDS.get(subcommand) if isinstance(subcommand, str) else None
    if handler is None:
        # A bare `dbqm oracle-client` prints the group's own help
        # (list/available/install/rm, with their flags) rather than a
        # one-line reminder -- mirrors `cmd_query`/`cmd_group`/`cmd_template`.
        if _oracle_client_parser is not None:
            _oracle_client_parser.print_help()
        else:
            console.print(
                f'[ds.op.failure]{t("oracle_client.usage")}[/ds.op.failure]'
            )
        sys.exit(int(exit_for("validation")))
    handler(args)
