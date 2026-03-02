"""Main interactive menu."""
from __future__ import annotations

from rich.console import Console

from dbqm.core.query_engine import execute_query, QueryResult
from dbqm.core.group_engine import build_group_result, GroupResult
from dbqm.core.exporter import (
    export_query_csv, export_query_json, export_query_txt,
    export_group_csv, export_group_json, export_group_txt,
)
from dbqm.models.connection import load_connections, find_connection
from dbqm.models.query import load_queries, find_query
from dbqm.models.group import load_groups, find_group
from dbqm.ui.display import (
    show_banner, show_success, show_error, show_warning, show_info,
    show_query_result, show_group_result,
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
                {"name": "Executar consulta", "value": "exec_query"},
                {"name": "Executar grupo de consultas", "value": "exec_group"},
                {"name": "Extrair DDL de objeto", "value": "extract_ddl"},
                {"name": "Configuracoes", "value": "config"},
                {"name": "Sair", "value": "exit"},
            ],
        )

        if is_esc(action) or action == "exit":
            console.print("\n[dim]Ate logo![/dim]\n")
            break
        elif action == "config":
            _config_menu()
        elif action == "extract_ddl":
            _extract_ddl_flow()
        elif action == "exec_query":
            _execute_query_flow()
        elif action == "exec_group":
            _execute_group_flow()


def _config_menu():
    """Configuration sub-menu."""
    while True:
        action = select(
            message="Configuracoes:",
            choices=[
                {"name": "Conexoes", "value": "config_conn"},
                {"name": "Consultas", "value": "config_query"},
                {"name": "Grupos", "value": "config_group"},
                {"name": "Exportar/Importar", "value": "portability"},
                {"name": "Voltar", "value": "back"},
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

    # Gather parameters
    param_values = {}
    for p in query.params:
        prompt = f"{p.name}"
        if p.description:
            prompt += f" ({p.description})"
        val = text(message=f"  {prompt}:", default=p.default)
        if is_esc(val):
            return
        param_values[p.name] = val

    # Execute
    with console.status(f"Executando {query.name} em {conn.name}..."):
        result = execute_query(query, conn, param_values)

    if result.success and result.rows:
        query.apply_column_maps(result.rows, result.columns)

    show_query_result(result)

    if result.success and result.rows:
        _post_result_actions(result, query.table)


def _post_result_actions(result: QueryResult, table: str = ""):
    """Actions after displaying a query result."""
    while True:
        action = select(
            message="Acao:",
            choices=[
                {"name": "Exportar resultado", "value": "export"},
                {"name": "Reexecutar", "value": "reexec"},
                {"name": "Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            break
        elif action == "reexec":
            return
        elif action == "export":
            _export_result(result, table)


def _export_result(result: QueryResult, table: str = ""):
    """Export a single query result."""
    fmt = select(
        message="Formato:",
        choices=[
            {"name": "CSV", "value": "csv"},
            {"name": "JSON", "value": "json"},
            {"name": "TXT (tabela formatada)", "value": "txt"},
        ],
    )

    if is_esc(fmt):
        return

    if fmt == "csv":
        path = export_query_csv(result, table)
    elif fmt == "json":
        path = export_query_json(result, table)
    else:
        path = export_query_txt(result, table)

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

    # Gather shared params
    param_values = {}
    for param_name, param_info in group.shared_params.items():
        desc = param_info.get("description", "")
        default = param_info.get("default", "")
        prompt = f"{param_name}"
        if desc:
            prompt += f" ({desc})"
        val = text(message=f"  {prompt}:", default=default)
        if is_esc(val):
            return
        param_values[param_name] = val

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

    show_group_result(group_result, param_values)

    # Post-group actions
    _post_group_actions(group_result, param_values)


def _post_group_actions(group_result: GroupResult, params: dict):
    """Actions after displaying a group result."""
    while True:
        action = select(
            message="Acao:",
            choices=[
                {"name": "Exportar resultado completo", "value": "export"},
                {"name": "Ver resultados individuais", "value": "detail"},
                {"name": "Reexecutar", "value": "reexec"},
                {"name": "Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            break
        elif action == "reexec":
            return
        elif action == "export":
            _export_group(group_result, params)
        elif action == "detail":
            _show_individual_results(group_result)


def _export_group(group_result: GroupResult, params: dict):
    """Export group result."""
    fmt = select(
        message="Formato:",
        choices=[
            {"name": "CSV", "value": "csv"},
            {"name": "JSON", "value": "json"},
            {"name": "TXT (tabela formatada)", "value": "txt"},
        ],
    )

    if is_esc(fmt):
        return

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
    console.rule("[bold cyan]EXTRACAO DDL[/bold cyan]", style="cyan")
    console.print(f"  [bold]Objeto:[/bold] {result.owner}.{result.object_name}")
    console.print(f"  [bold]Tipo:[/bold] {result.object_type}")
    console.print(f"  [bold]Conexao:[/bold] {result.connection_name}")
    console.print()

    type_counts: dict[str, int] = {}
    for obj in result.objects:
        base_type = obj.obj_type.split("(")[0].strip()
        type_counts[base_type] = type_counts.get(base_type, 0) + 1

    for obj_type, count in type_counts.items():
        console.print(f"  [green]v[/green] {obj_type}: {count}")

    if result.dependencies:
        console.print(f"\n  [bold]Dependencias:[/bold]")
        for dep in result.dependencies:
            console.print(f"    [dim]-[/dim] {dep}")

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
    console.rule("[bold cyan]EXTRACAO DE ROTINA[/bold cyan]", style="cyan")
    console.print(f"  [bold]Package:[/bold] {result.owner}.{result.package_name}")
    console.print(f"  [bold]Rotina:[/bold] {result.routine_name}")
    console.print(f"  [bold]Conexao:[/bold] {result.connection_name}")
    console.print()

    if result.spec_headers:
        console.print(f"  [green]v[/green] Spec headers: {len(result.spec_headers)}")
    console.print(f"  [green]v[/green] Rotinas extraidas: {len(result.body_routines)}")
    for obj in result.body_routines:
        marker = "[bold cyan]*[/bold cyan]" if obj.name.upper() == routine_name else " "
        console.print(f"    {marker} {obj.obj_type}: {obj.name}")

    if result.dependencies:
        console.print(f"\n  [bold]Dependencias externas:[/bold]")
        for dep in result.dependencies:
            console.print(f"    [dim]-[/dim] {dep}")

    if result.errors:
        console.print()
        for err in result.errors:
            show_warning(err)

    console.print()
    console.print(f"  [bold]Arquivos gerados:[/bold]")
    for f in result.saved_files:
        console.print(f"    [dim]-[/dim] {f}")
    console.print()
    show_success(f"Diretorio: {dir_path}")
    console.print()


def _portability_flow():
    """Export/Import configurations menu."""
    action = select(
        message="Exportar ou Importar?",
        choices=[
            {"name": "Exportar configuracoes", "value": "export"},
            {"name": "Importar configuracoes", "value": "import"},
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
            {"name": "Conexoes", "value": "connections", "enabled": True},
            {"name": "Consultas", "value": "queries", "enabled": True},
            {"name": "Grupos", "value": "groups", "enabled": True},
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
