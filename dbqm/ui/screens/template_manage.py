"""Template management screen — CRUD for report templates."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.widgets import Button, DataTable, Input, Static, TextArea

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.dialog import Dialog


# ---------------------------------------------------------------------------
# Modal: Template create / edit
# ---------------------------------------------------------------------------

class TemplateEditModal(ModalScreen[dict | None]):
    """Modal for creating or editing a template."""

    DEFAULT_CSS = """
    TemplateEditModal {
        align: center middle;
    }
    TemplateEditModal #dialog {
        height: 85%;
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
        with Dialog(self._title_text, largura="lg", id="dialog"):
            yield Input(
                value=self._name_value,
                placeholder="Nome do template",
                id="name-input",
                disabled=self._name_readonly,
            )
            yield Input(
                value=self._description_value,
                placeholder="Descricao (opcional)",
                id="desc-input",
            )
            yield Static(
                "[dim]Use {{campo}} para placeholders. Ex: {{titulo}}, {{analise}}, {{etapa_1}}[/dim]",
                id="hint",
                markup=True,
            )
            yield TextArea(self._content_value, id="content-area", language="markdown")
            with Horizontal(id="buttons"):
                yield Button("Salvar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

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
        if not name:
            self.notify("Informe o nome do template.", severity="warning")
            return

        content = self.query_one("#content-area", TextArea).text
        if not content.strip():
            self.notify("O conteudo do template nao pode estar vazio.", severity="warning")
            return

        description = self.query_one("#desc-input", Input).value.strip()

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
    TemplateManageScreen #tm-empty {
        height: 1fr;
        content-align: center middle;
        text-align: center;
    }
    TemplateManageScreen DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "[dim]Nenhum template configurado[/]",
            id="tm-empty",
            markup=True,
        )
        yield DataTable(id="tm-table")

    def on_mount(self) -> None:
        self._setup_table()
        self._load_templates()
        self._set_actions()
        self.call_after_refresh(self._set_initial_focus)

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
        empty_msg = self.query_one("#tm-empty", Static)

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
            Action("Novo", "N", "tm_new"),
            Action("Editar", "E", "tm_edit"),
            Action("Renomear", "R", "tm_rename"),
            Action("Remover", "D", "tm_remove"),
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
        modal = TemplateEditModal(title="Novo Template")
        self.app.push_screen(modal, callback=self._on_new_result)

    def _on_new_result(self, result: dict | None) -> None:
        if result is None:
            return

        from dbqm.models.template import Template, load_templates, save_templates

        templates = load_templates()

        if any(t.name == result["name"] for t in templates):
            self.notify(f'Template "{result["name"]}" ja existe.', severity="error")
            return

        template = Template(
            name=result["name"],
            description=result["description"],
            content=result["content"],
        )
        templates.append(template)
        save_templates(templates)
        self._load_templates()
        self.notify(f'Template "{template.name}" criado!')

    # -- Edit --

    def _handle_edit(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione um template.", severity="warning")
            return

        from dbqm.models.template import find_template

        template = find_template(name)
        if template is None:
            self.notify(f'Template "{name}" nao encontrado.', severity="error")
            return

        self._edit_template_name = name
        modal = TemplateEditModal(
            title=f"Editar: {name}",
            name_value=template.name,
            description_value=template.description,
            content_value=template.content,
            name_readonly=True,
        )
        self.app.push_screen(modal, callback=self._on_edit_result)

    def _on_edit_result(self, result: dict | None) -> None:
        if result is None:
            return

        from dbqm.models.template import load_templates, save_templates

        templates = load_templates()
        for t in templates:
            if t.name == self._edit_template_name:
                t.description = result["description"]
                t.content = result["content"]
                break
        save_templates(templates)
        self._load_templates()
        self.notify(f'Template "{self._edit_template_name}" atualizado!')

    # -- Rename --

    def _handle_rename(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione um template.", severity="warning")
            return

        from dbqm.ui.modals.text_input import TextInputModal

        self._rename_old_name = name
        modal = TextInputModal(
            title="Renomear Template",
            message=f'Novo nome para "{name}":',
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
            self.notify(f'Template "{new_name}" ja existe.', severity="error")
            return

        for t in templates:
            if t.name == old_name:
                t.name = new_name
                break
        save_templates(templates)
        self._load_templates()
        self.notify(f'Template renomeado: "{old_name}" -> "{new_name}"')

    # -- Remove --

    def _handle_remove(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione um template.", severity="warning")
            return

        from dbqm.ui.modals.confirm import ConfirmModal

        self._remove_name = name
        modal = ConfirmModal(message=f'Remover template "{name}"?')
        self.app.push_screen(modal, callback=self._on_remove_result)

    def _on_remove_result(self, confirmed: bool) -> None:
        if not confirmed:
            return

        from dbqm.models.template import delete_template

        name = self._remove_name
        if delete_template(name):
            self._load_templates()
            self.notify(f'Template "{name}" removido!')
        else:
            self.notify(f'Template "{name}" nao encontrado.', severity="error")
