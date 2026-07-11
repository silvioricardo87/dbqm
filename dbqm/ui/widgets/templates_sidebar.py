"""Collapsible Templates sidebar (Ctrl+B). Choosing a template emits its SQL."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option


class TemplatesSidebar(Vertical):
    """Collapsible sidebar listing saved SQL templates."""

    DEFAULT_CSS = """
    TemplatesSidebar {
        width: 26;
        border-right: solid $border;
        background: $panel;
        padding: 0;
    }
    TemplatesSidebar.-collapsed { display: none; }
    TemplatesSidebar > #tpl-title {
        height: 1; background: $surface; color: $accent; text-style: bold;
        border-bottom: solid $border; padding: 0 1;
    }
    TemplatesSidebar OptionList { border: none; background: $panel; height: 1fr; }
    """

    class TemplateChosen(Message):
        """Posted when a template is selected; carries its SQL content."""

        def __init__(self, sql: str) -> None:
            self.sql = sql
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("📄  TEMPLATES", id="tpl-title")
        yield OptionList(id="tpl-list")

    def on_mount(self) -> None:
        self._reload()

    def _reload(self) -> None:
        ol = self.query_one("#tpl-list", OptionList)
        ol.clear_options()
        self._sqls: dict[str, str] = {}
        try:
            from dbqm.models.template import load_templates

            for t in load_templates():
                self._sqls[t.name] = t.content
                ol.add_option(Option(f"📄  {t.name}", id=t.name))
        except Exception:
            pass

    def toggle(self) -> None:
        """Collapse or expand the sidebar."""
        self.toggle_class("-collapsed")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        sql = self._sqls.get(str(event.option.id), "")
        if sql:
            self.post_message(self.TemplateChosen(sql))
