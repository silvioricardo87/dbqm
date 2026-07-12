"""Collapsible Templates sidebar (Ctrl+B). Choosing a template emits its SQL."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option


class TemplatesSidebar(Vertical):
    """Collapsible sidebar listing saved SQL templates.

    Starts collapsed so the app opens clean; toggled open with Ctrl+B. When
    open with no saved templates, shows a hint instead of a blank panel.
    """

    DEFAULT_CSS = """
    TemplatesSidebar {
        width: 26;
        border-right: solid $border;
        background: $panel;
        padding: 0;
    }
    TemplatesSidebar.-collapsed { display: none; }
    TemplatesSidebar > #tpl-title {
        height: auto; background: $surface; color: $accent; text-style: bold;
        border-bottom: solid $border; padding: 0 1;
    }
    TemplatesSidebar OptionList { border: none; background: $panel; height: 1fr; }
    TemplatesSidebar > #tpl-empty {
        height: 1fr; padding: 1 1; color: $text-muted;
    }
    """

    class TemplateChosen(Message):
        """Posted when a template is selected; carries its SQL content."""

        def __init__(self, sql: str) -> None:
            self.sql = sql
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("📄  TEMPLATES", id="tpl-title")
        yield OptionList(id="tpl-list")
        yield Static(
            "Nenhum template salvo.\n\nCrie templates na aba Ferramentas para\nreutiliza-los aqui.",
            id="tpl-empty",
        )

    def on_mount(self) -> None:
        # Start collapsed — the app opens clean; Ctrl+B reveals the sidebar.
        self.add_class("-collapsed")
        self._reload()

    def _reload(self) -> None:
        ol = self.query_one("#tpl-list", OptionList)
        ol.clear_options()
        self._sqls: dict[str, str] = {}
        count = 0
        try:
            from dbqm.models.template import load_templates

            for t in load_templates():
                self._sqls[t.name] = t.content
                ol.add_option(Option(f"📄  {t.name}", id=t.name))
                count += 1
        except Exception:
            pass
        # Show the hint only when there are no templates.
        self.query_one("#tpl-empty", Static).display = count == 0
        ol.display = count > 0

    def toggle(self) -> None:
        """Collapse or expand the sidebar."""
        self.toggle_class("-collapsed")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        sql = self._sqls.get(str(event.option.id), "")
        if sql:
            self.post_message(self.TemplateChosen(sql))
