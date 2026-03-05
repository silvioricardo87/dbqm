"""Object browser flow: tables, packages (Oracle), and views."""
from __future__ import annotations

from rich.console import Console

from dbqm.core.db_manager import get_connection
from dbqm.core.table_browser import _validate_identifier
from dbqm.core.object_browser import (
    list_objects, get_table_structure, list_package_routines,
    get_package_source, get_view_definition, execute_routine,
    PackageInfo, RoutineInfo, TableStructure, ViewInfo,
)
from dbqm.core.query_engine import QueryResult, AdhocResult, execute_adhoc
from dbqm.core.table_browser import browse_table
from dbqm.core.exporter import (
    export_query_csv, export_query_json, export_query_txt, export_sql_file,
)
from dbqm.models.connection import load_connections, find_connection
from dbqm.ui.display import (
    show_error, show_warning, show_info, show_success,
    show_table_structure, show_package_routines, show_view_definition,
    show_routine_result, show_source_code, show_query_result,
    show_browse_result,
)
from dbqm.ui.helpers import pick_format, prompt_open_file, read_multiline_sql
from dbqm.ui.prompts import select, text, is_esc

console = Console()

DEFAULT_LIMIT = 100


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def object_browser_flow():
    """Flow to browse database objects (tables, packages, views)."""
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

        while True:
            type_choices = [
                {"name": "Tabelas", "value": "TABLE"},
                {"name": "Views", "value": "VIEW"},
            ]
            if conn.db_type == "oracle":
                type_choices.insert(1, {"name": "Packages", "value": "PACKAGE"})
            if conn.db_type in ("postgresql", "mysql"):
                type_choices.append({"name": "Rotinas", "value": "ROUTINE"})
            type_choices.append({"name": "Voltar", "value": "back"})

            obj_type = select(message="Tipo de objeto:", choices=type_choices)
            if is_esc(obj_type) or obj_type == "back":
                return

            if obj_type == "TABLE":
                _table_flow(db, conn)
            elif obj_type == "PACKAGE":
                _package_flow(db, conn)
            elif obj_type == "VIEW":
                _view_flow(db, conn)
            elif obj_type == "ROUTINE":
                _routine_list_flow(db, conn)

    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _pick_object(objects: list[str], label: str) -> str | None:
    """Let user pick an object from a list, with text filter support."""
    filter_text = text(message=f"Filtro de {label} (Enter para listar todos):")
    if is_esc(filter_text):
        return None

    if filter_text:
        filtered = [o for o in objects if filter_text.upper() in o.upper()]
    else:
        filtered = objects

    if not filtered:
        show_warning(f"Nenhum(a) {label} encontrado(a) com esse filtro.")
        return None

    if len(filtered) > 200:
        show_info(f"Exibindo os primeiros 200 de {len(filtered)} {label}.")

    choices = [{"name": o, "value": o} for o in filtered[:200]]
    selected = select(message=f"Selecione {label}:", choices=choices)
    if is_esc(selected):
        return None

    return selected


# ---------------------------------------------------------------------------
# Table sub-flow
# ---------------------------------------------------------------------------

def _table_flow(db, conn):
    """Sub-flow for browsing tables: list, pick, show structure, actions."""
    with console.status("Listando tabelas..."):
        tables = list_objects(db, conn.db_type, "TABLE")

    if not tables:
        show_warning("Nenhuma tabela encontrada.")
        return

    if len(tables) > 200:
        show_info(f"{len(tables)} tabelas encontradas. Use o filtro para refinar.")

    while True:
        table_name = _pick_object(tables, "tabela")
        if table_name is None:
            return

        with console.status(f"Carregando estrutura de {table_name}..."):
            structure = get_table_structure(db, conn.db_type, table_name)

        show_table_structure(structure)

        while True:
            action = select(
                message="Acao:",
                choices=[
                    {"name": "Consultar dados", "value": "query"},
                    {"name": "Exportar estrutura", "value": "export_struct"},
                    {"name": "Voltar", "value": "back"},
                ],
            )
            if is_esc(action) or action == "back":
                break

            if action == "query":
                _query_editor(db, conn, table_name)
            elif action == "export_struct":
                _export_structure(structure, conn.name)


# ---------------------------------------------------------------------------
# Query editor (table data query with pagination)
# ---------------------------------------------------------------------------

def _query_editor(db, conn, table_name: str):
    """Interactive query editor for a table with pagination."""
    safe_name = _validate_identifier(table_name)
    if conn.db_type in ("oracle", "postgresql"):
        default_sql = f'SELECT * FROM "{safe_name}"'
    elif conn.db_type == "mysql":
        default_sql = f"SELECT * FROM `{safe_name}`"
    else:
        default_sql = f"SELECT * FROM [{safe_name}]"

    console.print(f"\n  [bold]SQL padrao:[/bold] [dim]{default_sql}[/dim]")
    console.print("  [dim]Edite abaixo (Enter duas vezes para manter o padrao):[/dim]\n")

    custom_sql = read_multiline_sql()
    raw_sql = custom_sql if custom_sql else default_sql

    limit = DEFAULT_LIMIT
    offset = 0

    while True:
        # Build paginated SQL
        paginated_sql = raw_sql.rstrip().rstrip(";")
        if conn.db_type == "oracle":
            paginated_sql += f" OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
        elif conn.db_type in ("postgresql", "mysql"):
            paginated_sql += f" LIMIT {limit} OFFSET {offset}"
        else:
            if "ORDER BY" not in paginated_sql.upper():
                paginated_sql += " ORDER BY (SELECT NULL)"
            paginated_sql += f" OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"

        with console.status(f"Executando consulta em {conn.name}..."):
            result = execute_adhoc(paginated_sql, conn, {})

        if not isinstance(result, AdhocResult):
            result = result[0]

        if not result.success:
            show_error(f"Erro: {result.error}")
            return

        qr = QueryResult(
            query_name=f"Consulta: {table_name}",
            connection_name=result.connection_name,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            elapsed=result.elapsed,
        )
        show_query_result(qr)

        # Post-query actions
        action_choices = [
            {"name": "Exportar resultado", "value": "export"},
            {"name": "Alterar limite", "value": "limit"},
        ]
        if result.row_count >= limit:
            action_choices.append({"name": "Proxima pagina", "value": "next"})
        if offset > 0:
            action_choices.append({"name": "Pagina anterior", "value": "prev"})
        action_choices.append({"name": "Editar query", "value": "edit"})
        action_choices.append({"name": "Voltar", "value": "back"})

        action = select(message="Acao:", choices=action_choices)
        if is_esc(action) or action == "back":
            return

        if action == "export":
            _export_query_result(qr, table_name)
        elif action == "limit":
            new_limit = text(message="Novo limite:", default=str(limit))
            if not is_esc(new_limit) and new_limit.strip().isdigit():
                limit = int(new_limit.strip())
                offset = 0
        elif action == "next":
            offset += limit
        elif action == "prev":
            offset = max(0, offset - limit)
        elif action == "edit":
            console.print(f"\n  [bold]SQL atual:[/bold] [dim]{raw_sql}[/dim]")
            console.print("  [dim]Edite abaixo (Enter duas vezes para manter o atual):[/dim]\n")
            new_sql = read_multiline_sql()
            if new_sql:
                raw_sql = new_sql
                offset = 0


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _export_structure(structure: TableStructure, conn_name: str):
    """Export table structure as a query result (columns as rows)."""
    columns = ["Coluna", "Tipo", "Tamanho", "Nullable", "Chave"]
    rows = []
    for col in structure.columns:
        if col.data_precision is not None:
            size = f"{col.data_precision}"
            if col.data_scale is not None and col.data_scale > 0:
                size += f",{col.data_scale}"
        elif col.data_length is not None:
            size = str(col.data_length)
        else:
            size = ""

        key_parts = []
        if col.is_pk:
            key_parts.append("PK")
        if col.fk_ref:
            key_parts.append(f"FK -> {col.fk_ref}")
        key = " ".join(key_parts)

        rows.append([col.name, col.data_type, size, "Y" if col.nullable else "N", key])

    qr = QueryResult(
        query_name=f"Estrutura: {structure.table}",
        connection_name=conn_name,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        elapsed=structure.elapsed,
    )

    fmt = pick_format()
    if fmt is None:
        return

    if fmt == "csv":
        path = export_query_csv(qr, structure.table)
    elif fmt == "json":
        path = export_query_json(qr, structure.table)
    else:
        path = export_query_txt(qr, structure.table)

    show_success(f"Exportado: {path}")
    prompt_open_file(path)


def _export_query_result(qr: QueryResult, table_name: str):
    """Export a query result with format picker."""
    fmt = pick_format()
    if fmt is None:
        return

    if fmt == "csv":
        path = export_query_csv(qr, table_name)
    elif fmt == "json":
        path = export_query_json(qr, table_name)
    else:
        path = export_query_txt(qr, table_name)

    show_success(f"Exportado: {path}")
    prompt_open_file(path)


# ---------------------------------------------------------------------------
# Package sub-flow (Oracle only)
# ---------------------------------------------------------------------------

def _package_flow(db, conn):
    """Sub-flow for browsing packages: list, pick, show routines, actions."""
    with console.status("Listando packages..."):
        packages = list_objects(db, conn.db_type, "PACKAGE")

    if not packages:
        show_warning("Nenhum package encontrado.")
        return

    if len(packages) > 200:
        show_info(f"{len(packages)} packages encontrados. Use o filtro para refinar.")

    while True:
        pkg_name = _pick_object(packages, "package")
        if pkg_name is None:
            return

        with console.status(f"Carregando rotinas de {pkg_name}..."):
            pkg_info = list_package_routines(db, conn.db_type, pkg_name)

        show_package_routines(pkg_info)

        while True:
            action = select(
                message="Acao:",
                choices=[
                    {"name": "Executar rotina", "value": "execute"},
                    {"name": "Ver spec completa", "value": "spec"},
                    {"name": "Ver body completo", "value": "body"},
                    {"name": "Exportar package", "value": "export"},
                    {"name": "Voltar", "value": "back"},
                ],
            )
            if is_esc(action) or action == "back":
                break

            if action == "execute":
                _execute_routine_flow(db, conn, pkg_info)
            elif action == "spec":
                with console.status(f"Carregando spec de {pkg_name}..."):
                    source = get_package_source(db, conn.db_type, pkg_name, "PACKAGE")
                if source:
                    show_source_code(f"SPEC: {pkg_name}", source)
                else:
                    show_warning("Spec nao encontrada.")
            elif action == "body":
                with console.status(f"Carregando body de {pkg_name}..."):
                    source = get_package_source(db, conn.db_type, pkg_name, "PACKAGE BODY")
                if source:
                    show_source_code(f"BODY: {pkg_name}", source)
                else:
                    show_warning("Body nao encontrado.")
            elif action == "export":
                _export_package(db, conn, pkg_name)


# ---------------------------------------------------------------------------
# Routine execution
# ---------------------------------------------------------------------------

def _execute_routine_flow(db, conn, pkg_info: PackageInfo):
    """Pick a routine from a package and execute it with user-supplied params."""
    if not pkg_info.routines:
        show_warning("Nenhuma rotina encontrada neste package.")
        return

    routine_choices = [
        {
            "name": f"{r.routine_type} {r.name} {r.signature}",
            "value": r.name,
        }
        for r in pkg_info.routines
    ]
    routine_name = select(message="Selecione a rotina:", choices=routine_choices)
    if is_esc(routine_name):
        return

    routine = next((r for r in pkg_info.routines if r.name == routine_name), None)
    if routine is None:
        show_error("Rotina nao encontrada.")
        return

    # Gather IN parameters
    param_values: dict[str, str] = {}
    for p in routine.params:
        if p.direction in ("IN", "IN OUT"):
            val = text(
                message=f"  {p.name} ({p.direction} {p.data_type}):",
                default=p.default or "",
            )
            if is_esc(val):
                return
            param_values[p.name] = val

    # Execute
    with console.status(f"Executando {pkg_info.name}.{routine.name}..."):
        result = execute_routine(db, pkg_info.name, routine, param_values)

    show_routine_result(result)

    if not result.success:
        return

    # Post-execution actions
    action = select(
        message="Acao:",
        choices=[
            {"name": "COMMIT (efetivar)", "value": "commit"},
            {"name": "ROLLBACK (desfazer)", "value": "rollback"},
            {"name": "Exportar saida", "value": "export"},
            {"name": "Voltar", "value": "back"},
        ],
    )
    if is_esc(action) or action == "back":
        return

    if action == "commit":
        db.commit()
        show_success("COMMIT executado.")
    elif action == "rollback":
        db.rollback()
        show_warning("ROLLBACK executado. Alteracoes desfeitas.")
    elif action == "export":
        _export_routine_output(result, pkg_info.name, routine.name, conn.name)


# ---------------------------------------------------------------------------
# Package export
# ---------------------------------------------------------------------------

def _export_package(db, conn, pkg_name: str):
    """Export package spec + body source to a .sql file."""
    with console.status(f"Carregando source de {pkg_name}..."):
        spec = get_package_source(db, conn.db_type, pkg_name, "PACKAGE")
        body = get_package_source(db, conn.db_type, pkg_name, "PACKAGE BODY")

    parts: list[str] = []
    if spec:
        parts.append(f"-- PACKAGE SPEC: {pkg_name}")
        parts.append(f"CREATE OR REPLACE {spec}")
        parts.append("/")
        parts.append("")
    if body:
        parts.append(f"-- PACKAGE BODY: {pkg_name}")
        parts.append(f"CREATE OR REPLACE {body}")
        parts.append("/")

    if not parts:
        show_warning("Nenhum source encontrado para este package.")
        return

    content = "\n".join(parts)
    path = export_sql_file(content, pkg_name)
    show_success(f"Exportado: {path}")
    prompt_open_file(path)


# ---------------------------------------------------------------------------
# Routine output export
# ---------------------------------------------------------------------------

def _export_routine_output(result, pkg_name: str, routine_name: str, conn_name: str):
    """Export routine execution output as a text file."""
    lines: list[str] = []
    lines.append(f"Package: {pkg_name}")
    lines.append(f"Rotina: {routine_name}")
    lines.append(f"Conexao: {conn_name}")
    lines.append(f"Tempo: {result.elapsed:.2f}s")
    lines.append(f"Status: {'Sucesso' if result.success else 'Erro'}")
    lines.append("")

    if result.output_lines:
        lines.append("DBMS_OUTPUT:")
        for line in result.output_lines:
            lines.append(f"  {line}")
        lines.append("")

    if result.return_value is not None:
        lines.append(f"RETURN: {result.return_value}")
        lines.append("")

    if result.error:
        lines.append(f"ERRO: {result.error}")

    content = "\n".join(lines)
    label = f"{pkg_name}_{routine_name}"
    path = export_sql_file(content, label)
    show_success(f"Exportado: {path}")
    prompt_open_file(path)


# ---------------------------------------------------------------------------
# Routine sub-flow (PostgreSQL/MySQL)
# ---------------------------------------------------------------------------

def _routine_list_flow(db, conn):
    """Sub-flow for browsing stored routines (PostgreSQL/MySQL)."""
    with console.status("Listando rotinas..."):
        routines = list_objects(db, conn.db_type, "ROUTINE")

    if not routines:
        show_warning("Nenhuma rotina encontrada.")
        return

    if len(routines) > 200:
        show_info(f"{len(routines)} rotinas encontradas. Use o filtro para refinar.")

    routine_name = _pick_object(routines, "rotina")
    if routine_name is None:
        return

    cursor = db.cursor()
    try:
        if conn.db_type == "postgresql":
            cursor.execute("""
                SELECT routine_type, data_type, routine_definition
                FROM information_schema.routines
                WHERE routine_name = %(name)s AND routine_schema = 'public'
            """, {"name": routine_name})
        else:
            cursor.execute("""
                SELECT routine_type, data_type, routine_definition
                FROM information_schema.routines
                WHERE routine_name = %(name)s AND routine_schema = DATABASE()
            """, {"name": routine_name})
        row = cursor.fetchone()
        if row:
            rtype, rdata, rdef = row
            console.print(f"\n  [bold]Tipo:[/bold] {rtype}")
            if rdata:
                console.print(f"  [bold]Retorno:[/bold] {rdata}")
            if rdef:
                show_source_code(f"{rtype}: {routine_name}", rdef)
            else:
                show_warning("Definicao nao disponivel (rotina compilada ou sem permissao).")
        else:
            show_warning("Rotina nao encontrada.")
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# View sub-flow
# ---------------------------------------------------------------------------

def _view_flow(db, conn):
    """Sub-flow for browsing views: list, pick, show definition, actions."""
    with console.status("Listando views..."):
        views = list_objects(db, conn.db_type, "VIEW")

    if not views:
        show_warning("Nenhuma view encontrada.")
        return

    if len(views) > 200:
        show_info(f"{len(views)} views encontradas. Use o filtro para refinar.")

    while True:
        view_name = _pick_object(views, "view")
        if view_name is None:
            return

        with console.status(f"Carregando definicao de {view_name}..."):
            view_info = get_view_definition(db, conn.db_type, view_name)

        show_view_definition(view_info)

        while True:
            action = select(
                message="Acao:",
                choices=[
                    {"name": "Consultar dados", "value": "query"},
                    {"name": "Exportar definicao", "value": "export"},
                    {"name": "Voltar", "value": "back"},
                ],
            )
            if is_esc(action) or action == "back":
                break

            if action == "query":
                _view_data_flow(db, conn, view_name)
            elif action == "export":
                content = f"-- VIEW: {view_name}\n{view_info.sql_definition}"
                path = export_sql_file(content, view_name)
                show_success(f"Exportado: {path}")
                prompt_open_file(path)


# ---------------------------------------------------------------------------
# View data flow (browse with pagination)
# ---------------------------------------------------------------------------

def _view_data_flow(db, conn, view_name: str):
    """Browse view data with pagination using table_browser."""
    limit = DEFAULT_LIMIT
    offset = 0

    while True:
        with console.status(f"Consultando {view_name}..."):
            result = browse_table(db, conn.db_type, view_name, conn.name, limit, offset)

        show_browse_result(result)

        # Post-browse actions
        action_choices = [
            {"name": "Exportar resultado", "value": "export"},
            {"name": "Alterar limite", "value": "limit"},
        ]
        if result.offset + result.limit < result.total_count:
            action_choices.append({"name": "Proxima pagina", "value": "next"})
        if result.offset > 0:
            action_choices.append({"name": "Pagina anterior", "value": "prev"})
        action_choices.append({"name": "Voltar", "value": "back"})

        action = select(message="Acao:", choices=action_choices)
        if is_esc(action) or action == "back":
            return

        if action == "export":
            qr = QueryResult(
                query_name=f"View: {view_name}",
                connection_name=result.connection_name,
                columns=result.columns,
                rows=result.rows,
                row_count=result.row_count,
                elapsed=result.elapsed,
            )
            _export_query_result(qr, view_name)
        elif action == "limit":
            new_limit = text(message="Novo limite:", default=str(limit))
            if not is_esc(new_limit) and new_limit.strip().isdigit():
                limit = int(new_limit.strip())
                offset = 0
        elif action == "next":
            offset += limit
        elif action == "prev":
            offset = max(0, offset - limit)
