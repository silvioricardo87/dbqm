"""Help overlay showing keyboard shortcuts."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from dbqm.i18n import t
from dbqm.ui.widgets.dialog import Dialog


def help_text() -> str:
    """The shortcut sheet.

    A function, not a constant: a constant is built as this module is
    imported, which is before the app resolves the language.

    The key column is padded to the widest key rather than to a count typed
    out, so a longer word in another language cannot push the descriptions
    out of line.
    """
    sections = [
        (t("shortcuts.section_general"), [
            ("Ctrl+B", t("shortcuts.toggle_sidebar")),
            ("Ctrl+Q", t("shortcuts.quit")),
            ("ESC", t("shortcuts.back")),
            ("/", t("shortcuts.search_filter")),
            ("?", t("shortcuts.this_help")),
        ]),
        (t("shortcuts.section_query_result"), [
            ("V", t("shortcuts.vertical_view")),
            ("E", t("shortcuts.export")),
            ("R", t("shortcuts.rerun")),
        ]),
        (t("shortcuts.section_group_result"), [
            ("F", t("shortcuts.flat_pivoted")),
            ("S", t("shortcuts.filter_status")),
            ("E", t("shortcuts.export")),
            ("H", t("shortcuts.html_report")),
            ("I", t("shortcuts.view_individual")),
            ("R", t("shortcuts.rerun")),
        ]),
    ]
    width = max(len(key_name) for _, shortcuts in sections for key_name, _ in shortcuts)
    lines: list[str] = []
    for title, shortcuts in sections:
        lines.append(f"[bold $ds-text-strong]{title}[/]")
        lines.extend(f"  {key_name.ljust(width)}  {description}"
                      for key_name, description in shortcuts)
        lines.append("")
    lines.append(f'[dim]{t("shortcuts.dismiss")}[/dim]')
    return "\n".join(lines)


class HelpModal(ModalScreen[None]):
    """Displays keyboard shortcuts in a modal overlay."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }

    HelpModal #help-dialog {
        overflow-y: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_help", "Close", show=False),
        Binding("enter", "dismiss_help", "Close", show=False),
        Binding("question_mark", "dismiss_help", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Dialog(t("shortcuts.title"), width="sm", id="help-dialog"):
            yield Static(help_text(), markup=True)

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
