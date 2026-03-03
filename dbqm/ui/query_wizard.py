"""Query configuration wizard — guided and paste modes."""
from __future__ import annotations

from rich.console import Console
from rich.table import Table

from dbqm.core.query_engine import parse_sql, detect_params, replace_literals_with_params, execute_query
from dbqm.models.connection import load_connections, find_connection
from dbqm.models.query import Query, QueryParam, load_queries, save_queries
from dbqm.models.group import load_groups, save_groups
from dbqm.ui.display import show_success, show_error, show_warning, show_info, show_query_result
from dbqm.ui.helpers import pick_entity, read_multiline_sql
from dbqm.ui.prompts import select, text, confirm, is_esc

console = Console()


def query_wizard():
    """Main query management menu."""
    while True:
        queries = load_queries()
        console.print("\n[bold cyan]═══ 📝 Consultas Configuradas ═══[/bold cyan]\n")

        if queries:
            table = Table(show_lines=False, border_style="dim")
            table.add_column("#", style="bold", width=4)
            table.add_column("Nome", style="white")
            table.add_column("Conexao", style="white")
            table.add_column("Tabela", style="white")
            table.add_column("Params", style="dim")
            for i, q in enumerate(queries, 1):
                params_str = ", ".join(p.name for p in q.params) if q.params else "-"
                table.add_row(str(i), q.name, q.connection, q.table, params_str)
            console.print(table)
        else:
            show_warning("Nenhuma consulta configurada.")

        console.print()
        action = select(
            message="Acao:",
            choices=[
                {"name": "➕  Nova consulta", "value": "new"},
                {"name": "👁️   Visualizar SQL", "value": "view"},
                {"name": "🔄  Mapeamento de valores", "value": "maps"},
                {"name": "🏷️   Renomear consulta", "value": "rename"},
                {"name": "📋  Duplicar consulta", "value": "dup"},
                {"name": "🗑️   Remover consulta", "value": "remove"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            break
        elif action == "new":
            _create_query()
        elif action == "view":
            _view_query(queries)
        elif action == "maps":
            _edit_column_maps(queries)
        elif action == "rename":
            _rename_query(queries)
        elif action == "dup":
            _duplicate_query(queries)
        elif action == "remove":
            _remove_query(queries)


def _select_connection() -> str | None:
    """Let user pick a connection from the configured list."""
    connections = load_connections()
    if not connections:
        show_error("Nenhuma conexao configurada. Configure uma conexao primeiro.")
        return None
    choices = [{"name": f"{c.name} ({c.db_type} - {c.display_target()})", "value": c.name} for c in connections]
    result = select(message="Conexao:", choices=choices)
    if is_esc(result):
        return None
    return result


def _create_query():
    """Choose between wizard or paste mode."""
    mode = select(
        message="Como deseja configurar a consulta?",
        choices=[
            {"name": "📋  Colar SQL direto (sistema organiza)", "value": "paste"},
            {"name": "🧙  Passo a passo (wizard guiado)", "value": "wizard"},
        ],
    )

    if is_esc(mode):
        return

    if mode == "paste":
        _create_query_paste()
    else:
        _create_query_wizard()


def _create_query_paste():
    """Create query by pasting raw SQL."""
    console.print("\n[bold cyan]── 📋 Colar SQL ──[/bold cyan]")
    console.print("[dim]Cole sua consulta SQL e pressione Enter duas vezes para finalizar:[/dim]\n")

    raw_sql = read_multiline_sql()
    if not raw_sql:
        show_error("Nenhum SQL informado.")
        return

    # Parse the SQL
    parsed = parse_sql(raw_sql)
    console.print("\n[bold]Analise da consulta:[/bold]")
    console.print(f"  Tabela:    {parsed['table']}")
    console.print(f"  Colunas:   {', '.join(parsed['columns'])}")
    if parsed['where_values']:
        console.print(f"  Condicoes: {parsed['where_values']}")
    if parsed['order_by']:
        console.print(f"  Ordenacao: {parsed['order_by']}")
    console.print()

    # Name and connection
    name = text(message="Nome da consulta:")
    if is_esc(name) or not name:
        if not name and not is_esc(name):
            show_error("Nome obrigatorio.")
        return

    existing = load_queries()
    if any(q.name == name for q in existing):
        show_error(f'Consulta "{name}" ja existe.')
        return

    conn_name = _select_connection()
    if conn_name is None:
        return

    # Parametrize literal values
    sql = raw_sql
    params: list[QueryParam] = []

    # Check for existing bind variables
    existing_params = detect_params(sql)
    for p in existing_params:
        desc = text(message=f"Descricao do parametro :{p}:")
        if is_esc(desc):
            return
        default = text(message=f"Valor padrao para :{p} (vazio para nenhum):")
        if is_esc(default):
            return
        params.append(QueryParam(name=p, description=desc or "", default=default or ""))

    # Offer to parametrize literal values found in WHERE
    if parsed['where_values'] and not existing_params:
        transform = confirm(message="Transformar valores fixos em parametros?", default=True)
        if is_esc(transform):
            return
        if transform:
            replacements = {}
            for col, val in parsed['where_values'].items():
                console.print(f"\n  Valor [yellow]'{val}'[/yellow] encontrado para coluna [bold]{col}[/bold]")
                param_name = text(message="Nome do parametro:", default=col)
                if is_esc(param_name):
                    return
                desc = text(message="Descricao:")
                if is_esc(desc):
                    return
                default = text(message="Valor padrao:", default=val)
                if is_esc(default):
                    return
                replacements[param_name] = val
                params.append(QueryParam(name=param_name, description=desc or "", default=default or ""))

            sql = replace_literals_with_params(sql, replacements)

    # Confirm ordering
    change_order = confirm(message="Alterar ordenacao?", default=False)
    if is_esc(change_order):
        return
    order_by = parsed['order_by']
    if change_order:
        order_by = text(message="ORDER BY:", default=order_by)
        if is_esc(order_by):
            return

    query = Query(
        name=name,
        connection=conn_name,
        sql=sql.strip().rstrip(";"),
        table=parsed['table'],
        params=params,
        columns=parsed['columns'],
        order_by=order_by,
    )

    if not _confirm_or_test(query, existing):
        return


def _create_query_wizard():
    """Create query step by step."""
    console.print("\n[bold cyan]── 🧙 Nova Consulta (Wizard) ──[/bold cyan]\n")

    name = text(message="Nome da consulta:")
    if is_esc(name) or not name:
        if not name and not is_esc(name):
            show_error("Nome obrigatorio.")
        return

    existing = load_queries()
    if any(q.name == name for q in existing):
        show_error(f'Consulta "{name}" ja existe.')
        return

    conn_name = _select_connection()
    if conn_name is None:
        return

    table_name = text(message="Tabela (schema.tabela ou tabela):")
    if is_esc(table_name) or not table_name:
        if not table_name and not is_esc(table_name):
            show_error("Tabela obrigatoria.")
        return

    # Columns
    console.print("\n[dim]Campos de retorno (um por linha, vazio para finalizar):[/dim]")
    columns_raw = []
    while True:
        col = text(message="  campo:")
        if is_esc(col):
            return
        if not col:
            break
        columns_raw.append(col)

    if not columns_raw:
        columns_raw = ["*"]

    # WHERE conditions
    console.print("\n[dim]Condicoes WHERE (uma por linha, vazio para finalizar):[/dim]")
    console.print("[dim]Use :nome_param para parametros (ex: NO_APOLICE = :apolice)[/dim]")
    conditions = []
    while True:
        cond = text(message="  condicao:")
        if is_esc(cond):
            return
        if not cond:
            break
        conditions.append(cond)

    # Build SQL
    select_part = ",\n    ".join(columns_raw)
    sql = f"SELECT\n    {select_part}\nFROM {table_name}"

    if conditions:
        where_part = "\n    AND ".join(conditions)
        sql += f"\nWHERE {where_part}"

    # Detect params
    params: list[QueryParam] = []
    detected = detect_params(sql)
    if detected:
        console.print(f"\n[bold]Parametros detectados:[/bold] {', '.join(detected)}")
        for p in detected:
            desc = text(message=f"  Descricao de :{p}:")
            if is_esc(desc):
                return
            default = text(message=f"  Valor padrao de :{p}:")
            if is_esc(default):
                return
            params.append(QueryParam(name=p, description=desc or "", default=default or ""))

    # ORDER BY
    order_by = text(message="\nOrdenacao ORDER BY (vazio para nenhuma):")
    if is_esc(order_by):
        return
    if order_by:
        sql += f"\nORDER BY {order_by}"

    # Extract column aliases
    parsed = parse_sql(sql)
    columns = parsed['columns'] if parsed['columns'] else [c.split()[-1] for c in columns_raw]

    console.print("\n[bold]SQL gerado:[/bold]")
    console.print(f"[dim]{sql}[/dim]\n")

    query = Query(
        name=name,
        connection=conn_name,
        sql=sql,
        table=table_name,
        params=params,
        columns=columns,
        order_by=order_by,
    )

    if not _confirm_or_test(query, existing):
        return


def _confirm_or_test(query: Query, existing: list[Query]) -> bool:
    """Show test/save menu before saving. Returns True if saved, False if cancelled."""
    while True:
        maps_label = "Configurar mapeamento de valores"
        if query.column_maps:
            n = sum(len(v) for v in query.column_maps.values())
            maps_label += f" ({n} regras)"
        action = select(
            message="O que deseja fazer?",
            choices=[
                {"name": f"🧪  Testar execucao antes de salvar", "value": "test"},
                {"name": f"🔄  {maps_label}", "value": "maps"},
                {"name": "💾  Salvar consulta", "value": "save"},
                {"name": "🗑️   Descartar", "value": "discard"},
            ],
        )

        if is_esc(action) or action == "discard":
            show_warning("Consulta descartada.")
            return False

        if action == "maps":
            _configure_column_maps(query)

        elif action == "test":
            conn = find_connection(query.connection)
            if not conn:
                show_error(f'Conexao "{query.connection}" nao encontrada.')
                continue

            # Gather param values for test
            param_values = {}
            cancelled = False
            for p in query.params:
                prompt = f"{p.name}"
                if p.description:
                    prompt += f" ({p.description})"
                val = text(message=f"  {prompt}:", default=p.default)
                if is_esc(val):
                    cancelled = True
                    break
                param_values[p.name] = val

            if cancelled:
                continue

            with console.status(f"Testando em {conn.name}..."):
                result = execute_query(query, conn, param_values)

            if result.success and result.rows:
                query.apply_column_maps(result.rows, result.columns)

            show_query_result(result)

            if not result.success:
                show_warning("A consulta retornou erro. Voce pode testar novamente, salvar mesmo assim ou descartar.")
            # Loop back to menu

        elif action == "save":
            existing.append(query)
            save_queries(existing)
            show_success(f'Consulta "{query.name}" salva!')
            return True


def _configure_column_maps(query: Query):
    """Configure column value mappings for a query (in-memory, not saved yet)."""
    cols = query.columns if query.columns else []
    if not cols:
        show_warning("Nenhuma coluna detectada. Salve e edite depois.")
        return

    while True:
        # Show current mappings
        if query.column_maps:
            console.print("\n[bold]Mapeamentos atuais:[/bold]")
            for col, mapping in query.column_maps.items():
                console.print(f"  [cyan]{col}[/cyan]:")
                for raw, label in mapping.items():
                    console.print(f"    '{raw}' -> '{label}'")
        else:
            console.print("\n[dim]Nenhum mapeamento configurado.[/dim]")

        action = select(
            message="Mapeamento:",
            choices=[
                {"name": "➕  Adicionar mapeamento", "value": "add"},
                {"name": "🗑️   Remover mapeamento de uma coluna", "value": "remove"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            break

        if action == "add":
            col = select(
                message="Coluna:",
                choices=[{"name": c, "value": c} for c in cols],
            )
            if is_esc(col):
                continue

            console.print(f"\n[dim]Mapeamento para [bold]{col}[/bold] (vazio para parar):[/dim]")
            if col not in query.column_maps:
                query.column_maps[col] = {}

            while True:
                raw = text(message="  Valor original (ex: PG):")
                if is_esc(raw) or not raw:
                    break
                label = text(message=f"  Exibir como:")
                if is_esc(label):
                    break
                query.column_maps[col][raw] = label
                show_success(f"'{raw}' -> '{label}'")

        elif action == "remove":
            mapped_cols = [c for c in query.column_maps if query.column_maps[c]]
            if not mapped_cols:
                show_warning("Nenhum mapeamento para remover.")
                continue
            col = select(
                message="Remover mapeamento de qual coluna?",
                choices=[{"name": f"{c} ({len(query.column_maps[c])} regras)", "value": c} for c in mapped_cols],
            )
            if is_esc(col):
                continue
            do_confirm = confirm(message=f'Remover todos os mapeamentos de "{col}"?', default=False)
            if not is_esc(do_confirm) and do_confirm:
                del query.column_maps[col]
                show_success(f'Mapeamentos de "{col}" removidos.')


def _edit_column_maps(queries: list[Query]):
    """Edit column value mappings for an existing saved query."""
    q = pick_entity(
        queries,
        formatter=lambda q: f"{q.name} ({q.connection})",
        message="Selecione a consulta:",
        empty_msg="Nenhuma consulta configurada.",
    )
    if q is None:
        return
    _configure_column_maps(q)
    save_queries(queries)
    show_success(f'Mapeamentos de "{q.name}" salvos!')


def _view_query(queries: list[Query]):
    q = pick_entity(
        queries,
        formatter=lambda q: f"{q.name} ({q.connection})",
        message="Selecione:",
        empty_msg="Nenhuma consulta para visualizar.",
    )
    if q is None:
        return
    console.print(f"\n[bold]{q.name}[/bold] ({q.connection} -> {q.table})")
    if q.params:
        console.print(f"Parametros: {', '.join(f':{p.name}' for p in q.params)}")
    console.print(f"\n[dim]{q.sql}[/dim]\n")


def _rename_query(queries: list[Query]):
    """Rename an existing query."""
    q = pick_entity(
        queries,
        formatter=lambda q: f"{q.name} ({q.connection})",
        message="Selecione:",
        empty_msg="Nenhuma consulta para renomear.",
    )
    if q is None:
        return
    old_name = q.name

    new_name = text(message="Novo nome:", default=old_name)
    if is_esc(new_name) or not new_name:
        return

    if new_name == old_name:
        show_warning("Nome nao alterado.")
        return

    if any(qq.name == new_name for qq in queries):
        show_error(f'Consulta "{new_name}" ja existe.')
        return

    q.name = new_name
    save_queries(queries)

    # Update groups that reference the old query name
    groups = load_groups()
    updated_groups = False
    for g in groups:
        if old_name in g.queries:
            g.queries = [new_name if qn == old_name else qn for qn in g.queries]
            updated_groups = True
    if updated_groups:
        save_groups(groups)
        show_info(f'Grupos atualizados para usar "{new_name}".')

    show_success(f'Consulta renomeada: "{old_name}" -> "{new_name}"')


def _duplicate_query(queries: list[Query]):
    q = pick_entity(
        queries,
        formatter=lambda q: f"{q.name} ({q.connection})",
        message="Selecione:",
        empty_msg="Nenhuma consulta para duplicar.",
    )
    if q is None:
        return
    new_name = text(message="Nome da copia:", default=f"{q.name}_copy")
    if is_esc(new_name) or not new_name:
        return

    if any(qq.name == new_name for qq in queries):
        show_error(f'Consulta "{new_name}" ja existe.')
        return

    # Optionally change connection
    change_conn = confirm(message="Alterar conexao?", default=False)
    if is_esc(change_conn):
        return
    conn_name = q.connection
    if change_conn:
        conn_name = _select_connection() or q.connection

    new_query = Query(
        name=new_name,
        connection=conn_name,
        sql=q.sql,
        table=q.table,
        description=q.description,
        params=[QueryParam(p.name, p.description, p.default) for p in q.params],
        columns=list(q.columns),
        order_by=q.order_by,
    )

    queries.append(new_query)
    save_queries(queries)
    show_success(f'Consulta "{new_name}" criada como copia de "{q.name}"!')


def _remove_query(queries: list[Query]):
    q = pick_entity(
        queries,
        formatter=lambda q: f"{q.name} ({q.connection})",
        message="Selecione:",
        empty_msg="Nenhuma consulta para remover.",
    )
    if q is None:
        return

    selected = q.name
    do_confirm = confirm(message=f'Remover consulta "{selected}"?', default=False)
    if is_esc(do_confirm) or not do_confirm:
        return

    new_queries = [q for q in queries if q.name != selected]
    save_queries(new_queries)
    show_success(f'Consulta "{selected}" removida!')
