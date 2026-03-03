"""Group query execution flow."""
from __future__ import annotations

from rich.console import Console

from dbqm.core.query_engine import execute_query, QueryResult
from dbqm.core.group_engine import build_group_result, GroupResult
from dbqm.core.exporter import (
    export_group_csv, export_group_json, export_group_txt,
    export_group_flat_csv, export_group_flat_json, export_group_flat_txt,
)
from dbqm.models.connection import find_connection
from dbqm.models.query import find_query
from dbqm.models.group import load_groups, find_group
from dbqm.ui.display import (
    show_query_result, show_group_result, show_group_result_flat,
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
                if result.rows:
                    query.apply_column_maps(result.rows, result.columns)
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

        if not _post_group_actions(group_result, param_values, view_mode):
            break


def _post_group_actions(group_result: GroupResult, params: dict, current_view: str = "flat") -> bool:
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
            _show_individual_results(group_result)


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


def _show_individual_results(group_result: GroupResult):
    """Show individual query results from a group execution."""
    choices = [
        {"name": f"{qname} ({r.row_count} registros)", "value": qname}
        for qname, r in group_result.query_results.items()
        if r.success
    ]

    selected = select(message="Qual resultado?", choices=choices)
    if is_esc(selected):
        return

    result = group_result.query_results[selected]
    show_query_result(result)
