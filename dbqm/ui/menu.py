"""Main interactive menu."""
from __future__ import annotations

import re

from rich.console import Console

from dbqm.core.query_engine import (
    execute_query, QueryResult, classify_sql, parse_sql,
    detect_params, replace_literals_with_params, parse_dml_literals,
    execute_adhoc, AdhocResult, generate_sql_text,
)
from dbqm.core.group_engine import build_group_result, GroupResult
from dbqm.core.exporter import (
    export_query_csv, export_query_json, export_query_txt,
    export_group_csv, export_group_json, export_group_txt,
    export_group_flat_csv, export_group_flat_json, export_group_flat_txt,
    export_sql_file,
)
from dbqm.models.connection import load_connections, find_connection
from dbqm.models.query import Query, QueryParam, load_queries, save_queries, find_query
from dbqm.models.group import load_groups, find_group
from dbqm.ui.display import (
    clear_screen, show_banner, show_success, show_error, show_warning, show_info,
    show_query_result, show_group_result, show_group_result_flat,
)
from dbqm.core.config_portability import export_configs, import_configs
from dbqm.core.ddl_extractor import extract_ddl, save_extraction, extract_routine, save_routine_extraction
from dbqm.ui.prompts import select, text, secret, checkbox, is_esc
from dbqm.ui.config_wizard import connection_wizard
from dbqm.ui.query_wizard import query_wizard
from dbqm.ui.group_wizard import group_wizard

console = Console()


def main_menu():
    """Main application loop."""
    show_banner()

    # First-run check
    connections = load_connections()
    if not connections:
        show_info("Nenhuma conexao configurada. Vamos configurar a primeira?")
        connection_wizard()

    while True:
        console.print()
        action = select(
            message="Menu principal:",
            choices=[
                {"name": "🔍  Executar consulta", "value": "exec_query"},
                {"name": "📊  Executar grupo de consultas", "value": "exec_group"},
                {"name": "⌨️   Executar SQL avulso", "value": "adhoc_sql"},
                {"name": "🏗️   Extrair DDL de objeto", "value": "extract_ddl"},
                {"name": "⚙️   Configuracoes", "value": "config"},
                {"name": "🚪  Sair", "value": "exit"},
            ],
        )

        if is_esc(action) or action == "exit":
            clear_screen()
            console.print("[dim]Ate logo![/dim]\n")
            break
        elif action == "config":
            _config_menu()
        elif action == "extract_ddl":
            _extract_ddl_flow()
        elif action == "exec_query":
            _execute_query_flow()
        elif action == "exec_group":
            _execute_group_flow()
        elif action == "adhoc_sql":
            _adhoc_sql_flow()


def _config_menu():
    """Configuration sub-menu."""
    while True:
        action = select(
            message="Configuracoes:",
            choices=[
                {"name": "🔌  Conexoes", "value": "config_conn"},
                {"name": "📝  Consultas", "value": "config_query"},
                {"name": "📁  Grupos", "value": "config_group"},
                {"name": "📦  Exportar/Importar", "value": "portability"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            break
        elif action == "config_conn":
            connection_wizard()
        elif action == "config_query":
            query_wizard()
        elif action == "config_group":
            group_wizard()
        elif action == "portability":
            _portability_flow()


def _execute_query_flow():
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

    # Re-execution loop: gather params, execute, show result, repeat if requested
    last_params = {p.name: p.default for p in query.params}
    while True:
        # Gather parameters (using last values as defaults for re-execution)
        param_values = {}
        cancelled = False
        for p in query.params:
            prompt = f"{p.name}"
            if p.description:
                prompt += f" ({p.description})"
            val = text(message=f"  {prompt}:", default=last_params.get(p.name, p.default))
            if is_esc(val):
                cancelled = True
                break
            param_values[p.name] = val

        if cancelled:
            return

        last_params = dict(param_values)

        # Execute
        with console.status(f"Executando {query.name} em {conn.name}..."):
            result = execute_query(query, conn, param_values)

        if result.success and result.rows:
            query.apply_column_maps(result.rows, result.columns)

        show_query_result(result)

        if not (result.success and result.rows):
            break

        # Post-result actions (returns "reexec" to loop, None to exit)
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
    fmt = select(
        message="Formato:",
        choices=[
            {"name": "📄  CSV", "value": "csv"},
            {"name": "📋  JSON", "value": "json"},
            {"name": "📃  TXT (tabela formatada)", "value": "txt"},
        ],
    )

    if is_esc(fmt):
        return

    if fmt == "csv":
        path = export_query_csv(result, table, params)
    elif fmt == "json":
        path = export_query_json(result, table, params)
    else:
        path = export_query_txt(result, table, params)

    show_success(f"Exportado: {path}")


def _execute_group_flow():
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

    # Re-execution loop
    last_params = {k: v.get("default", "") for k, v in group.shared_params.items()}
    while True:
        # Gather shared params (using last values as defaults for re-execution)
        param_values = {}
        cancelled = False
        for param_name, param_info in group.shared_params.items():
            desc = param_info.get("description", "")
            prompt = f"{param_name}"
            if desc:
                prompt += f" ({desc})"
            val = text(message=f"  {prompt}:", default=last_params.get(param_name, ""))
            if is_esc(val):
                cancelled = True
                break
            param_values[param_name] = val

        if cancelled:
            return

        last_params = dict(param_values)

        # Execute each query in sequence
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

            # Build params for this query (shared + query-specific defaults)
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

        # Build comparison
        group_result = build_group_result(
            group_name=group.name,
            query_results=query_results,
            join_key=group.join_key,
            compare_columns=group.compare_columns,
            column_mapping=group.column_mapping or None,
            normalize=group.normalize or None,
        )

        # Choose display mode
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

        # Post-group actions (returns True to re-execute, False to exit)
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

    fmt = select(
        message="Formato:",
        choices=[
            {"name": "📄  CSV", "value": "csv"},
            {"name": "📋  JSON", "value": "json"},
            {"name": "📃  TXT (tabela formatada)", "value": "txt"},
        ],
    )

    if is_esc(fmt):
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


def _extract_ddl_flow():
    """Flow to extract DDL from an Oracle object."""
    connections = load_connections()
    oracle_conns = [c for c in connections if c.db_type == "oracle"]
    if not oracle_conns:
        show_warning("Nenhuma conexao Oracle configurada.")
        return

    choices = [
        {"name": f"{c.name} ({c.display_target()})", "value": c.name}
        for c in oracle_conns
    ]
    selected = select(message="Selecione a conexao:", choices=choices)
    if is_esc(selected):
        return

    conn = find_connection(selected)
    if not conn:
        show_error("Conexao nao encontrada.")
        return

    object_name = text(message="Nome do objeto (ex: TABELA, PKG, ou PKG.ROTINA):")
    if is_esc(object_name) or not object_name.strip():
        return

    obj_input = object_name.strip().upper()

    # Detect PACKAGE.ROUTINE format
    if "." in obj_input:
        pkg_name, routine_name = obj_input.split(".", 1)
        _extract_routine_flow(conn, pkg_name, routine_name)
    else:
        _extract_full_ddl_flow(conn, obj_input)


def _extract_full_ddl_flow(conn, object_name: str):
    """Extract full DDL for an object."""
    with console.status(f"Extraindo DDL de {object_name}..."):
        result = extract_ddl(conn, object_name)

    if result.errors and not result.objects:
        for err in result.errors:
            show_error(err)
        return

    filepath = save_extraction(result)

    # Summary
    console.print()
    console.rule("[bold cyan]🏗️  EXTRACAO DDL[/bold cyan]", style="cyan")
    console.print(f"  [bold]📦 Objeto:[/bold] {result.owner}.{result.object_name}")
    console.print(f"  [bold]🏷️  Tipo:[/bold] {result.object_type}")
    console.print(f"  [bold]🔌 Conexao:[/bold] {result.connection_name}")
    console.print()

    type_counts: dict[str, int] = {}
    for obj in result.objects:
        base_type = obj.obj_type.split("(")[0].strip()
        type_counts[base_type] = type_counts.get(base_type, 0) + 1

    for obj_type, count in type_counts.items():
        console.print(f"  [green]✅[/green] {obj_type}: {count}")

    if result.dependencies:
        console.print(f"\n  [bold]🔗 Dependencias:[/bold]")
        for dep in result.dependencies:
            console.print(f"    [dim]•[/dim] {dep}")

    if result.errors:
        console.print()
        for err in result.errors:
            show_warning(err)

    console.print()
    show_success(f"Arquivo salvo: {filepath}")
    console.print()


def _extract_routine_flow(conn, pkg_name: str, routine_name: str):
    """Extract a specific routine from a package with its dependencies."""
    with console.status(f"Extraindo {pkg_name}.{routine_name}..."):
        result = extract_routine(conn, pkg_name, routine_name)

    if result.errors and not result.body_routines:
        for err in result.errors:
            show_error(err)
        return

    dir_path = save_routine_extraction(result)

    # Summary
    console.print()
    console.rule("[bold cyan]🏗️  EXTRACAO DE ROTINA[/bold cyan]", style="cyan")
    console.print(f"  [bold]📦 Package:[/bold] {result.owner}.{result.package_name}")
    console.print(f"  [bold]🎯 Rotina:[/bold] {result.routine_name}")
    console.print(f"  [bold]🔌 Conexao:[/bold] {result.connection_name}")
    console.print()

    if result.spec_headers:
        console.print(f"  [green]✅[/green] Spec headers: {len(result.spec_headers)}")
    console.print(f"  [green]✅[/green] Rotinas extraidas: {len(result.body_routines)}")
    for obj in result.body_routines:
        marker = "[bold cyan]▸[/bold cyan]" if obj.name.upper() == routine_name else " "
        console.print(f"    {marker} {obj.obj_type}: {obj.name}")

    if result.dependencies:
        console.print(f"\n  [bold]🔗 Dependencias externas:[/bold]")
        for dep in result.dependencies:
            console.print(f"    [dim]•[/dim] {dep}")

    if result.errors:
        console.print()
        for err in result.errors:
            show_warning(err)

    console.print()
    console.print(f"  [bold]📂 Arquivos gerados:[/bold]")
    for f in result.saved_files:
        console.print(f"    [dim]•[/dim] {f}")
    console.print()
    show_success(f"Diretorio: {dir_path}")
    console.print()


def _adhoc_sql_flow():
    """Flow to execute an ad-hoc SQL statement."""
    console.print("\n[bold cyan]── ⌨️  SQL Avulso ──[/bold cyan]")
    console.print("[dim]Cole seu SQL e pressione Enter duas vezes para finalizar:[/dim]\n")

    # 1. Collect multiline SQL input
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "" and lines and lines[-1].strip() == "":
            break
        lines.append(line)

    raw_sql = "\n".join(lines).strip()
    if not raw_sql:
        show_error("Nenhum SQL informado.")
        return

    # 2. Classify SQL type
    sql_type = classify_sql(raw_sql)
    if sql_type == "UNKNOWN":
        show_error("Tipo de SQL nao suportado. Use SELECT, INSERT, UPDATE ou DELETE.")
        return

    console.print(f"\n  [bold]Tipo:[/bold] {sql_type}")

    # 3. Detect existing :params and literal values
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

    # 4. Detect literal values and offer parametrisation
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

    # 5. Select connection
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

    # 6. Re-execution loop
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

        # Gather parameter values
        param_values = {}
        cancelled = False
        for p in params:
            val = text(message=f"  {p.name}:", default=last_params.get(p.name, p.default))
            if is_esc(val):
                cancelled = True
                break
            param_values[p.name] = val

        if cancelled:
            continue

        last_params = dict(param_values)

        if action == "generate":
            _adhoc_generate_sql(sql, param_values, table_name)
        elif action == "execute":
            if sql_type == "SELECT":
                _adhoc_execute_select(sql, conn, param_values, table_name)
            else:
                _adhoc_execute_dml(sql, sql_type, conn, param_values)

        # Post-action: save or continue
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

        if result.rows:
            export_action = select(
                message="Exportar resultado?",
                choices=[
                    {"name": "💾  Exportar", "value": "export"},
                    {"name": "↩️   Continuar", "value": "skip"},
                ],
            )
            if not is_esc(export_action) and export_action == "export":
                _export_result(qr, table_name, param_values)
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
    name = text(message="Nome da consulta:")
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


def _portability_flow():
    """Export/Import configurations menu."""
    action = select(
        message="Exportar ou Importar?",
        choices=[
            {"name": "📤  Exportar configuracoes", "value": "export"},
            {"name": "📥  Importar configuracoes", "value": "import"},
        ],
    )

    if is_esc(action):
        return

    if action == "export":
        _export_configs_flow()
    else:
        _import_configs_flow()


def _export_configs_flow():
    """Export configurations to a .dbqm file."""
    items = checkbox(
        message="O que exportar?",
        choices=[
            {"name": "🔌  Conexoes", "value": "connections", "enabled": True},
            {"name": "📝  Consultas", "value": "queries", "enabled": True},
            {"name": "📁  Grupos", "value": "groups", "enabled": True},
        ],
    )

    if is_esc(items) or not items:
        return

    password = secret(message="Senha para proteger o arquivo:")
    if is_esc(password) or not password:
        show_warning("Senha obrigatoria para exportar.")
        return

    password_confirm = secret(message="Confirme a senha:")
    if is_esc(password_confirm):
        return

    if password != password_confirm:
        show_error("Senhas nao conferem.")
        return

    try:
        path = export_configs(
            password=password,
            include_connections="connections" in items,
            include_queries="queries" in items,
            include_groups="groups" in items,
        )
        show_success(f"Configuracoes exportadas: {path}")
    except Exception as e:
        show_error(f"Erro ao exportar: {e}")


def _import_configs_flow():
    """Import configurations from a .dbqm file."""
    filepath = text(message="Caminho do arquivo .dbqm:")
    if is_esc(filepath) or not filepath:
        return

    filepath = filepath.strip().strip('"').strip("'")

    from pathlib import Path
    if not Path(filepath).exists():
        show_error("Arquivo nao encontrado.")
        return

    password = secret(message="Senha do arquivo:")
    if is_esc(password) or not password:
        return

    try:
        summary = import_configs(filepath, password)
        total = summary["connections"] + summary["queries"] + summary["groups"]
        parts = []
        if summary["connections"]:
            parts.append(f'{summary["connections"]} conexoes')
        if summary["queries"]:
            parts.append(f'{summary["queries"]} consultas')
        if summary["groups"]:
            parts.append(f'{summary["groups"]} grupos')
        if summary["skipped"]:
            parts.append(f'{summary["skipped"]} ignorados (duplicados)')

        if total > 0:
            show_success(f"Importado: {', '.join(parts)}")
        else:
            show_warning(f"Nenhuma configuracao nova importada. {summary['skipped']} duplicados ignorados.")
    except Exception as e:
        show_error(f"Erro ao importar: {e}")
