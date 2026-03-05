"""DDL extraction flow."""
from __future__ import annotations

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn

from dbqm.core.ddl_extractor import (
    extract_ddl, save_extraction,
    extract_routine, save_routine_extraction,
    extract_dependencies_ddl, save_dependencies_extraction,
)
from dbqm.models.connection import load_connections, find_connection
from dbqm.ui.display import show_error, show_warning, show_success
from dbqm.ui.helpers import prompt_open_file
from dbqm.ui.prompts import select, text, confirm, is_esc

console = Console()


def _prompt_and_export_deps(
    conn, dependencies: list[str], extract_label: str, output_dir: str, file_num: int,
) -> None:
    """Offer to export dependency DDL into the same output directory."""
    if not dependencies:
        return
    console.print()
    export_deps = confirm(
        message="Deseja exportar a estrutura (DDL) dos objetos dependentes? (tabelas, views, indices, etc.)",
        default=False,
    )
    if is_esc(export_deps) or not export_deps:
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Iniciando...", total=None)

        def _on_progress(current: int, total: int, dep_type: str, dep_name: str):
            progress.update(task, total=total, completed=current - 1,
                            description=f"[{current}/{total}] {dep_type} {dep_name}")

        dep_result = extract_dependencies_ddl(conn, dependencies, extract_label, on_progress=_on_progress)
        progress.update(task, completed=progress.tasks[0].total)

    if not dep_result.objects:
        show_warning("Nenhuma dependencia pôde ser extraida.")
        return

    dep_filepath = save_dependencies_extraction(dep_result, output_dir, file_num)

    dep_counts: dict[str, int] = {}
    for obj in dep_result.objects:
        base_type = obj.obj_type.split("(")[0].strip()
        dep_counts[base_type] = dep_counts.get(base_type, 0) + 1

    console.print()
    console.rule("[bold cyan]📦  DEPENDENCIAS[/bold cyan]", style="cyan")
    for obj_type, count in dep_counts.items():
        console.print(f"  [green]✅[/green] {obj_type}: {count}")

    if dep_result.errors:
        console.print()
        for err in dep_result.errors:
            show_warning(err)

    console.print()
    show_success(f"Arquivo salvo: {dep_filepath}")


def extract_ddl_flow():
    """Flow to extract DDL from a database object."""
    connections = load_connections()
    supported_conns = [c for c in connections if c.db_type in ("oracle", "postgresql", "mysql")]
    if not supported_conns:
        show_warning("Nenhuma conexao Oracle, PostgreSQL ou MySQL configurada.")
        return

    choices = [
        {"name": f"{c.name} ({c.db_type} - {c.display_target()})", "value": c.name}
        for c in supported_conns
    ]
    selected = select(message="Selecione a conexao:", choices=choices)
    if is_esc(selected):
        return

    conn = find_connection(selected)
    if not conn:
        show_error("Conexao nao encontrada.")
        return

    object_name = text(message="Nome do objeto (ex: tabela, view, rotina):")
    if is_esc(object_name) or not object_name.strip():
        return

    obj_input = object_name.strip()

    if conn.db_type == "oracle":
        obj_input = obj_input.upper()
        if "." in obj_input:
            pkg_name, routine_name = obj_input.split(".", 1)
            _extract_routine_flow(conn, pkg_name, routine_name)
        else:
            _extract_full_ddl_flow(conn, obj_input)
    elif conn.db_type in ("postgresql", "mysql"):
        _extract_generic_ddl_flow(conn, obj_input)


def _extract_full_ddl_flow(conn, object_name: str):
    """Extract full DDL for an object."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Detectando {object_name}...", total=None)

        def _on_progress(current: int, total: int, obj_type: str, obj_name: str):
            progress.update(task, total=total, completed=current - 1,
                            description=f"[{current}/{total}] {obj_type} {obj_name}")

        result = extract_ddl(conn, object_name, on_progress=_on_progress)
        if progress.tasks[0].total:
            progress.update(task, completed=progress.tasks[0].total)

    if result.errors and not result.objects:
        for err in result.errors:
            show_error(err)
        return

    dir_path, next_num = save_extraction(result)

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
    console.print(f"  [bold]📂 Arquivos gerados:[/bold]")
    for f in result.saved_files:
        console.print(f"    [dim]•[/dim] {f}")
    console.print()
    show_success(f"Diretorio: {dir_path}")
    prompt_open_file(dir_path)
    _prompt_and_export_deps(conn, result.dependencies, result.object_name, dir_path, next_num)
    console.print()


def _extract_routine_flow(conn, pkg_name: str, routine_name: str):
    """Extract a specific routine from a package with its dependencies."""
    with console.status(f"Extraindo {pkg_name}.{routine_name}..."):
        result = extract_routine(conn, pkg_name, routine_name)

    if result.errors and not result.body_routines:
        for err in result.errors:
            show_error(err)
        return

    dir_path, next_num = save_routine_extraction(result)

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
    prompt_open_file(dir_path)
    _prompt_and_export_deps(
        conn, result.dependencies,
        f"{pkg_name}.{routine_name}",
        dir_path, next_num,
    )
    console.print()


def _extract_generic_ddl_flow(conn, object_name: str):
    """Extract DDL for PostgreSQL or MySQL objects."""
    from dbqm.core.db_manager import get_connection
    from dbqm.core.ddl_extractor import ExtractionResult, save_extraction

    db = None
    try:
        with console.status(f"Conectando e extraindo {object_name}..."):
            db = get_connection(conn)
            result = ExtractionResult(
                object_name=object_name, object_type="UNKNOWN",
                owner="", connection_name=conn.name,
            )

            if conn.db_type == "postgresql":
                from dbqm.core.ddl_pg import extract_pg_ddl
                extract_pg_ddl(db, object_name, result)
            else:
                from dbqm.core.ddl_mysql import extract_mysql_ddl
                extract_mysql_ddl(db, object_name, result)

        if result.errors and not result.objects:
            for err in result.errors:
                show_error(err)
            return

        dir_path, _ = save_extraction(result)

        console.print()
        console.rule("[bold cyan]🏗️  EXTRACAO DDL[/bold cyan]", style="cyan")
        console.print(f"  [bold]📦 Objeto:[/bold] {result.object_name}")
        console.print(f"  [bold]🏷️  Tipo:[/bold] {result.object_type}")
        console.print(f"  [bold]🔌 Conexao:[/bold] {result.connection_name}")
        console.print()

        for obj in result.objects:
            console.print(f"  [green]✅[/green] {obj.obj_type}: {obj.name}")

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
        prompt_open_file(dir_path)
        console.print()

    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
