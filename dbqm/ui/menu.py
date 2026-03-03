"""Main interactive menu."""
from __future__ import annotations

from rich.console import Console

from dbqm.models.connection import load_connections
from dbqm.ui.display import clear_screen, show_banner, show_info
from dbqm.ui.prompts import select, is_esc
from dbqm.ui.config_wizard import connection_wizard
from dbqm.ui.query_wizard import query_wizard
from dbqm.ui.group_wizard import group_wizard
from dbqm.ui.flows.query_flow import execute_query_flow
from dbqm.ui.flows.group_flow import execute_group_flow
from dbqm.ui.flows.ddl_flow import extract_ddl_flow
from dbqm.ui.flows.adhoc_flow import adhoc_sql_flow
from dbqm.ui.flows.browse_flow import browse_tables_flow
from dbqm.ui.flows.config_flow import portability_flow

console = Console()


def main_menu():
    """Main application loop."""
    show_banner()

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
                {"name": "🗂️   Navegar tabelas", "value": "browse"},
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
            extract_ddl_flow()
        elif action == "exec_query":
            execute_query_flow()
        elif action == "exec_group":
            execute_group_flow()
        elif action == "adhoc_sql":
            adhoc_sql_flow()
        elif action == "browse":
            browse_tables_flow()


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
            portability_flow()
