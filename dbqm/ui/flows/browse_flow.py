"""Table browser flow."""
from __future__ import annotations

from rich.console import Console

from dbqm.core.db_manager import get_connection
from dbqm.core.query_engine import QueryResult
from dbqm.core.table_browser import list_tables, browse_table
from dbqm.core.exporter import export_query_csv, export_query_json, export_query_txt
from dbqm.models.connection import load_connections, find_connection
from dbqm.ui.display import show_error, show_warning, show_info, show_success, show_browse_result
from dbqm.ui.helpers import pick_format, prompt_open_file
from dbqm.ui.prompts import select, text, is_esc

console = Console()

DEFAULT_LIMIT = 100


def browse_tables_flow():
    """Flow to browse database tables with FK resolution."""
    connections = load_connections()
    if not connections:
        show_warning("Nenhuma conexao configurada.")
        return

    conn_choices = [
        {"name": f"{c.name} ({c.db_type} - {c.display_target()})", "value": c.name}
        for c in connections
    ]
    conn_name = select(message="Selecione a conexao:", choices=conn_choices)
    if is_esc(conn_name):
        return

    conn = find_connection(conn_name)
    if not conn:
        show_error("Conexao nao encontrada.")
        return

    db = None
    try:
        with console.status(f"Conectando a {conn.name}..."):
            db = get_connection(conn)

        # List tables
        with console.status("Listando tabelas..."):
            tables = list_tables(db, conn.db_type)

        if not tables:
            show_warning("Nenhuma tabela encontrada.")
            return

        if len(tables) > 200:
            show_info(f"{len(tables)} tabelas encontradas. Use o filtro para refinar.")

        limit = DEFAULT_LIMIT

        while True:
            table_name = _pick_table(tables)
            if table_name is None:
                return

            # Browse loop for selected table
            offset = 0
            while True:
                with console.status(f"Consultando {table_name}..."):
                    result = browse_table(db, conn.db_type, table_name, conn.name, limit, offset)

                show_browse_result(result)

                action = _post_browse_actions(result)

                if action == "back":
                    break
                elif action == "refresh":
                    continue
                elif action == "export":
                    _export_browse_result(result)
                elif action == "limit":
                    new_limit = text(message="Novo limite:", default=str(limit))
                    if not is_esc(new_limit) and new_limit.strip().isdigit():
                        limit = int(new_limit.strip())
                        offset = 0
                elif action == "next":
                    if offset + limit < result.total_count:
                        offset += limit
                elif action == "prev":
                    offset = max(0, offset - limit)

    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def _pick_table(tables: list[str]) -> str | None:
    """Let user pick a table, with text filter support."""
    filter_text = text(message="Filtro (Enter para listar todas):")
    if is_esc(filter_text):
        return None

    if filter_text:
        filtered = [t for t in tables if filter_text.upper() in t.upper()]
    else:
        filtered = tables

    if not filtered:
        show_warning("Nenhuma tabela encontrada com esse filtro.")
        return None

    choices = [{"name": t, "value": t} for t in filtered[:200]]
    if len(filtered) > 200:
        show_info(f"Exibindo as primeiras 200 de {len(filtered)} tabelas.")

    selected = select(message="Selecione a tabela:", choices=choices)
    if is_esc(selected):
        return None

    return selected


def _post_browse_actions(result) -> str:
    """Actions after displaying browse result. Returns action string."""
    choices = [
        {"name": "🔄  Atualizar", "value": "refresh"},
        {"name": "💾  Exportar resultado", "value": "export"},
        {"name": "📏  Alterar limite", "value": "limit"},
    ]

    if result.offset + result.limit < result.total_count:
        choices.append({"name": "➡️   Proxima pagina", "value": "next"})
    if result.offset > 0:
        choices.append({"name": "⬅️   Pagina anterior", "value": "prev"})

    choices.append({"name": "↩️   Voltar (escolher outra tabela)", "value": "back"})

    action = select(message="Acao:", choices=choices)
    if is_esc(action):
        return "back"
    return action


def _export_browse_result(result):
    """Export browse result using standard exporters via QueryResult wrapper."""
    qr = QueryResult(
        query_name=f"Browse: {result.table}",
        connection_name=result.connection_name,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        elapsed=result.elapsed,
    )

    fmt = pick_format()
    if fmt is None:
        return

    if fmt == "csv":
        path = export_query_csv(qr, result.table)
    elif fmt == "json":
        path = export_query_json(qr, result.table)
    else:
        path = export_query_txt(qr, result.table)

    show_success(f"Exportado: {path}")
    prompt_open_file(path)
