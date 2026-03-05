"""Application settings flow."""
from __future__ import annotations

from rich.console import Console

from dbqm.models.settings import load_settings, save_settings
from dbqm.ui.display import show_success
from dbqm.ui.prompts import select, confirm, is_esc

console = Console()


def settings_flow():
    """Application settings menu."""
    settings = load_settings()

    while True:
        audit_status = "Ativado" if settings.audit_log_enabled else "Desativado"
        action = select(
            message="Configuracoes gerais:",
            choices=[
                {"name": f"📝  Log de auditoria: {audit_status}", "value": "audit"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )
        if is_esc(action) or action == "back":
            return

        if action == "audit":
            toggle = confirm(
                message=f"{'Desativar' if settings.audit_log_enabled else 'Ativar'} log de auditoria?",
                default=True,
            )
            if not is_esc(toggle) and toggle:
                settings.audit_log_enabled = not settings.audit_log_enabled
                save_settings(settings)
                status = "ativado" if settings.audit_log_enabled else "desativado"
                show_success(f"Log de auditoria {status}!")
