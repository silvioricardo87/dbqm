"""Main interactive menu."""
from __future__ import annotations

from rich.console import Console

from dbqm.models.connection import load_connections
from dbqm.ui.display import clear_screen, show_banner, show_info
from dbqm.ui.prompts import select, is_esc, Separator
from dbqm.ui.config_wizard import connection_wizard
from dbqm.ui.query_wizard import query_wizard
from dbqm.ui.group_wizard import group_wizard
from dbqm.ui.flows.query_flow import execute_query_flow
from dbqm.ui.flows.group_flow import execute_group_flow
from dbqm.ui.flows.ddl_flow import extract_ddl_flow
from dbqm.ui.flows.adhoc_flow import adhoc_sql_flow
from dbqm.ui.flows.object_browser_flow import object_browser_flow
from dbqm.ui.flows.config_flow import portability_flow
from dbqm.ui.flows.history_flow import history_flow
from dbqm.ui.flows.settings_flow import settings_flow

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
            message="O que deseja fazer?",
            choices=[
                Separator("─── Consultas ──────────────────"),
                {"name": "🔍  Executar consulta salva", "value": "exec_query"},
                {"name": "⌨️   SQL avulso", "value": "adhoc_sql"},
                {"name": "📝  Gerenciar consultas", "value": "config_query"},
                Separator("─── Grupos ─────────────────────"),
                {"name": "📊  Executar grupo comparativo", "value": "exec_group"},
                {"name": "📁  Gerenciar grupos", "value": "config_group"},
                Separator("─── Ferramentas ────────────────"),
                {"name": "🏗️   Extrair DDL de objeto", "value": "extract_ddl"},
                {"name": "🗂️   Navegar objetos do banco", "value": "browse"},
                {"name": "📜  Historico de execucoes", "value": "history"},
                Separator("─── Sistema ────────────────────"),
                {"name": "🔌  Conexoes", "value": "config_conn"},
                {"name": "📦  Exportar / Importar", "value": "portability"},
                {"name": "🛠️   Preferencias", "value": "settings"},
                {"name": "🚪  Sair", "value": "exit"},
            ],
        )

        if is_esc(action) or action == "exit":
            clear_screen()
            console.print("[dim]Ate logo![/dim]\n")
            break
        elif action == "exec_query":
            execute_query_flow()
        elif action == "adhoc_sql":
            adhoc_sql_flow()
        elif action == "config_query":
            query_wizard()
        elif action == "exec_group":
            execute_group_flow()
        elif action == "config_group":
            group_wizard()
        elif action == "extract_ddl":
            extract_ddl_flow()
        elif action == "browse":
            object_browser_flow()
        elif action == "history":
            history_flow()
        elif action == "config_conn":
            connection_wizard()
        elif action == "portability":
            portability_flow()
        elif action == "settings":
            settings_flow()
