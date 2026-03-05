"""Connection configuration wizard."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console

from dbqm.core.crypto import encrypt
from dbqm.core.db_manager import test_connection
from dbqm.models.connection import Connection, load_connections, save_connections
from dbqm.models.query import load_queries, save_queries
from dbqm.ui.display import show_success, show_error, show_warning
from dbqm.ui.helpers import pick_entity
from dbqm.ui.prompts import select, text, secret, confirm, is_esc, Separator

console = Console()

TNS_DEFAULT_PATH = str(Path(__file__).resolve().parent.parent.parent / "tns" / "tnsnames.ora")


def connection_wizard():
    """Main connection management menu."""
    while True:
        connections = load_connections()
        console.print("\n[bold cyan]═══ 🔌 Conexoes Configuradas ═══[/bold cyan]\n")

        if connections:
            from rich.table import Table
            table = Table(show_lines=False, border_style="dim")
            table.add_column("#", style="bold", width=4)
            table.add_column("Nome", style="white")
            table.add_column("Tipo", style="white")
            table.add_column("Destino", style="white")
            for i, c in enumerate(connections, 1):
                db_label = {"oracle": "Oracle", "sqlserver": "SQL Server",
                            "postgresql": "PostgreSQL", "mysql": "MySQL"}.get(c.db_type, c.db_type)
                if c.db_type == "oracle" and c.mode == "tns":
                    db_label = "Oracle/TNS"
                table.add_row(str(i), c.name, db_label, c.display_target())
            console.print(table)
        else:
            show_warning("Nenhuma conexao configurada.")

        console.print()
        action = select(
            message="Conexoes:",
            choices=[
                {"name": "➕  Nova conexao", "value": "new"},
                {"name": "🧪  Testar conexao", "value": "test"},
                Separator("─── Editar ─────────────────────"),
                {"name": "✏️   Editar conexao", "value": "edit"},
                {"name": "🏷️   Renomear conexao", "value": "rename"},
                Separator("────────────────────────────────"),
                {"name": "🗑️   Remover conexao", "value": "remove"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )

        if is_esc(action) or action == "back":
            break
        elif action == "new":
            _create_connection()
        elif action == "test":
            _test_existing_connection(connections)
        elif action == "edit":
            _edit_connection(connections)
        elif action == "rename":
            _rename_connection(connections)
        elif action == "remove":
            _remove_connection(connections)


def _create_connection():
    """Wizard to create a new connection."""
    console.print("\n[bold cyan]── ➕ Nova Conexao ──[/bold cyan]\n")

    name = text(message="Nome da conexao:")
    if is_esc(name) or not name:
        if not name and not is_esc(name):
            show_error("Nome obrigatorio.")
        return

    # Check duplicate
    existing = load_connections()
    if any(c.name == name for c in existing):
        show_error(f'Conexao "{name}" ja existe.')
        return

    db_type = select(
        message="Tipo de banco:",
        choices=[
            {"name": "Oracle", "value": "oracle"},
            {"name": "SQL Server", "value": "sqlserver"},
            {"name": "PostgreSQL", "value": "postgresql"},
            {"name": "MySQL", "value": "mysql"},
        ],
    )
    if is_esc(db_type):
        return

    if db_type == "oracle":
        conn = _create_oracle_connection(name)
    elif db_type == "sqlserver":
        conn = _create_sqlserver_connection(name)
    elif db_type == "postgresql":
        conn = _create_postgresql_connection(name)
    elif db_type == "mysql":
        conn = _create_mysql_connection(name)
    else:
        return

    if conn is None:
        return

    # Test connection?
    do_test = confirm(message="Testar conexao agora?", default=True)
    if is_esc(do_test):
        return
    if do_test:
        with console.status("Testando conexao..."):
            success, msg = test_connection(conn)
        if success:
            show_success(msg)
        else:
            show_error(msg)
            save_anyway = confirm(message="Salvar mesmo assim?", default=False)
            if is_esc(save_anyway) or not save_anyway:
                return

    existing.append(conn)
    save_connections(existing)
    show_success(f'Conexao "{name}" salva!')


def _create_oracle_connection(name: str) -> Connection | None:
    mode = select(
        message="Modo de conexao:",
        choices=[
            {"name": "TNS (tnsnames.ora)", "value": "tns"},
            {"name": "Conexao direta (host/port/service)", "value": "direct"},
        ],
    )
    if is_esc(mode):
        return None

    if mode == "tns":
        tns_path = text(message="Caminho do tnsnames.ora:", default=TNS_DEFAULT_PATH)
        if is_esc(tns_path):
            return None
        tns_name = text(message="Nome do TNS (service):")
        if is_esc(tns_name):
            return None
        user = text(message="Usuario:")
        if is_esc(user):
            return None
        password = secret(message="Senha:")
        if is_esc(password):
            return None

        return Connection(
            name=name,
            db_type="oracle",
            mode="tns",
            tns_path=tns_path,
            tns_name=tns_name,
            user=user,
            password=encrypt(password),
        )
    else:
        host = text(message="Host:")
        if is_esc(host):
            return None
        port = text(message="Porta:", default="1521")
        if is_esc(port):
            return None
        service_name = text(message="Service Name:")
        if is_esc(service_name):
            return None
        user = text(message="Usuario:")
        if is_esc(user):
            return None
        password = secret(message="Senha:")
        if is_esc(password):
            return None

        return Connection(
            name=name,
            db_type="oracle",
            mode="direct",
            host=host,
            port=int(port),
            service_name=service_name,
            user=user,
            password=encrypt(password),
        )


def _create_sqlserver_connection(name: str) -> Connection | None:
    host = text(message="Host:")
    if is_esc(host):
        return None
    port = text(message="Porta:", default="1433")
    if is_esc(port):
        return None
    database = text(message="Database:")
    if is_esc(database):
        return None
    user = text(message="Usuario:")
    if is_esc(user):
        return None
    password = secret(message="Senha:")
    if is_esc(password):
        return None

    return Connection(
        name=name,
        db_type="sqlserver",
        host=host,
        port=int(port),
        database=database,
        user=user,
        password=encrypt(password),
    )


def _create_postgresql_connection(name: str) -> Connection | None:
    host = text(message="Host:", default="localhost")
    if is_esc(host):
        return None
    port = text(message="Porta:", default="5432")
    if is_esc(port):
        return None
    database = text(message="Database:")
    if is_esc(database):
        return None
    user = text(message="Usuario:")
    if is_esc(user):
        return None
    password = secret(message="Senha:")
    if is_esc(password):
        return None

    return Connection(
        name=name,
        db_type="postgresql",
        host=host,
        port=int(port),
        database=database,
        user=user,
        password=encrypt(password),
    )


def _create_mysql_connection(name: str) -> Connection | None:
    host = text(message="Host:", default="localhost")
    if is_esc(host):
        return None
    port = text(message="Porta:", default="3306")
    if is_esc(port):
        return None
    database = text(message="Database:")
    if is_esc(database):
        return None
    user = text(message="Usuario:")
    if is_esc(user):
        return None
    password = secret(message="Senha:")
    if is_esc(password):
        return None

    return Connection(
        name=name,
        db_type="mysql",
        host=host,
        port=int(port),
        database=database,
        user=user,
        password=encrypt(password),
    )


def _test_existing_connection(connections: list[Connection]):
    conn = pick_entity(
        connections,
        formatter=lambda c: f"{c.name} ({c.db_type})",
        message="Selecione a conexao:",
        empty_msg="Nenhuma conexao para testar.",
    )
    if conn is None:
        return
    with console.status(f"Testando {conn.name}..."):
        success, msg = test_connection(conn)
    if success:
        show_success(msg)
    else:
        show_error(msg)


def _edit_connection(connections: list[Connection]):
    conn = pick_entity(
        connections,
        formatter=lambda c: f"{c.name} ({c.db_type})",
        message="Selecione a conexao:",
        empty_msg="Nenhuma conexao para editar.",
    )
    if conn is None:
        return
    console.print(f"\n[bold]Editando conexao: {conn.name}[/bold]")
    console.print("[dim]Pressione Enter para manter o valor atual | ESC para cancelar[/dim]\n")

    new_user = text(message="Usuario:", default=conn.user)
    if is_esc(new_user):
        return
    new_pass = secret(message="Senha (vazio para manter):")
    if is_esc(new_pass):
        return

    conn.user = new_user
    if new_pass:
        conn.password = encrypt(new_pass)

    if conn.db_type == "oracle" and conn.mode == "tns":
        new_tns = text(message="TNS Name:", default=conn.tns_name or "")
        if is_esc(new_tns):
            return
        conn.tns_name = new_tns
    elif conn.db_type == "oracle":
        h = text(message="Host:", default=conn.host or "")
        if is_esc(h):
            return
        conn.host = h
        p = text(message="Porta:", default=str(conn.port or 1521))
        if is_esc(p):
            return
        conn.port = int(p)
        s = text(message="Service:", default=conn.service_name or "")
        if is_esc(s):
            return
        conn.service_name = s
    elif conn.db_type in ("sqlserver", "postgresql", "mysql"):
        default_port = {"sqlserver": 1433, "postgresql": 5432, "mysql": 3306}[conn.db_type]
        h = text(message="Host:", default=conn.host or "")
        if is_esc(h):
            return
        conn.host = h
        p = text(message="Porta:", default=str(conn.port or default_port))
        if is_esc(p):
            return
        conn.port = int(p)
        d = text(message="Database:", default=conn.database or "")
        if is_esc(d):
            return
        conn.database = d

    save_connections(connections)
    show_success(f'Conexao "{conn.name}" atualizada!')


def _rename_connection(connections: list[Connection]):
    """Rename an existing connection."""
    conn = pick_entity(
        connections,
        formatter=lambda c: f"{c.name} ({c.db_type})",
        message="Selecione a conexao:",
        empty_msg="Nenhuma conexao para renomear.",
    )
    if conn is None:
        return
    old_name = conn.name

    new_name = text(message="Novo nome:", default=old_name)
    if is_esc(new_name) or not new_name:
        return

    if new_name == old_name:
        show_warning("Nome nao alterado.")
        return

    if any(c.name == new_name for c in connections):
        show_error(f'Conexao "{new_name}" ja existe.')
        return

    conn.name = new_name
    save_connections(connections)

    # Update queries that reference the old connection name
    queries = load_queries()
    updated_queries = False
    for q in queries:
        if q.connection == old_name:
            q.connection = new_name
            updated_queries = True
    if updated_queries:
        save_queries(queries)
        show_info_inline(f'Consultas atualizadas para usar "{new_name}".')

    show_success(f'Conexao renomeada: "{old_name}" -> "{new_name}"')


def show_info_inline(msg: str):
    console.print(f"  [cyan]💡[/cyan] {msg}")


def _remove_connection(connections: list[Connection]):
    conn = pick_entity(
        connections,
        formatter=lambda c: f"{c.name} ({c.db_type})",
        message="Selecione a conexao:",
        empty_msg="Nenhuma conexao para remover.",
    )
    if conn is None:
        return

    selected = conn.name
    do_confirm = confirm(message=f'Remover conexao "{selected}"?', default=False)
    if is_esc(do_confirm) or not do_confirm:
        return

    new_conns = [c for c in connections if c.name != selected]
    save_connections(new_conns)
    show_success(f'Conexao "{selected}" removida!')
