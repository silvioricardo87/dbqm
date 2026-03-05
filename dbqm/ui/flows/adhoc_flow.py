"""Ad-hoc SQL execution flow."""
from __future__ import annotations

import re

from rich.console import Console

from dbqm.core.audit import log_execution
from dbqm.core.query_engine import (
    QueryResult, classify_sql, parse_sql,
    detect_params, replace_literals_with_params, parse_dml_literals,
    execute_adhoc, AdhocResult, generate_sql_text,
)
from dbqm.core.exporter import (
    export_query_csv, export_query_json, export_query_txt, export_sql_file,
)
from dbqm.models.connection import load_connections, find_connection
from dbqm.models.query import Query, QueryParam, load_queries, save_queries
from dbqm.ui.display import show_query_result, show_query_result_vertical, show_error, show_warning, show_success
from dbqm.ui.helpers import gather_params, pick_format, prompt_open_file, read_multiline_sql
from dbqm.ui.prompts import select, text, is_esc

console = Console()


def adhoc_sql_flow():
    """Flow to execute an ad-hoc SQL statement."""
    console.print("\n[bold cyan]── ⌨️  SQL Avulso ──[/bold cyan]")
    console.print("[dim]Cole seu SQL e pressione Enter duas vezes para finalizar:[/dim]\n")

    raw_sql = read_multiline_sql()
    if not raw_sql:
        show_error("Nenhum SQL informado.")
        return

    sql_type = classify_sql(raw_sql)
    if sql_type == "UNKNOWN":
        show_error("Tipo de SQL nao suportado. Use SELECT, INSERT, UPDATE ou DELETE.")
        return

    console.print(f"\n  [bold]Tipo:[/bold] {sql_type}")

    sql = raw_sql
    params: list[QueryParam] = []
    existing_params = detect_params(sql)

    if existing_params:
        console.print(f"  [bold]Parametros detectados:[/bold] {', '.join(f':{p}' for p in existing_params)}")
        for p in existing_params:
            desc = text(message=f"  Descricao de :{p} (Enter para pular):")
            if is_esc(desc):
                return
            params.append(QueryParam(name=p, description=desc or "", default=""))

    if not existing_params:
        if sql_type == "SELECT":
            parsed = parse_sql(raw_sql)
            literals = parsed.get("where_values", {})
            table_name = parsed.get("table", "")
        else:
            literals = parse_dml_literals(raw_sql)
            tbl_match = re.search(
                r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|DELETE)\s+(\S+)", raw_sql, re.IGNORECASE
            )
            table_name = tbl_match.group(1) if tbl_match else ""

        if literals:
            console.print(f"\n  [bold]Valores literais encontrados:[/bold]")
            for col, val in literals.items():
                console.print(f"    {col} = [yellow]'{val}'[/yellow]")

            transform = select(
                message="Transformar valores em parametros?",
                choices=[
                    {"name": "✅  Sim, permitir alterar valores", "value": "yes"},
                    {"name": "❌  Nao, manter valores fixos", "value": "no"},
                ],
            )
            if is_esc(transform):
                return

            if transform == "yes":
                replacements = {}
                for col, val in literals.items():
                    console.print(f"\n  Valor [yellow]'{val}'[/yellow] para [bold]{col}[/bold]")
                    param_name = text(message="  Nome do parametro:", default=col)
                    if is_esc(param_name):
                        return
                    replacements[param_name] = val
                    params.append(QueryParam(name=param_name, description="", default=val))
                sql = replace_literals_with_params(sql, replacements)
    else:
        if sql_type == "SELECT":
            parsed = parse_sql(raw_sql)
            table_name = parsed.get("table", "")
        else:
            tbl_match = re.search(
                r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|DELETE)\s+(\S+)", raw_sql, re.IGNORECASE
            )
            table_name = tbl_match.group(1) if tbl_match else ""

    connections = load_connections()
    if not connections:
        show_error("Nenhuma conexao configurada.")
        return

    conn_choices = [
        {"name": f"{c.name} ({c.db_type} - {c.display_target()})", "value": c.name}
        for c in connections
    ]
    conn_name = select(message="Conexao:", choices=conn_choices)
    if is_esc(conn_name):
        return

    conn = find_connection(conn_name)
    if not conn:
        show_error("Conexao nao encontrada.")
        return

    last_params = {p.name: p.default for p in params}
    while True:
        action = select(
            message="O que deseja fazer?",
            choices=[
                {"name": "▶️   Executar no banco", "value": "execute"},
                {"name": "📝  Gerar SQL (substituir parametros)", "value": "generate"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            return

        param_values = gather_params(params, last_params)
        if param_values is None:
            continue

        last_params = dict(param_values)

        if action == "generate":
            _adhoc_generate_sql(sql, param_values, table_name)
        elif action == "execute":
            if sql_type == "SELECT":
                _adhoc_execute_select(sql, conn, param_values, table_name)
            else:
                _adhoc_execute_dml(sql, sql_type, conn, param_values)

        post = select(
            message="Proximo passo:",
            choices=[
                {"name": "🔄  Executar/gerar novamente", "value": "again"},
                {"name": "💾  Salvar como consulta", "value": "save"},
                {"name": "↩️   Voltar ao menu", "value": "back"},
            ],
        )

        if is_esc(post) or post == "back":
            return
        elif post == "save":
            _adhoc_save_query(sql, sql_type, conn_name, table_name, params)
            return


def _adhoc_generate_sql(sql: str, param_values: dict, table_name: str):
    """Generate final SQL text with parameters replaced."""
    final_sql = generate_sql_text(sql, param_values)
    console.print("\n[bold]SQL Gerado:[/bold]")
    console.print(f"\n[dim]{final_sql}[/dim]\n")

    export_action = select(
        message="Exportar SQL?",
        choices=[
            {"name": "💾  Exportar como .sql", "value": "export"},
            {"name": "↩️   Continuar", "value": "skip"},
        ],
    )
    if not is_esc(export_action) and export_action == "export":
        label = table_name if table_name else "adhoc"
        path = export_sql_file(final_sql, label, param_values)
        show_success(f"Exportado: {path}")
        prompt_open_file(path)


def _adhoc_execute_select(sql: str, conn, param_values: dict, table_name: str):
    """Execute a SELECT ad-hoc and show results."""
    with console.status(f"Executando em {conn.name}..."):
        result = execute_adhoc(sql, conn, param_values)

    if not isinstance(result, AdhocResult):
        result = result[0]

    if result.success:
        qr = QueryResult(
            query_name="SQL Avulso",
            connection_name=result.connection_name,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            elapsed=result.elapsed,
        )
        show_query_result(qr)
        log_execution("adhoc_select", table_name or "adhoc", conn.name, param_values, result.row_count, result.success)

        if result.rows:
            while True:
                post_action = select(
                    message="Resultado:",
                    choices=[
                        {"name": "📐  Visualizacao vertical (uma coluna por linha)", "value": "vertical"},
                        {"name": "💾  Exportar", "value": "export"},
                        {"name": "↩️   Continuar", "value": "skip"},
                    ],
                )
                if is_esc(post_action) or post_action == "skip":
                    break
                elif post_action == "vertical":
                    show_query_result_vertical(qr)
                elif post_action == "export":
                    fmt = pick_format()
                    if fmt is not None:
                        if fmt == "csv":
                            path = export_query_csv(qr, table_name, param_values)
                        elif fmt == "json":
                            path = export_query_json(qr, table_name, param_values)
                        else:
                            path = export_query_txt(qr, table_name, param_values)
                        show_success(f"Exportado: {path}")
                        prompt_open_file(path)
                    break
    else:
        show_error(f"Erro: {result.error}")


def _adhoc_execute_dml(sql: str, sql_type: str, conn, param_values: dict):
    """Execute a DML ad-hoc (INSERT/UPDATE/DELETE) with commit confirmation."""
    with console.status(f"Executando {sql_type} em {conn.name}..."):
        ret = execute_adhoc(sql, conn, param_values)

    if isinstance(ret, tuple):
        result, db = ret
    else:
        result = ret
        db = None

    if not result.success:
        show_error(f"Erro: {result.error}")
        return

    log_execution(f"adhoc_{sql_type.lower()}", "adhoc", conn.name, param_values, result.rows_affected, True)

    console.print(f"\n  [bold]{result.rows_affected}[/bold] linha(s) afetada(s) ({result.elapsed:.2f}s)")

    if db:
        commit_action = select(
            message="Confirmar alteracao?",
            choices=[
                {"name": "✅  COMMIT (efetivar)", "value": "commit"},
                {"name": "❌  ROLLBACK (desfazer)", "value": "rollback"},
            ],
        )

        if is_esc(commit_action) or commit_action == "rollback":
            db.rollback()
            db.close()
            show_warning("ROLLBACK executado. Alteracoes desfeitas.")
        else:
            db.commit()
            db.close()
            show_success("COMMIT executado. Alteracoes efetivadas.")
    else:
        show_warning("Conexao nao disponivel para commit/rollback.")


def _adhoc_save_query(sql: str, sql_type: str, conn_name: str, table_name: str, params: list):
    """Save the ad-hoc SQL as a regular Query."""
    suggested = ""
    if table_name:
        clean_table = table_name.strip('"').strip("[]").split(".")[-1]
        suggested = f"{clean_table} ({conn_name})"
    name = text(message="Nome da consulta:", default=suggested)
    if is_esc(name) or not name:
        show_warning("Nome obrigatorio. Consulta nao salva.")
        return

    existing = load_queries()
    if any(q.name == name for q in existing):
        show_error(f'Consulta "{name}" ja existe.')
        return

    columns = []
    if sql_type == "SELECT":
        parsed = parse_sql(sql)
        columns = parsed.get("columns", [])

    query = Query(
        name=name,
        connection=conn_name,
        sql=sql.strip().rstrip(";"),
        table=table_name,
        params=params,
        columns=columns,
    )

    existing.append(query)
    save_queries(existing)
    show_success(f'Consulta "{name}" salva!')
