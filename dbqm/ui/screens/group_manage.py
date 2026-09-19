"""Group management screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.widgets import Button, DataTable, Input, Select, Static, SelectionList

from dbqm.i18n import t
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

        with Dialog(t("group_manage.new_dialog_title"), width="lg", id="dialog"):
            yield Static(
                f'[dim]{t("group_manage.pick_two_hint")}[/dim]',
                id="info",
                markup=True,
            )
            yield Input(placeholder=t("group_manage.name_placeholder"), id="name-input")
            yield Input(placeholder=t("common.description_optional"), id="desc-input")
            yield SelectionList(*query_items, id="query-select")
            yield Input(placeholder=t("group_manage.join_key_placeholder"), id="join-key-input")
            yield Input(
                placeholder=t("group_manage.compare_cols_placeholder"),
                id="compare-cols-input",
            )
            with Horizontal(id="buttons"):
                yield Button(t("common.save"), variant="primary", id="save")
                yield Button(t("common.cancel"), variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#name-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def _save(self) -> None:
        name = self.query_one("#name-input", Input).value.strip()
        selection_list = self.query_one("#query-select", SelectionList)
        selected_queries = list(selection_list.selected)
        join_key = self.query_one("#join-key-input", Input).value.strip()
        description = self.query_one("#desc-input", Input).value.strip()
        compare_cols_raw = self.query_one("#compare-cols-input", Input).value.strip()
        compare_columns = [
            c.strip() for c in compare_cols_raw.split(",") if c.strip()
        ]

        from dbqm.core.group_builder import validate

        errors = validate({
            "name": name, "queries": selected_queries, "join_key": join_key,
            "description": description, "compare_columns": compare_columns,
        })
        if errors:
            self.notify(errors[0], severity="warning")
            return

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
        with Dialog(t("query_manage.edit_what"), width="sm", id="dialog"):
            yield Button(t("common.description"), id="edit_description")
            yield Button(t("query.list_title"), id="edit_queries")
            yield Button(t("group_manage.join_key_button"), id="edit_join_key")
            yield Button(t("group_manage.compare_cols_button"), id="edit_compare_columns")
            yield Button(t("common.template"), id="edit_template")
            yield Button(t("group_manage.template_fields_button"), id="edit_template_fields")
            yield Button(t("common.cancel"), variant="default", id="cancel")

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

        with Dialog(t("group_manage.select_queries_title"), id="dialog"):
            yield SelectionList(*query_items, id="query-select")
            with Horizontal(id="buttons"):
                yield Button(t("common.ok"), variant="primary", id="ok")
                yield Button(t("common.cancel"), variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            selection_list = self.query_one("#query-select", SelectionList)
            selected = list(selection_list.selected)
            if len(selected) < 2:
                self.notify(t("group_manage.pick_two"), severity="warning")
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
        with Dialog(t("group_manage.folder_dialog_title"), id="dialog"):
            if self._existing:
                folders_text = ", ".join(self._existing)
                yield Static(f'[dim]{t("query_manage.existing_folders", folders=folders_text)}[/dim]', id="existing", markup=True)
            yield Input(value=self._current, placeholder=t("query_manage.folder_placeholder"), id="folder-input")
            with Horizontal(id="buttons"):
                yield Button(t("common.ok"), variant="primary", id="ok")
                yield Button(t("common.cancel"), variant="default", id="cancel")

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
        with Dialog(t("group_manage.select_template_title"), width="sm", id="dialog"):
            for tname in self._templates:
                variant = "primary" if tname == self._current else "default"
                yield Button(tname, id=f"tpl-{tname}", variant=variant)
            yield Button(t("group_manage.no_template"), variant="warning", id="tpl--none--")
            yield Button(t("common.cancel"), variant="default", id="tpl--cancel--")

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

        with Dialog(t("group_manage.template_fields_title"), width="lg", id="dialog"):
            yield Static(
                f'[dim]{t("group_manage.template_fields_hint")}[/dim]',
                id="hint",
                markup=True,
            )
            for ph in self._placeholders:
                with H(classes="field-row"):
                    yield Static(f"[bold]{{{{{ph}}}}}[/bold]", classes="field-label", markup=True)
                    yield Input(
                        value=self._current.get(ph, ""),
                        placeholder=t("group_manage.manual_input_placeholder"),
                        id=f"tf-{ph}",
                        classes="field-input",
                    )
            with H(id="buttons"):
                yield Button(t("common.save"), variant="primary", id="save")
                yield Button(t("common.cancel"), variant="default", id="cancel")

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
        with Panel(t("panel.groups"), id="gm-panel"):
            yield EmptyState(
                what=t("group.list_title"),
                why=t("group_manage.empty_why"),
                action_label=t("group_manage.create_group"),
                action_id="create-group",
                id="gm-empty",
            )
            yield DataTable(id="gm-table")

    def on_mount(self) -> None:
        self._setup_table()
        self._load_groups()
        self._set_actions()
        self.call_after_refresh(self._set_initial_focus)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-group":
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
        table.add_columns("#", t("common.name"), t("query.list_title"),
                          t("common.description"), t("common.folder"))

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
            Action(t("action.new_group"), "N", "gm_new"),
            Action(t("action.edit"), "E", "gm_edit"),
            Action(t("action.rename"), "R", "gm_rename"),
            Action(t("action.folder"), "P", "gm_folder"),
            Action(t("action.remove"), "D", "gm_remove"),
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
                t("group_manage.two_queries_needed"),
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
            self.notify(t("group.already_exists", name=result["name"]), severity="error")
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
        self.notify(t("group_manage.created", name=group.name))

    # -- Edit --

    def _handle_edit(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify(t("group_manage.select_one"), severity="warning")
            return

        from dbqm.models.group import find_group

        group = find_group(name)
        if group is None:
            self.notify(t("group.not_found_named", name=name), severity="error")
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
                title=t("query_manage.edit_description_title"),
                message=t("query_manage.description_for", name=name),
                default=group.description,
            )
            self.app.push_screen(modal, callback=self._on_edit_description)

        elif field == "queries":
            modal = QuerySelectionModal(current_queries=group.queries)
            self.app.push_screen(modal, callback=self._on_edit_queries)

        elif field == "join_key":
            from dbqm.ui.modals.text_input import TextInputModal
            modal = TextInputModal(
                title=t("group_manage.edit_join_key_title"),
                message=t("group_manage.join_key_for", name=name),
                default=group.join_key,
            )
            self.app.push_screen(modal, callback=self._on_edit_join_key)

        elif field == "compare_columns":
            from dbqm.ui.modals.text_input import TextInputModal
            current = ", ".join(group.compare_columns)
            modal = TextInputModal(
                title=t("group_manage.edit_compare_cols_title"),
                message=t("group_manage.compare_cols_for", name=name),
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
            self.notify(t("group_manage.no_templates"), severity="warning")
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
            self.notify(t("group_manage.select_template_first"), severity="warning")
            return

        from dbqm.models.template import find_template
        from dbqm.core.template_engine import extract_placeholders

        template = find_template(group.template)
        if template is None:
            self.notify(t("template.not_found_named", name=group.template), severity="error")
            return

        placeholders = extract_placeholders(template.content)
        if not placeholders:
            self.notify(t("group_manage.template_without_fields"), severity="warning")
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
        self.notify(t("group_manage.updated", name=name))

    # -- Rename --

    def _handle_rename(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify(t("group_manage.select_one"), severity="warning")
            return

        from dbqm.ui.modals.text_input import TextInputModal

        self._rename_old_name = name
        modal = TextInputModal(
            title=t("group_manage.rename_title"),
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

        from dbqm.models.group import load_groups, save_groups

        groups = load_groups()

        if any(g.name == new_name for g in groups):
            self.notify(t("group.already_exists", name=new_name), severity="error")
            return

        for g in groups:
            if g.name == old_name:
                g.name = new_name
                break
        save_groups(groups)
        self._load_groups()
        self.notify(t("group_manage.renamed", old=old_name, new=new_name))

    # -- Folder --

    def _handle_folder(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify(t("group_manage.select_one"), severity="warning")
            return

        from dbqm.models.group import find_group, load_groups

        group = find_group(name)
        if group is None:
            self.notify(t("group.not_found_named", name=name), severity="error")
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
        label = f'"{folder}"' if folder else t("common.no_folder")
        self.notify(t("group_manage.moved_to", name=self._folder_group_name, folder=label))

    # -- Remove --

    def _handle_remove(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify(t("group_manage.select_one"), severity="warning")
            return

        from dbqm.ui.modals.confirm import ConfirmModal

        self._remove_name = name
        modal = ConfirmModal(message=t("group_manage.confirm_remove", name=name))
        self.app.push_screen(modal, callback=self._on_remove_result)

    def _on_remove_result(self, confirmed: bool) -> None:
        if not confirmed:
            return

        from dbqm.models.group import delete_group

        name = self._remove_name
        if delete_group(name):
            self._load_groups()
            self._update_status_bar()
            self.notify(t("group_manage.removed", name=name))
        else:
            self.notify(t("group.not_found_named", name=name), severity="error")

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
