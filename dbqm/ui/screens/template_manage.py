"""Template management screen — CRUD for report templates."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.widgets import Button, DataTable, Input, Static, TextArea

from dbqm.i18n import t
from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.dialog import Dialog
from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.panel import Panel


# ---------------------------------------------------------------------------
# Modal: Template create / edit
# ---------------------------------------------------------------------------

class TemplateEditModal(ModalScreen[dict | None]):
    """Modal for creating or editing a template."""

    DEFAULT_CSS = """
    TemplateEditModal {
        align: center middle;
    }
    TemplateEditModal Input {
        width: 100%;
        margin-bottom: 1;
    }
    TemplateEditModal #hint {
        margin-bottom: 1;
        color: $text-muted;
    }
    TemplateEditModal TextArea {
        height: 1fr;
        margin-bottom: 1;
    }
    TemplateEditModal #buttons {
        margin-top: 1;
        width: 100%;
        height: auto;
        align: center middle;
    }
    TemplateEditModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(
        self,
        title: str = "Novo Template",
        name_value: str = "",
        description_value: str = "",
        content_value: str = "",
        name_readonly: bool = False,
    ) -> None:
        super().__init__()
        self._title_text = title
        self._name_value = name_value
        self._description_value = description_value
        self._content_value = content_value
        self._name_readonly = name_readonly

    def compose(self) -> ComposeResult:
        with Dialog(self._title_text, width="screen", id="dialog"):
            yield Input(
                value=self._name_value,
                placeholder=t("template_manage.name_placeholder"),
                id="name-input",
                disabled=self._name_readonly,
            )
            yield Input(
                value=self._description_value,
                placeholder=t("common.description_optional"),
                id="desc-input",
            )
            yield Static(
                f'[dim]{t("template_manage.placeholder_hint")}[/dim]',
                id="hint",
                markup=True,
            )
            yield TextArea(self._content_value, id="content-area", language="markdown")
            with Horizontal(id="buttons"):
                yield Button(t("common.save"), variant="primary", id="save")
                yield Button(t("common.cancel"), variant="default", id="cancel")

    def on_mount(self) -> None:
        if not self._name_readonly:
            self.query_one("#name-input", Input).focus()
        else:
            self.query_one("#content-area", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def _save(self) -> None:
        name = self.query_one("#name-input", Input).value.strip()
        description = self.query_one("#desc-input", Input).value.strip()
        content = self.query_one("#content-area", TextArea).text

        from dbqm.core.template_builder import validate

        errors = validate({"name": name, "description": description, "content": content})
        if errors:
            self.notify(errors[0], severity="warning")
            return

        self.dismiss({
            "name": name,
            "description": description,
            "content": content,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Main screen
# ---------------------------------------------------------------------------

class TemplateManageScreen(Vertical):
    """Screen widget for managing templates (CRUD)."""

    DEFAULT_CSS = """
    TemplateManageScreen {
        height: 1fr;
    }
    TemplateManageScreen #tm-panel {
        margin: 1 2;
    }
    TemplateManageScreen #tm-empty {
        height: 1fr;
    }
    TemplateManageScreen DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        with Panel(t("panel.templates"), id="tm-panel"):
            yield EmptyState(
                what=t("template.list_title"),
                why=t("template_manage.empty_why"),
                action_label=t("template_manage.create"),
                action_id="create-template",
                id="tm-empty",
            )
            yield DataTable(id="tm-table")

    def on_mount(self) -> None:
        self._setup_table()
        self._load_templates()
        self._set_actions()
        self.call_after_refresh(self._set_initial_focus)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-template":
            self._handle_new()

    def _set_initial_focus(self) -> None:
        table = self.query_one("#tm-table", DataTable)
        if table.display:
            table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "tm-table":
            self._handle_edit()

    def _setup_table(self) -> None:
        table = self.query_one("#tm-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "Nome", "Descricao", "Campos")

    def _load_templates(self) -> None:
        from dbqm.models.template import load_templates
        from dbqm.core.template_engine import extract_placeholders

        templates = load_templates()
        table = self.query_one("#tm-table", DataTable)
        empty_msg = self.query_one("#tm-empty", EmptyState)

        table.clear()

        if not templates:
            empty_msg.display = True
            table.display = False
            return

        empty_msg.display = False
        table.display = True

        sorted_templates = sorted(templates, key=lambda t: t.name.lower())

        for i, t in enumerate(sorted_templates, 1):
            placeholders = extract_placeholders(t.content)
            fields_str = ", ".join(placeholders[:5])
            if len(placeholders) > 5:
                fields_str += f" (+{len(placeholders) - 5})"
            table.add_row(
                str(i),
                t.name,
                (t.description[:40] if t.description else ""),
                fields_str,
            )

    def _set_actions(self) -> None:
        try:
            action_bar = self.app.query_one(ActionBar)
        except Exception:
            return
        actions = [
            Action(t("action.new_template"), "N", "tm_new"),
            Action(t("action.edit"), "E", "tm_edit"),
            Action(t("action.rename"), "R", "tm_rename"),
            Action(t("action.remove"), "D", "tm_remove"),
        ]
        action_bar.set_actions(actions)

    def _get_selected_name(self) -> str | None:
        table = self.query_one("#tm-table", DataTable)
        if not table.display or table.row_count == 0:
            return None
        try:
            row_key = table.cursor_row
            row = table.get_row_at(row_key)
            return str(row[1])
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id
        handler = {
            "tm_new": self._handle_new,
            "tm_edit": self._handle_edit,
            "tm_rename": self._handle_rename,
            "tm_remove": self._handle_remove,
        }.get(action)
        if handler:
            handler()

    # -- New --

    def _handle_new(self) -> None:
        modal = TemplateEditModal(title=t("template_manage.new_title"))
        self.app.push_screen(modal, callback=self._on_new_result)

    def _on_new_result(self, result: dict | None) -> None:
        if result is None:
            return

        from dbqm.core.template_builder import build
        from dbqm.models.template import load_templates, save_templates

        templates = load_templates()

        if any(t.name == result["name"] for t in templates):
            self.notify(t("template.already_exists", name=result["name"]), severity="error")
            return

        template = build(result)
        templates.append(template)
        save_templates(templates)
        self._load_templates()
        self.notify(t("template_manage.created", name=template.name))

    # -- Edit --

    def _handle_edit(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify(t("template_manage.select_one"), severity="warning")
            return

        from dbqm.models.template import find_template

        template = find_template(name)
        if template is None:
            self.notify(t("template.not_found_named", name=name), severity="error")
            return

        self._edit_template_name = name
        modal = TemplateEditModal(
            title=t("template_manage.edit_title", name=name),
            name_value=template.name,
            description_value=template.description,
            content_value=template.content,
            name_readonly=True,
        )
        self.app.push_screen(modal, callback=self._on_edit_result)

    def _on_edit_result(self, result: dict | None) -> None:
        if result is None:
            return

        from dbqm.core.template_builder import build
        from dbqm.models.template import load_templates, save_templates

        templates = load_templates()
        for i, t in enumerate(templates):
            if t.name == self._edit_template_name:
                templates[i] = build(result, existing=t)
                break
        save_templates(templates)
        self._load_templates()
        self.notify(t("template_manage.updated", name=self._edit_template_name))

    # -- Rename --

    def _handle_rename(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify(t("template_manage.select_one"), severity="warning")
            return

        from dbqm.ui.modals.text_input import TextInputModal

        self._rename_old_name = name
        modal = TextInputModal(
            title=t("template_manage.rename_title"),
            message=t("common.new_name_for", name=name),
            default=name,
        )
        self.app.push_screen(modal, callback=self._on_rename_result)

    def _on_rename_result(self, new_name: str | None) -> None:
        if new_name is None or not new_name.strip():
            return

        new_name = new_name.strip()
        old_name = self._rename_old_name

        if new_name == old_name:
            return

        from dbqm.models.template import load_templates, save_templates

        templates = load_templates()

        if any(t.name == new_name for t in templates):
            self.notify(t("template.already_exists", name=new_name), severity="error")
            return

        for t in templates:
            if t.name == old_name:
                t.name = new_name
                break
        save_templates(templates)
        self._load_templates()
        self.notify(t("template_manage.renamed", old=old_name, new=new_name))

    # -- Remove --

    def _handle_remove(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify(t("template_manage.select_one"), severity="warning")
            return

        from dbqm.ui.modals.confirm import ConfirmModal

        self._remove_name = name
        modal = ConfirmModal(message=t("template_manage.confirm_remove", name=name))
        self.app.push_screen(modal, callback=self._on_remove_result)

    def _on_remove_result(self, confirmed: bool) -> None:
        if not confirmed:
            return

        from dbqm.models.template import delete_template

        name = self._remove_name
        if delete_template(name):
            self._load_templates()
            self.notify(t("template_manage.removed", name=name))
        else:
            self.notify(t("template.not_found_named", name=name), severity="error")
