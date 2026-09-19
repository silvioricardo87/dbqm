"""Rendering helpers shared by the CLI commands: theme, console, output formatting."""
from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table
from rich.theme import Theme as _RichTheme

from dbqm.i18n import t
from dbqm.core.group_engine import ComparisonResult
from dbqm.design.tokens import DARK_TOKENS


def rich_theme() -> _RichTheme:
    """A Rich theme built from the design tokens.

    The CLI runs in a terminal whose background it cannot know, so it always
    uses the dark variant: it is the only one whose legibility does not depend
    on the terminal being light. The names trade '-' for '.' to follow Rich's
    own style convention.
    """
    return _RichTheme(
        {key.replace("-", "."): value for key, value in DARK_TOKENS.items()}
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
        console.print(
            f"[dim]{t('result.rows_in_seconds', rows=result.row_count, seconds=f'{result.elapsed:.2f}')}[/dim]"
        )


def _colored_comparison_lines(comparisons: list[ComparisonResult]) -> list[str]:
    """The group's summary lines, coloured by the verdict axis.

    Rebuilt from `ComparisonResult` (the counts) rather than reprinting
    `group_result.summary_lines` raw: each count then gets the token of the
    axis it belongs to (equal/different/absent) without depending on the text
    core writes — core/ stays free of markup.
    """
    lines: list[str] = []
    for comp in comparisons:
        lines.append(t("group.summary_column", column=comp.column))
        # The labels differ in length between languages, so the column is
        # aligned from the widest of them rather than from typed-in spaces.
        labels = [t("comparison.equal"), t("comparison.normalized"),
                   t("comparison.different"), t("comparison.absent")]
        width = max(len(r) for r in labels)
        lines.append(f"  [ds.verdict.match]{labels[0]:<{width}}[/] {comp.equal_count}")
        if comp.normalized_count > 0:
            lines.append(
                f"  [ds.verdict.match]{labels[1]:<{width}}[/] {comp.normalized_count}")
        lines.append(f"  [ds.verdict.diff]{labels[2]:<{width}}[/] {comp.diff_count}")
        lines.append(f"  [ds.verdict.absent]{labels[3]:<{width}}[/] {comp.absent_count}")
    return lines
