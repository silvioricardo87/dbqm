"""Single query execution flow."""
from __future__ import annotations

from datetime import datetime

from rich.console import Console

from dbqm.core.query_engine import execute_query, QueryResult
from dbqm.core.exporter import export_query_csv, export_query_json, export_query_txt
from dbqm.models.connection import find_connection
from dbqm.models.query import load_queries, find_query, save_queries
from dbqm.core.audit import log_execution
from dbqm.core.history import record_query_execution
from dbqm.ui.display import show_query_result, show_error, show_warning
from dbqm.ui.helpers import gather_params, pick_format, prompt_open_file
from dbqm.ui.prompts import select, is_esc
from dbqm.ui.display import show_success

console = Console()

PAGE_SIZE = 100


def execute_query_flow():
    """Flow to execute a single query with paginated results."""
    queries = load_queries()
    if not queries:
        show_warning("Nenhuma consulta configurada.")
        return

    queries.sort(key=lambda q: (q.is_favorite, q.last_executed or ""), reverse=True)

    choices = [
        {
            "name": f"{'*' if q.is_favorite else ' '} {q.name} ({q.connection} -> {q.table})",
            "value": q.name,
        }
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

        if result.success:
            query.last_executed = datetime.now().isoformat(timespec="seconds")
            all_queries = load_queries()
            for q in all_queries:
                if q.name == query.name:
                    q.last_executed = query.last_executed
                    break
            save_queries(all_queries)

        record_query_execution(
            query_name=query.name,
            connection_name=conn.name,
            params=param_values,
            row_count=result.row_count,
            elapsed=result.elapsed,
            success=result.success,
            error=result.error,
        )
        log_execution("query", query.name, conn.name, param_values, result.row_count, result.success, result.error)

        if result.success and result.rows:
            query.apply_column_maps(result.rows, result.columns)

        show_query_result(result)

        if not (result.success and result.rows):
            break

        all_rows = result.rows
        offset = 0

        while True:
            if len(all_rows) > PAGE_SIZE:
                page_rows = all_rows[offset:offset + PAGE_SIZE]
                page_result = QueryResult(
                    query_name=result.query_name,
                    connection_name=result.connection_name,
                    columns=result.columns,
                    rows=page_rows,
                    row_count=len(page_rows),
                    elapsed=result.elapsed,
                )
                show_query_result(page_result)
                total_pages = (len(all_rows) + PAGE_SIZE - 1) // PAGE_SIZE
                console.print(
                    f"  [dim]Pagina {offset // PAGE_SIZE + 1} de {total_pages} "
                    f"({len(all_rows)} registros total)[/dim]\n"
                )

            action_choices = [
                {"name": "💾  Exportar resultado completo", "value": "export"},
            ]
            if len(all_rows) > PAGE_SIZE and offset + PAGE_SIZE < len(all_rows):
                action_choices.append({"name": "➡️   Proxima pagina", "value": "next"})
            if offset > 0:
                action_choices.append({"name": "⬅️   Pagina anterior", "value": "prev"})
            action_choices.append({"name": "🔄  Reexecutar", "value": "reexec"})
            action_choices.append({"name": "↩️   Voltar", "value": "back"})

            action = select(message="Acao:", choices=action_choices)

            if is_esc(action) or action == "back":
                return
            elif action == "reexec":
                break
            elif action == "next":
                offset += PAGE_SIZE
            elif action == "prev":
                offset = max(0, offset - PAGE_SIZE)
            elif action == "export":
                _export_result(result, query.table, param_values)


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
