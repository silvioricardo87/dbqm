"""Group management screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.widgets import Button, DataTable, Input, Select, Static, SelectionList

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.dialog import Dialog
from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.panel import Panel


# ---------------------------------------------------------------------------
# Helper modal: Group create
# ---------------------------------------------------------------------------

class GroupCreateModal(ModalScreen[dict | None]):
    """Modal for creating a new group."""

    DEFAULT_CSS = """
    GroupCreateModal {
        align: center middle;
    }
    GroupCreateModal Input {
        width: 100%;
        margin-bottom: 1;
    }
    GroupCreateModal SelectionList {
        height: 10;
        margin-bottom: 1;
    }
    GroupCreateModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }
    GroupCreateModal Button {
        margin: 0 1;
    }
    GroupCreateModal #info {
        margin-bottom: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def compose(self) -> ComposeResult:
        from dbqm.models.query import load_queries

        queries = load_queries()
        query_items = [(q.name, q.name) for q in sorted(queries, key=lambda q: q.name)]

        with Dialog("Novo Grupo", width="lg", id="dialog"):
            yield Static(
                "[dim]Selecione pelo menos 2 consultas para comparar.[/dim]",
                id="info",
                markup=True,
            )
            yield Input(placeholder="Nome do grupo", id="name-input")
            yield Input(placeholder="Descricao (opcional)", id="desc-input")
            yield SelectionList(*query_items, id="query-select")
            yield Input(placeholder="Coluna de juncao (join key)", id="join-key-input")
            yield Input(
                placeholder="Colunas de comparacao (separadas por virgula)",
                id="compare-cols-input",
            )
            with Horizontal(id="buttons"):
                yield Button("Salvar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def _save(self) -> None:
        name = self.query_one("#name-input", Input).value.strip()
        if not name:
            self.notify("Informe o nome do grupo.", severity="warning")
            return

        selection_list = self.query_one("#query-select", SelectionList)
        selected_queries = list(selection_list.selected)
        if len(selected_queries) < 2:
            self.notify("Selecione pelo menos 2 consultas.", severity="warning")
            return

        join_key = self.query_one("#join-key-input", Input).value.strip()
        if not join_key:
            self.notify("Informe a coluna de juncao.", severity="warning")
            return

        description = self.query_one("#desc-input", Input).value.strip()
        compare_cols_raw = self.query_one("#compare-cols-input", Input).value.strip()
        compare_columns = [
            c.strip() for c in compare_cols_raw.split(",") if c.strip()
        ]

        self.dismiss({
            "name": name,
            "description": description,
            "queries": selected_queries,
            "join_key": join_key,
            "compare_columns": compare_columns,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Helper modal: Group edit sub-menu
# ---------------------------------------------------------------------------

class GroupEditMenuModal(ModalScreen[str | None]):
    """Modal to pick what to edit on a group."""

    DEFAULT_CSS = """
    GroupEditMenuModal {
        align: center middle;
    }
    GroupEditMenuModal Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Dialog("O que deseja editar?", width="sm", id="dialog"):
            yield Button("Descricao", id="edit_description")
            yield Button("Consultas", id="edit_queries")
            yield Button("Coluna de juncao", id="edit_join_key")
            yield Button("Colunas de comparacao", id="edit_compare_columns")
            yield Button("Template", id="edit_template")
            yield Button("Campos do template", id="edit_template_fields")
            yield Button("Cancelar", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "cancel":
            self.dismiss(None)
        elif bid and bid.startswith("edit_"):
            self.dismiss(bid.replace("edit_", ""))

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Helper modal: Query selection for editing queries in a group
# ---------------------------------------------------------------------------

class QuerySelectionModal(ModalScreen[list[str] | None]):
    """Modal for selecting queries for a group."""

    DEFAULT_CSS = """
    QuerySelectionModal {
        align: center middle;
    }
    QuerySelectionModal SelectionList {
        height: 12;
        margin-bottom: 1;
    }
    QuerySelectionModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }
    QuerySelectionModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, current_queries: list[str]) -> None:
        super().__init__()
        self._current = set(current_queries)

    def compose(self) -> ComposeResult:
        from dbqm.models.query import load_queries

        queries = load_queries()
        query_items = [
            (q.name, q.name, q.name in self._current)
            for q in sorted(queries, key=lambda q: q.name)
        ]

        with Dialog("Selecionar Consultas", id="dialog"):
            yield SelectionList(*query_items, id="query-select")
            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            selection_list = self.query_one("#query-select", SelectionList)
            selected = list(selection_list.selected)
            if len(selected) < 2:
                self.notify("Selecione pelo menos 2 consultas.", severity="warning")
                return
            self.dismiss(selected)
        elif event.button.id == "cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Helper modal: Folder selection (reused pattern from query_manage)
# ---------------------------------------------------------------------------

class GroupFolderModal(ModalScreen[str | None]):
    """Modal to pick or type a folder name for a group."""

    DEFAULT_CSS = """
    GroupFolderModal {
        align: center middle;
    }
    GroupFolderModal Input {
        width: 100%;
        margin-bottom: 1;
    }
    GroupFolderModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }
    GroupFolderModal Button {
        margin: 0 1;
    }
    GroupFolderModal #existing {
        margin-bottom: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, current_folder: str = "", existing_folders: list[str] | None = None) -> None:
        super().__init__()
        self._current = current_folder
        self._existing = existing_folders or []

    def compose(self) -> ComposeResult:
        with Dialog("Pasta do Grupo", id="dialog"):
            if self._existing:
                folders_text = ", ".join(self._existing)
                yield Static(f"[dim]Pastas existentes: {folders_text}[/dim]", id="existing", markup=True)
            yield Input(value=self._current, placeholder="Nome da pasta (vazio = sem pasta)", id="folder-input")
            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#folder-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.dismiss(self.query_one("#folder-input", Input).value.strip())
        elif event.button.id == "cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Helper modal: Template picker
# ---------------------------------------------------------------------------

class TemplatePickerModal(ModalScreen[str | None]):
    """Modal to pick a template for a group."""

    DEFAULT_CSS = """
    TemplatePickerModal {
        align: center middle;
    }
    TemplatePickerModal Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, templates: list[str], current: str = "") -> None:
        super().__init__()
        self._templates = templates
        self._current = current

    def compose(self) -> ComposeResult:
        with Dialog("Selecionar Template", width="sm", id="dialog"):
            for tname in self._templates:
                variant = "primary" if tname == self._current else "default"
                yield Button(tname, id=f"tpl-{tname}", variant=variant)
            yield Button("Nenhum (remover)", variant="warning", id="tpl--none--")
            yield Button("Cancelar", variant="default", id="tpl--cancel--")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "tpl--cancel--":
            self.dismiss(None)
        elif btn_id == "tpl--none--":
            self.dismiss("")
        elif btn_id.startswith("tpl-"):
            self.dismiss(btn_id.removeprefix("tpl-"))

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Helper modal: Template fields mapping editor
# ---------------------------------------------------------------------------

class TemplateFieldsModal(ModalScreen[dict | None]):
    """Modal to configure template field source mappings."""

    DEFAULT_CSS = """
    TemplateFieldsModal {
        align: center middle;
    }
    TemplateFieldsModal #dialog {
        overflow-y: auto;
    }
    TemplateFieldsModal #hint {
        margin-bottom: 1;
        color: $text-muted;
    }
    TemplateFieldsModal .field-row {
        height: auto;
        margin-bottom: 1;
    }
    TemplateFieldsModal .field-label {
        width: 20;
        height: 1;
        padding: 1 1 0 0;
    }
    TemplateFieldsModal .field-input {
        width: 1fr;
    }
    TemplateFieldsModal #buttons {
        margin-top: 1;
        width: 100%;
        height: auto;
        align: center middle;
    }
    TemplateFieldsModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(
        self,
        placeholders: list[str],
        current_mappings: dict[str, str],
        query_names: list[str],
    ) -> None:
        super().__init__()
        self._placeholders = placeholders
        self._current = current_mappings
        self._query_names = query_names

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal as H

        with Dialog("Configurar Campos do Template", width="lg", id="dialog"):
            yield Static(
                "[dim]Fontes: param:NOME | query:CONSULTA:COLUNA | query:CONSULTA:_count | "
                "query:CONSULTA:_status | literal:texto\n"
                "Vazio = campo de preenchimento manual[/dim]",
                id="hint",
                markup=True,
            )
            for ph in self._placeholders:
                with H(classes="field-row"):
                    yield Static(f"[bold]{{{{{ph}}}}}[/bold]", classes="field-label", markup=True)
                    yield Input(
                        value=self._current.get(ph, ""),
                        placeholder="vazio = input manual",
                        id=f"tf-{ph}",
                        classes="field-input",
                    )
            with H(id="buttons"):
                yield Button("Salvar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        if self._placeholders:
            try:
                self.query_one(f"#tf-{self._placeholders[0]}", Input).focus()
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def _save(self) -> None:
        mappings = {}
        for ph in self._placeholders:
            try:
                value = self.query_one(f"#tf-{ph}", Input).value.strip()
                if value:
                    mappings[ph] = value
            except Exception:
                pass
        self.dismiss(mappings)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Main screen
# ---------------------------------------------------------------------------

class GroupManageScreen(Vertical):
    """Screen widget for managing groups (CRUD)."""

    DEFAULT_CSS = """
    GroupManageScreen {
        height: 1fr;
    }
    GroupManageScreen #gm-panel {
        margin: 1 2;
    }
    GroupManageScreen #gm-empty {
        height: 1fr;
    }
    GroupManageScreen DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        with Panel("👥  GRUPOS", id="gm-panel"):
            yield EmptyState(
                what="Grupos",
                why="Grupos comparam a mesma consulta em varias conexoes de uma vez",
                action_label="Criar grupo",
                action_id="criar-grupo",
                id="gm-empty",
            )
            yield DataTable(id="gm-table")

    def on_mount(self) -> None:
        self._setup_table()
        self._load_groups()
        self._set_actions()
        self.call_after_refresh(self._set_initial_focus)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "criar-grupo":
            self._handle_new()

    def _set_initial_focus(self) -> None:
        table = self.query_one("#gm-table", DataTable)
        if table.display:
            table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter on a row — edit the selected group."""
        if event.data_table.id == "gm-table":
            self._handle_edit()

    def _setup_table(self) -> None:
        table = self.query_one("#gm-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "Nome", "Consultas", "Descricao", "Pasta")

    def _load_groups(self) -> None:
        from dbqm.models.group import load_groups

        groups = load_groups()
        table = self.query_one("#gm-table", DataTable)
        empty_msg = self.query_one("#gm-empty", EmptyState)

        table.clear()

        if not groups:
            empty_msg.display = True
            table.display = False
            return

        empty_msg.display = False
        table.display = True

        sorted_groups = sorted(groups, key=lambda g: g.name.lower())

        for i, g in enumerate(sorted_groups, 1):
            queries_str = ", ".join(g.queries[:3])
            if len(g.queries) > 3:
                queries_str += f" (+{len(g.queries) - 3})"
            table.add_row(
                str(i),
                g.name,
                queries_str,
                (g.description[:40] if g.description else ""),
                g.folder or "",
            )

    def _set_actions(self) -> None:
        try:
            action_bar = self.app.query_one(ActionBar)
        except Exception:
            return
        actions = [
            Action("Novo", "N", "gm_new"),
            Action("Editar", "E", "gm_edit"),
            Action("Renomear", "R", "gm_rename"),
            Action("Pasta", "P", "gm_folder"),
            Action("Remover", "D", "gm_remove"),
        ]
        action_bar.set_actions(actions)

    def _get_selected_name(self) -> str | None:
        """Get the group name from the currently selected table row."""
        table = self.query_one("#gm-table", DataTable)
        if not table.display or table.row_count == 0:
            return None
        try:
            row_key = table.cursor_row
            row = table.get_row_at(row_key)
            return str(row[1])  # Name column (index 1)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id
        handler = {
            "gm_new": self._handle_new,
            "gm_edit": self._handle_edit,
            "gm_rename": self._handle_rename,
            "gm_folder": self._handle_folder,
            "gm_remove": self._handle_remove,
        }.get(action)
        if handler:
            handler()

    # -- New --

    def _handle_new(self) -> None:
        from dbqm.models.query import load_queries

        queries = load_queries()
        if len(queries) < 2:
            self.notify(
                "Sao necessarias pelo menos 2 consultas para criar um grupo.",
                severity="warning",
            )
            return

        modal = GroupCreateModal()
        self.app.push_screen(modal, callback=self._on_new_result)

    def _on_new_result(self, result: dict | None) -> None:
        if result is None:
            return

        from dbqm.models.group import Group, load_groups, save_groups

        groups = load_groups()

        if any(g.name == result["name"] for g in groups):
            self.notify(f'Grupo "{result["name"]}" ja existe.', severity="error")
            return

        group = Group(
            name=result["name"],
            description=result["description"],
            queries=result["queries"],
            join_key=result["join_key"],
            compare_columns=result["compare_columns"],
        )
        groups.append(group)
        save_groups(groups)
        self._load_groups()
        self._update_status_bar()
        self.notify(f'Grupo "{group.name}" criado!')

    # -- Edit --

    def _handle_edit(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione um grupo.", severity="warning")
            return

        from dbqm.models.group import find_group

        group = find_group(name)
        if group is None:
            self.notify(f'Grupo "{name}" nao encontrado.', severity="error")
            return

        self._edit_group_name = name
        modal = GroupEditMenuModal()
        self.app.push_screen(modal, callback=self._on_edit_menu_result)

    def _on_edit_menu_result(self, field: str | None) -> None:
        if field is None:
            return

        from dbqm.models.group import find_group

        name = self._edit_group_name
        group = find_group(name)
        if group is None:
            return

        if field == "description":
            from dbqm.ui.modals.text_input import TextInputModal
            modal = TextInputModal(
                title="Editar Descricao",
                message=f'Descricao para "{name}":',
                default=group.description,
            )
            self.app.push_screen(modal, callback=self._on_edit_description)

        elif field == "queries":
            modal = QuerySelectionModal(current_queries=group.queries)
            self.app.push_screen(modal, callback=self._on_edit_queries)

        elif field == "join_key":
            from dbqm.ui.modals.text_input import TextInputModal
            modal = TextInputModal(
                title="Editar Coluna de Juncao",
                message=f'Coluna de juncao para "{name}":',
                default=group.join_key,
            )
            self.app.push_screen(modal, callback=self._on_edit_join_key)

        elif field == "compare_columns":
            from dbqm.ui.modals.text_input import TextInputModal
            current = ", ".join(group.compare_columns)
            modal = TextInputModal(
                title="Editar Colunas de Comparacao",
                message=f'Colunas para "{name}" (separadas por virgula):',
                default=current,
            )
            self.app.push_screen(modal, callback=self._on_edit_compare_columns)

        elif field == "template":
            self._push_template_picker(group)

        elif field == "template_fields":
            self._push_template_fields_editor(group)

    def _on_edit_description(self, value: str | None) -> None:
        if value is None:
            return
        self._update_group_field(self._edit_group_name, "description", value.strip())

    def _on_edit_queries(self, queries: list[str] | None) -> None:
        if queries is None:
            return
        self._update_group_field(self._edit_group_name, "queries", queries)

    def _on_edit_join_key(self, value: str | None) -> None:
        if value is None:
            return
        self._update_group_field(self._edit_group_name, "join_key", value.strip())

    def _on_edit_compare_columns(self, value: str | None) -> None:
        if value is None:
            return
        cols = [c.strip() for c in value.split(",") if c.strip()]
        self._update_group_field(self._edit_group_name, "compare_columns", cols)

    def _push_template_picker(self, group) -> None:
        """Show a picker to select a template for this group."""
        from dbqm.models.template import load_templates

        templates = load_templates()
        if not templates:
            self.notify("Nenhum template disponivel. Crie um primeiro.", severity="warning")
            return

        modal = TemplatePickerModal(
            templates=[t.name for t in templates],
            current=group.template,
        )
        self.app.push_screen(modal, callback=self._on_template_selected)

    def _on_template_selected(self, result: str | None) -> None:
        if result is None:
            return
        self._update_group_field(self._edit_group_name, "template", result)
        if result == "":
            self._update_group_field(self._edit_group_name, "template_fields", {})

    def _push_template_fields_editor(self, group) -> None:
        """Show the template field mapping editor."""
        if not group.template:
            self.notify("Selecione um template primeiro.", severity="warning")
            return

        from dbqm.models.template import find_template
        from dbqm.core.template_engine import extract_placeholders

        template = find_template(group.template)
        if template is None:
            self.notify(f'Template "{group.template}" nao encontrado.', severity="error")
            return

        placeholders = extract_placeholders(template.content)
        if not placeholders:
            self.notify("Template nao possui campos {{campo}}.", severity="warning")
            return

        modal = TemplateFieldsModal(
            placeholders=placeholders,
            current_mappings=group.template_fields,
            query_names=group.queries,
        )
        self.app.push_screen(modal, callback=self._on_template_fields_result)

    def _on_template_fields_result(self, result: dict | None) -> None:
        if result is None:
            return
        self._update_group_field(self._edit_group_name, "template_fields", result)

    def _update_group_field(self, name: str, field: str, value) -> None:
        from dbqm.models.group import load_groups, save_groups

        groups = load_groups()
        for g in groups:
            if g.name == name:
                setattr(g, field, value)
                break
        save_groups(groups)
        self._load_groups()
        self.notify(f'"{name}" atualizado!')

    # -- Rename --

    def _handle_rename(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione um grupo.", severity="warning")
            return

        from dbqm.ui.modals.text_input import TextInputModal

        self._rename_old_name = name
        modal = TextInputModal(
            title="Renomear Grupo",
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

        from dbqm.models.group import load_groups, save_groups

        groups = load_groups()

        if any(g.name == new_name for g in groups):
            self.notify(f'Grupo "{new_name}" ja existe.', severity="error")
            return

        for g in groups:
            if g.name == old_name:
                g.name = new_name
                break
        save_groups(groups)
        self._load_groups()
        self.notify(f'Grupo renomeado: "{old_name}" -> "{new_name}"')

    # -- Folder --

    def _handle_folder(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione um grupo.", severity="warning")
            return

        from dbqm.models.group import find_group, load_groups

        group = find_group(name)
        if group is None:
            self.notify(f'Grupo "{name}" nao encontrado.', severity="error")
            return

        all_groups = load_groups()
        existing_folders = sorted({g.folder for g in all_groups if g.folder})

        self._folder_group_name = name
        modal = GroupFolderModal(current_folder=group.folder, existing_folders=existing_folders)
        self.app.push_screen(modal, callback=self._on_folder_result)

    def _on_folder_result(self, folder: str | None) -> None:
        if folder is None:
            return

        from dbqm.models.group import load_groups, save_groups

        groups = load_groups()
        for g in groups:
            if g.name == self._folder_group_name:
                g.folder = folder
                break
        save_groups(groups)
        self._load_groups()
        label = f'"{folder}"' if folder else "(sem pasta)"
        self.notify(f'"{self._folder_group_name}" movido para {label}!')

    # -- Remove --

    def _handle_remove(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione um grupo.", severity="warning")
            return

        from dbqm.ui.modals.confirm import ConfirmModal

        self._remove_name = name
        modal = ConfirmModal(message=f'Remover grupo "{name}"?')
        self.app.push_screen(modal, callback=self._on_remove_result)

    def _on_remove_result(self, confirmed: bool) -> None:
        if not confirmed:
            return

        from dbqm.models.group import delete_group

        name = self._remove_name
        if delete_group(name):
            self._load_groups()
            self._update_status_bar()
            self.notify(f'Grupo "{name}" removido!')
        else:
            self.notify(f'Grupo "{name}" nao encontrado.', severity="error")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_status_bar(self) -> None:
        """Update the status bar counts."""
        try:
            from dbqm.models.connection import load_connections
            from dbqm.models.query import load_queries
            from dbqm.models.group import load_groups
            from dbqm.ui.widgets.status_bar import StatusBar

            status_bar = self.app.query_one(StatusBar)
            status_bar.update_counts(
                connections=len(load_connections()),
                queries=len(load_queries()),
                groups=len(load_groups()),
            )
        except Exception:
            pass
