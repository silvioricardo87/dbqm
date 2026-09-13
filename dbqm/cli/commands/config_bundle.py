"""Commands for exporting and importing configuration bundles (.dbqm files)."""
from __future__ import annotations

import argparse
import sys

from rich.markup import escape

from dbqm.cli import deps
from dbqm.cli.params import resolve_password
from dbqm.cli.render import console


def cmd_export_config(args: argparse.Namespace) -> None:
    """Export configurations to a .dbqm bundle."""
    password = resolve_password(
        args, "DBQM_BUNDLE_PASSWORD", "Senha para o bundle: ", required=True
    )
    path = deps.export_configs(
        password,
        include_connections=not args.no_connections,
        include_queries=not args.no_queries,
        include_groups=not args.no_groups,
    )
    console.print(f"Configuracoes exportadas: {path}")


def cmd_import_config(args: argparse.Namespace) -> None:
    """Import configurations from a .dbqm bundle."""
    password = resolve_password(
        args, "DBQM_BUNDLE_PASSWORD", "Senha do bundle: ", required=True
    )
    try:
        summary = deps.import_configs(args.file, password)
    except Exception as e:
        console.print(f"[ds.op.failure]Erro ao importar: {escape(str(e))}[/ds.op.failure]")
        sys.exit(1)

    console.print(f"Importado: {summary['connections']} conexoes, "
                  f"{summary['queries']} consultas, {summary['groups']} grupos "
                  f"({summary['skipped']} duplicados ignorados)")
