"""Rendering helpers shared by the CLI commands: theme, console, output formatting."""
from __future__ import annotations

import sys
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.theme import Theme as _RichTheme

from dbqm.design.tokens import DARK_TOKENS


def rich_theme() -> _RichTheme:
    """Tema do Rich construido a partir dos design tokens.

    O CLI roda em terminal de fundo desconhecido, entao usa sempre a variante
    escura: ela e a unica cuja legibilidade nao depende de o terminal ser claro.
    Os nomes trocam '-' por '.' para seguir a convencao de estilo do Rich.
    """
    return _RichTheme(
        {chave.replace("-", "."): valor for chave, valor in DARK_TOKENS.items()}
    )


console = Console(theme=rich_theme())


def _materialize(value: Any) -> str:
    """Materialize CLOB/LONG/etc. to plain text for `--format raw`."""
    if value is None:
        return ""
    read = getattr(value, "read", None)
    if callable(read):
        try:
            return str(read())
        except Exception:
            return str(value)
    return str(value)


def _print_query_result(result: Any, output_format: str = "table") -> None:
    """Print query result in the specified format."""
    from dbqm.core.query_engine import QueryResult
    if not result.success:
        console.print(f"[ds.op.failure]Erro: {result.error}[/ds.op.failure]")
        sys.exit(1)

    if output_format == "csv":
        import csv
        import io
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(result.columns)
        writer.writerows(result.rows)
        print(out.getvalue(), end="")
    elif output_format == "raw":
        # No headers, no decoration. CLOB/LONG materialized to text.
        # 1 column → bare value per row. >1 column → tab-separated.
        for row in result.rows:
            values = [_materialize(v) for v in row]
            if len(values) == 1:
                print(values[0])
            else:
                print("\t".join(values))
    else:
        table = Table(show_lines=False)
        for col in result.columns:
            table.add_column(col)
        for row in result.rows:
            table.add_row(*[str(v) if v is not None else "" for v in row])
        console.print(table)
        console.print(f"[dim]{result.row_count} registros em {result.elapsed:.2f}s[/dim]")


def _colored_comparison_lines(comparisons: list) -> list[str]:
    """Linhas de resumo do grupo, coloridas pelo eixo de veredito.

    Reconstroi o texto a partir de `ComparisonResult` (contagens), em vez de
    reimprimir `group_result.summary_lines` cru: assim cada contagem recebe
    o token do eixo a que pertence (igual/diferente/ausente) sem depender do
    texto que o core escreve — core/ permanece livre de markup.
    """
    linhas: list[str] = []
    for comp in comparisons:
        linhas.append(f"Coluna: {comp.column}")
        linhas.append(f"  [ds.verdict.match]Iguais:[/]       {comp.equal_count}")
        if comp.normalized_count > 0:
            linhas.append(f"  [ds.verdict.match]Iguais (norm):[/] {comp.normalized_count}")
        linhas.append(f"  [ds.verdict.diff]Diferentes:[/]   {comp.diff_count}")
        linhas.append(f"  [ds.verdict.absent]Ausentes:[/]     {comp.absent_count}")
    return linhas
