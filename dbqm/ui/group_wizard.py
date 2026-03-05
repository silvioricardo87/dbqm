"""Group configuration wizard."""
from __future__ import annotations

from rich.console import Console
from rich.table import Table

from dbqm.models.query import load_queries
from dbqm.models.group import Group, load_groups, save_groups
from dbqm.ui.display import show_success, show_error, show_warning
from dbqm.ui.helpers import pick_entity
from dbqm.ui.prompts import select, checkbox, text, confirm, is_esc

console = Console()


def group_wizard():
    """Main group management menu."""
    while True:
        groups = load_groups()
        console.print("\n[bold cyan]═══ 📁 Grupos de Consultas ═══[/bold cyan]\n")

        if groups:
            table = Table(show_lines=False, border_style="dim")
            table.add_column("#", style="bold", width=4)
            table.add_column("Nome", style="white")
            table.add_column("Consultas", style="white")
            table.add_column("Chave", style="white")
            table.add_column("Comparar", style="dim")
            for i, g in enumerate(groups, 1):
                table.add_row(
                    str(i),
                    g.name,
                    ", ".join(g.queries),
                    g.join_key,
                    ", ".join(g.compare_columns),
                )
            console.print(table)
        else:
            show_warning("Nenhum grupo configurado.")

        console.print()
        action = select(
            message="Acao:",
            choices=[
                {"name": "➕  Novo grupo", "value": "new"},
                {"name": "✏️   Editar grupo", "value": "edit"},
                {"name": "🗑️   Remover grupo", "value": "remove"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            break
        elif action == "new":
            _create_group()
        elif action == "edit":
            _edit_group(groups)
        elif action == "remove":
            _remove_group(groups)


def _create_group():
    """Create a new query group."""
    queries = load_queries()
    if len(queries) < 2:
        show_error("E necessario ter ao menos 2 consultas configuradas para criar um grupo.")
        return

    console.print("\n[bold cyan]── ➕ Novo Grupo ──[/bold cyan]\n")

    name = text(message="Nome do grupo:")
    if is_esc(name) or not name:
        if not name and not is_esc(name):
            show_error("Nome obrigatorio.")
        return

    existing = load_groups()
    if any(g.name == name for g in existing):
        show_error(f'Grupo "{name}" ja existe.')
        return

    description = text(message="Descricao:")
    if is_esc(description):
        return

    # Select queries
    query_choices = [{"name": f"{q.name} ({q.connection} -> {q.table})", "value": q.name} for q in queries]

    console.print("\n[dim]Selecione as consultas do grupo (minimo 2, use Espaco para marcar):[/dim]")
    selected_queries = checkbox(message="Consultas:", choices=query_choices)
    if is_esc(selected_queries):
        return

    if len(selected_queries) < 2:
        show_error("Selecione ao menos 2 consultas.")
        return

    # Detect shared params
    selected_query_objs = [q for q in queries if q.name in selected_queries]
    all_params: dict[str, set] = {}
    for q in selected_query_objs:
        for p in q.params:
            if p.name not in all_params:
                all_params[p.name] = set()
            all_params[p.name].add(q.name)

    shared_params = {}
    for param_name, query_set in all_params.items():
        if len(query_set) >= 2:
            console.print(f"\n  Parametro [bold]:{param_name}[/bold] presente em: {', '.join(query_set)}")
            share = confirm(
                message=f"Compartilhar :{param_name} entre as consultas?",
                default=True,
            )
            if is_esc(share):
                return
            if share:
                desc = text(message=f"Descricao de :{param_name}:")
                if is_esc(desc):
                    return
                # Use first default found
                default = ""
                for q in selected_query_objs:
                    for p in q.params:
                        if p.name == param_name and p.default:
                            default = p.default
                            break
                    if default:
                        break
                default_val = text(message="Valor padrao:", default=default)
                if is_esc(default_val):
                    return
                shared_params[param_name] = {"description": desc or "", "default": default_val or ""}

    # Join key
    console.print("\n[dim]Coluna-chave para cruzar os resultados (ex: parcela):[/dim]")
    all_cols = set()
    for q in selected_query_objs:
        all_cols.update(q.columns)

    join_key = text(
        message="Coluna-chave:",
        completer={c: None for c in all_cols},
    )
    if is_esc(join_key) or not join_key:
        if not join_key and not is_esc(join_key):
            show_error("Coluna-chave obrigatoria.")
        return

    # Compare columns
    console.print("\n[dim]Colunas para comparacao (vazio para todas):[/dim]")
    compare_columns = []
    remaining = sorted(all_cols - {join_key})
    while True:
        col = text(
            message="  comparar:",
            completer={c: None for c in remaining},
        )
        if is_esc(col):
            return
        if not col:
            break
        compare_columns.append(col)
        if col in remaining:
            remaining.remove(col)

    if not compare_columns:
        compare_columns = sorted(all_cols - {join_key})
        console.print(f"  Usando todas as colunas: {', '.join(compare_columns)}")

    # Column mapping (if column names differ between queries)
    column_mapping = {}
    for col in compare_columns:
        needs_mapping = False
        for q in selected_query_objs:
            if col not in q.columns:
                needs_mapping = True
                break

        if needs_mapping:
            console.print(f"\n  Coluna [bold]{col}[/bold] nao existe em todas as consultas.")
            mapping = {}
            for q in selected_query_objs:
                if col in q.columns:
                    mapping[q.name] = col
                else:
                    # Auto-suggest based on position
                    suggested = ""
                    ref_query = next((rq for rq in selected_query_objs if col in rq.columns), None)
                    if ref_query and col in ref_query.columns:
                        col_idx = ref_query.columns.index(col)
                        if col_idx < len(q.columns):
                            suggested = q.columns[col_idx]

                    mapped = text(
                        message=f"  Em {q.name}, qual coluna corresponde a '{col}'?",
                        default=suggested,
                        completer={c: None for c in q.columns},
                    )
                    if is_esc(mapped):
                        return
                    mapping[q.name] = mapped
            column_mapping[col] = mapping

    # Normalization
    setup_norm = confirm(
        message="Configurar normalizacao de valores? (ex: 'paga' = 'pago')",
        default=False,
    )
    if is_esc(setup_norm):
        return

    normalize = {}
    if setup_norm:
        for col in compare_columns:
            console.print(f"\n  Normalizacao para [bold]{col}[/bold] (vazio para parar):")
            col_norm = {}
            while True:
                from_val = text(message="    De (valor original):")
                if is_esc(from_val):
                    return
                if not from_val:
                    break
                to_val = text(message="    Para (valor normalizado):")
                if is_esc(to_val):
                    return
                col_norm[from_val] = to_val
            if col_norm:
                normalize[col] = col_norm

    # Validation rule
    validation = select(
        message="Regra de validacao:",
        choices=[
            {"name": "Todas iguais (todas devem retornar o mesmo valor)", "value": "all_equal"},
            {"name": "Nenhuma (apenas exibir comparativo)", "value": "none"},
        ],
    )
    if is_esc(validation):
        return

    group = Group(
        name=name,
        description=description or "",
        queries=selected_queries,
        join_key=join_key,
        compare_columns=compare_columns,
        shared_params=shared_params,
        column_mapping=column_mapping,
        normalize=normalize,
        validation_rule=validation,
    )

    existing.append(group)
    save_groups(existing)
    show_success(f'Grupo "{name}" salvo!')


def _edit_group(groups: list[Group]):
    group = pick_entity(
        groups,
        formatter=lambda g: g.name,
        message="Selecione:",
        empty_msg="Nenhum grupo para editar.",
    )
    if group is None:
        return

    console.print(f"\n[bold]Editando grupo: {group.name}[/bold]")

    # Edit normalization
    edit_norm = confirm(message="Editar normalizacao de valores?", default=True)
    if is_esc(edit_norm):
        return

    if edit_norm:
        for col in group.compare_columns:
            existing_norm = group.normalize.get(col, {})
            if existing_norm:
                console.print(f"\n  Normalizacao atual para [bold]{col}[/bold]:")
                for k, v in existing_norm.items():
                    console.print(f"    '{k}' -> '{v}'")

            console.print(f"\n  Adicionar normalizacao para [bold]{col}[/bold] (vazio para parar):")
            while True:
                from_val = text(message="    De:")
                if is_esc(from_val):
                    return
                if not from_val:
                    break
                to_val = text(message="    Para:")
                if is_esc(to_val):
                    return
                if col not in group.normalize:
                    group.normalize[col] = {}
                group.normalize[col][from_val] = to_val

    save_groups(groups)
    show_success(f'Grupo "{group.name}" atualizado!')


def _remove_group(groups: list[Group]):
    group = pick_entity(
        groups,
        formatter=lambda g: g.name,
        message="Selecione:",
        empty_msg="Nenhum grupo para remover.",
    )
    if group is None:
        return

    selected = group.name
    do_confirm = confirm(message=f'Remover grupo "{selected}"?', default=False)
    if is_esc(do_confirm) or not do_confirm:
        return

    new_groups = [g for g in groups if g.name != selected]
    save_groups(new_groups)
    show_success(f'Grupo "{selected}" removido!')
