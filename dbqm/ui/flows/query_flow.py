"""Single query execution flow."""
from __future__ import annotations

from rich.console import Console

from dbqm.core.query_engine import execute_query, QueryResult
from dbqm.core.exporter import export_query_csv, export_query_json, export_query_txt
from dbqm.models.connection import find_connection
from dbqm.models.query import load_queries, find_query
from dbqm.ui.display import show_query_result, show_error, show_warning
from dbqm.ui.helpers import gather_params, pick_format, prompt_open_file
from dbqm.ui.prompts import select, is_esc
from dbqm.ui.display import show_success

console = Console()


def execute_query_flow():
    """Flow to execute a single query."""
    queries = load_queries()
    if not queries:
        show_warning("Nenhuma consulta configurada.")
        return

    choices = [
        {"name": f"{q.name} ({q.connection} -> {q.table})", "value": q.name}
        for q in queries
    ]

    selected = select(message="Selecione a consulta:", choices=choices)
    if is_esc(selected):
        return

    query = find_query(selected)
    if not query:
        show_error("Consulta nao encontrada.")
        return

    conn = find_connection(query.connection)
    if not conn:
        show_error(f'Conexao "{query.connection}" nao encontrada.')
        return

    last_params = {p.name: p.default for p in query.params}
    while True:
        param_values = gather_params(query.params, last_params)
        if param_values is None:
            return

        last_params = dict(param_values)

        with console.status(f"Executando {query.name} em {conn.name}..."):
            result = execute_query(query, conn, param_values)

        if result.success and result.rows:
            query.apply_column_maps(result.rows, result.columns)

        show_query_result(result)

        if not (result.success and result.rows):
            break

        if not _post_result_actions(result, query.table, param_values):
            break


def _post_result_actions(result: QueryResult, table: str = "", params: dict | None = None) -> bool:
    """Actions after displaying a query result. Returns True to re-execute."""
    while True:
        action = select(
            message="Acao:",
            choices=[
                {"name": "💾  Exportar resultado", "value": "export"},
                {"name": "🔄  Reexecutar", "value": "reexec"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            return False
        elif action == "reexec":
            return True
        elif action == "export":
            _export_result(result, table, params)


def _export_result(result: QueryResult, table: str = "", params: dict | None = None):
    """Export a single query result."""
    fmt = pick_format()
    if fmt is None:
        return

    if fmt == "csv":
        path = export_query_csv(result, table, params)
    elif fmt == "json":
        path = export_query_json(result, table, params)
    else:
        path = export_query_txt(result, table, params)

    show_success(f"Exportado: {path}")
    prompt_open_file(path)
