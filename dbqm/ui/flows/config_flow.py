"""Config portability flow (export/import)."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console

from dbqm.core.config_portability import export_configs, import_configs
from dbqm.ui.display import show_error, show_warning, show_success
from dbqm.ui.helpers import prompt_open_file
from dbqm.ui.prompts import select, text, secret, checkbox, is_esc

console = Console()


def portability_flow():
    """Export/Import configurations menu."""
    action = select(
        message="Exportar ou Importar?",
        choices=[
            {"name": "📤  Exportar configuracoes", "value": "export"},
            {"name": "📥  Importar configuracoes", "value": "import"},
            {"name": "📦  Exportar/Importar tudo", "value": "all"},
        ],
    )

    if is_esc(action):
        return

    if action == "export":
        _export_configs_flow()
    elif action == "import":
        _import_configs_flow()
    else:
        _all_portability_flow()


def _all_portability_flow():
    """Export or import all configurations at once."""
    action = select(
        message="Exportar ou Importar tudo?",
        choices=[
            {"name": "📤  Exportar tudo", "value": "export"},
            {"name": "📥  Importar tudo", "value": "import"},
        ],
    )

    if is_esc(action):
        return

    if action == "export":
        _export_all_flow()
    else:
        _import_configs_flow()


def _export_all_flow():
    """Export all configurations to a .dbqm file."""
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
            include_connections=True,
            include_queries=True,
            include_groups=True,
        )
        show_success(f"Todas as configuracoes exportadas: {path}")
        prompt_open_file(path)
    except Exception as e:
        show_error(f"Erro ao exportar: {e}")


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
        prompt_open_file(path)
    except Exception as e:
        show_error(f"Erro ao exportar: {e}")


def _import_configs_flow():
    """Import configurations from a .dbqm file."""
    filepath = text(message="Caminho do arquivo .dbqm:")
    if is_esc(filepath) or not filepath:
        return

    filepath = filepath.strip().strip('"').strip("'")

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
