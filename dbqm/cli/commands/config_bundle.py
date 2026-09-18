"""Commands for exporting and importing configuration bundles (.dbqm files)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.markup import escape

from dbqm.cli import deps
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.params import resolve_password
from dbqm.cli.render import console


def cmd_export_config(args: argparse.Namespace) -> None:
    """Export configurations to a .dbqm bundle."""
    # Asked to exclude everything, this still wrote a file: a bundle
    # carrying nothing but its own salt, reported as a successful export.
    # Refused before the password is asked for -- there is nothing to
    # encrypt.
    if args.no_connections and args.no_queries and args.no_groups:
        message = (
            "Nada a exportar: --no-connections, --no-queries e --no-groups "
            "excluem tudo que o bundle carrega."
        )
        if args.format == "json":
            fail("export-config", "usage", message)
        console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
        sys.exit(int(exit_for("usage")))

    password = resolve_password(
        args, "DBQM_BUNDLE_PASSWORD", "Senha para o bundle: ", required=True,
        command="export-config",
    )
    path = deps.export_configs(
        password,
        include_connections=not args.no_connections,
        include_queries=not args.no_queries,
        include_groups=not args.no_groups,
    )
    if args.format == "json":
        ok("export-config", {"path": str(path)})
        return
    console.print(f"Configuracoes exportadas: {path}")


def cmd_import_config(args: argparse.Namespace) -> None:
    """Import configurations from a .dbqm bundle."""
    # Before the password is asked for: a path that does not exist is a
    # `not_found` in the CLI's own words, not the OS's localised error text
    # surfacing through the generic `validation` arm below.
    if not Path(args.file).is_file():
        message = f"Arquivo '{args.file}' nao encontrado."
        if args.format == "json":
            fail("import-config", "not_found", message)
        console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
        sys.exit(int(exit_for("not_found")))
    password = resolve_password(
        args, "DBQM_BUNDLE_PASSWORD", "Senha do bundle: ", required=True,
        command="import-config",
    )
    try:
        summary = deps.import_configs(args.file, password)
    except Exception as e:
        message = f"Erro ao importar: {e}"
        if args.format == "json":
            fail("import-config", "validation", message)
        console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
        sys.exit(int(exit_for("validation")))

    if args.format == "json":
        ok("import-config", summary)
        return
    console.print(f"Importado: {summary['connections']} conexoes, "
                  f"{summary['queries']} consultas, {summary['groups']} grupos "
                  f"({summary['skipped']} duplicados ignorados)")
