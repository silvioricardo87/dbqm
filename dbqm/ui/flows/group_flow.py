"""Group query execution flow."""
from __future__ import annotations

import copy

from rich.console import Console

from dbqm.core.query_engine import execute_query, QueryResult
from dbqm.core.group_engine import build_group_result, GroupResult
from dbqm.core.exporter import (
    export_group_csv, export_group_json, export_group_txt,
    export_group_flat_csv, export_group_flat_json, export_group_flat_txt,
    export_query_csv, export_query_json, export_query_txt,
    export_screenshot,
)
from dbqm.models.connection import find_connection
from dbqm.models.query import find_query
from dbqm.models.group import load_groups, find_group
from dbqm.ui.display import (
    show_query_result, show_group_result, show_group_result_flat,
    show_individual_query_result, build_individual_renderables,
    show_error, show_warning, show_success,
)
from dbqm.ui.helpers import gather_shared_params, pick_format, prompt_open_file
from dbqm.ui.prompts import select, is_esc

console = Console()


def execute_group_flow():
    """Flow to execute a query group."""
    groups = load_groups()
    if not groups:
        show_warning("Nenhum grupo configurado.")
        return

    choices = [
        {"name": f"{g.name} ({', '.join(g.queries)})", "value": g.name}
        for g in groups
    ]

    selected = select(message="Selecione o grupo:", choices=choices)
    if is_esc(selected):
        return

    group = find_group(selected)
    if not group:
        show_error("Grupo nao encontrado.")
        return

    last_params = {k: v.get("default", "") for k, v in group.shared_params.items()}
    while True:
        param_values = gather_shared_params(group.shared_params, last_params)
        if param_values is None:
            return

        last_params = dict(param_values)

        console.print(f"\n[bold]Executando {len(group.queries)} consultas...[/bold]\n")

        query_results = {}
        raw_results = {}  # raw rows (without DE-PARA) for individual view
        query_sql_map = {}  # SQL and params per query
        all_ok = True

        for i, qname in enumerate(group.queries, 1):
            query = find_query(qname)
            if not query:
                show_error(f"[{i}/{len(group.queries)}] Consulta '{qname}' nao encontrada.")
                all_ok = False
                continue

            conn = find_connection(query.connection)
            if not conn:
                show_error(f"[{i}/{len(group.queries)}] Conexao '{query.connection}' nao encontrada.")
                all_ok = False
                continue

            q_params = dict(param_values)
            for p in query.params:
                if p.name not in q_params:
                    q_params[p.name] = p.default

            console.print(f"  [{i}/{len(group.queries)}] {qname} ({conn.name})")
            with console.status(f"    Conectando e executando..."):
                result = execute_query(query, conn, q_params)

            if result.success:
                # Save raw rows before applying DE-PARA
                if result.rows:
                    raw_results[qname] = QueryResult(
                        query_name=result.query_name,
                        connection_name=result.connection_name,
                        columns=list(result.columns),
                        rows=copy.deepcopy(result.rows),
                        row_count=result.row_count,
                        elapsed=result.elapsed,
                    )
                    query.apply_column_maps(result.rows, result.columns)
                else:
                    raw_results[qname] = result
                query_sql_map[qname] = (query.sql, q_params)
                show_success(f"{result.row_count} registros ({result.elapsed:.2f}s)")
            else:
                show_error(f"ERRO - {result.error}")
                all_ok = False

            query_results[qname] = result

        if not query_results:
            show_error("Nenhuma consulta executada com sucesso.")
            return

        group_result = build_group_result(
            group_name=group.name,
            query_results=query_results,
            join_key=group.join_key,
            compare_columns=group.compare_columns,
            column_mapping=group.column_mapping or None,
            normalize=group.normalize or None,
        )

        view_mode = select(
            message="Modo de exibicao:",
            choices=[
                {"name": "📊  Comparativo direto (uma tabela por coluna)", "value": "flat"},
                {"name": "🔑  Detalhado por chave (uma tabela por chave)", "value": "pivoted"},
            ],
        )
        if is_esc(view_mode):
            view_mode = "flat"

        if view_mode == "flat":
            show_group_result_flat(group_result, param_values)
        else:
            show_group_result(group_result, param_values)

        if not _post_group_actions(group_result, param_values, view_mode, raw_results, query_sql_map):
            break


def _post_group_actions(
    group_result: GroupResult,
    params: dict,
    current_view: str = "flat",
    raw_results: dict | None = None,
    query_sql_map: dict | None = None,
) -> bool:
    """Actions after displaying a group result. Returns True to re-execute."""
    while True:
        switch_label = "🔑  Alternar para: Detalhado por chave" if current_view == "flat" \
            else "📊  Alternar para: Comparativo direto"
        action = select(
            message="Acao:",
            choices=[
                {"name": switch_label, "value": "switch_view"},
                {"name": "💾  Exportar resultado completo", "value": "export"},
                {"name": "🔎  Ver resultados individuais", "value": "detail"},
                {"name": "🔄  Reexecutar", "value": "reexec"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            return False
        elif action == "reexec":
            return True
        elif action == "switch_view":
            if current_view == "flat":
                show_group_result(group_result, params)
                current_view = "pivoted"
            else:
                show_group_result_flat(group_result, params)
                current_view = "flat"
        elif action == "export":
            _export_group(group_result, params)
        elif action == "detail":
            _show_individual_results(group_result, raw_results or {}, query_sql_map or {})


def _export_group(group_result: GroupResult, params: dict):
    """Export group result."""
    layout = select(
        message="Layout da exportacao:",
        choices=[
            {"name": "📊  Comparativo direto (flat)", "value": "flat"},
            {"name": "🔑  Detalhado por chave (pivoted)", "value": "pivoted"},
        ],
    )
    if is_esc(layout):
        return

    fmt = pick_format()
    if fmt is None:
        return

    if layout == "flat":
        if fmt == "csv":
            path = export_group_flat_csv(group_result, params)
        elif fmt == "json":
            path = export_group_flat_json(group_result, params)
        else:
            path = export_group_flat_txt(group_result, params)
    else:
        if fmt == "csv":
            path = export_group_csv(group_result, params)
        elif fmt == "json":
            path = export_group_json(group_result, params)
        else:
            path = export_group_txt(group_result, params)

    show_success(f"Exportado: {path}")
    prompt_open_file(path)


def _show_individual_results(
    group_result: GroupResult,
    raw_results: dict[str, QueryResult],
    query_sql_map: dict[str, tuple[str, dict]],
):
    """Show individual query results from a group execution with SQL and raw data."""
    choices = [
        {"name": f"{qname} ({r.row_count} registros)", "value": qname}
        for qname, r in group_result.query_results.items()
        if r.success
    ]

    selected = select(message="Qual resultado?", choices=choices)
    if is_esc(selected):
        return

    # Use raw result (without DE-PARA) if available, otherwise fall back to mapped result
    result = raw_results.get(selected, group_result.query_results[selected])
    sql_info = query_sql_map.get(selected)
    sql = sql_info[0] if sql_info else ""
    q_params = sql_info[1] if sql_info else None

    show_individual_query_result(result, sql, q_params)

    # Post-actions loop
    while True:
        action = select(
            message="Acao:",
            choices=[
                {"name": "💾  Exportar resultado (CSV/JSON/TXT)", "value": "export"},
                {"name": "📸  Captura de tela (PNG)", "value": "screenshot"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            return

        if action == "export":
            fmt = pick_format()
            if fmt is None:
                continue
            if fmt == "csv":
                path = export_query_csv(result, result.query_name, q_params)
            elif fmt == "json":
                path = export_query_json(result, result.query_name, q_params)
            else:
                path = export_query_txt(result, result.query_name, q_params)
            show_success(f"Exportado: {path}")
            prompt_open_file(path)

        elif action == "screenshot":
            renderables = build_individual_renderables(result, sql, q_params)
            path = export_screenshot(renderables, result.query_name, q_params)
            show_success(f"Screenshot salvo: {path}")
            prompt_open_file(path)
