"""Query management screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.widgets import Button, DataTable, Input, Select, Static, TextArea

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.dialog import Dialog


# ---------------------------------------------------------------------------
# Helper modal: SQL paste screen for creating a new query
# ---------------------------------------------------------------------------

class SqlPasteModal(ModalScreen[dict | None]):
    """Modal for pasting SQL and configuring a new query."""

    DEFAULT_CSS = """
    SqlPasteModal {
        align: center middle;
    }
    SqlPasteModal TextArea {
        height: 10;
        margin-bottom: 1;
    }
    SqlPasteModal Input {
        width: 100%;
        margin-bottom: 1;
    }
    SqlPasteModal Select {
        width: 100%;
        margin-bottom: 1;
    }
    SqlPasteModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }
    SqlPasteModal Button {
        margin: 0 1;
    }
    SqlPasteModal #info {
        margin-bottom: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def compose(self) -> ComposeResult:
        from dbqm.models.connection import load_connections

        connections = load_connections()
        conn_options = [(c.name, c.name) for c in connections]

        with Dialog("Nova Consulta (Colar SQL)", largura="lg", id="dialog"):
            yield Static("[dim]Cole o SQL abaixo. A tabela e colunas serao detectadas automaticamente.[/dim]", id="info", markup=True)
            yield TextArea(id="sql-area", language="sql")
            yield Input(placeholder="Nome da consulta", id="name-input")
            yield Input(placeholder="Descricao (opcional)", id="desc-input")
            yield Select(conn_options, prompt="Conexao", id="conn-select")
            with Horizontal(id="buttons"):
                yield Button("Salvar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#sql-area", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def _save(self) -> None:
        sql = self.query_one("#sql-area", TextArea).text.strip()
        name = self.query_one("#name-input", Input).value.strip()
        conn_select = self.query_one("#conn-select", Select)
        connection = str(conn_select.value) if conn_select.value is not Select.BLANK else ""

        if not sql:
            self.notify("Informe o SQL.", severity="warning")
            return
        if not name:
            self.notify("Informe o nome da consulta.", severity="warning")
            return
        if not connection:
            self.notify("Selecione uma conexao.", severity="warning")
            return

        description = self.query_one("#desc-input", Input).value.strip()

        # Parse SQL to extract table, columns, params
        from dbqm.core.query_engine import parse_sql, detect_params

        parsed = parse_sql(sql)
        params_found = detect_params(sql)

        result = {
            "name": name,
            "connection": connection,
            "sql": sql,
            "table": parsed.get("table", ""),
            "description": description,
            "columns": parsed.get("columns", []),
            "order_by": parsed.get("order_by", ""),
            "params": [{"name": p, "description": "", "default": ""} for p in params_found],
        }
        self.dismiss(result)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Helper modal: SQL viewer modal
# ---------------------------------------------------------------------------

class SqlViewerModal(ModalScreen[None]):
    """Read-only modal showing SQL for a query."""

    DEFAULT_CSS = """
    SqlViewerModal {
        align: center middle;
    }
    SqlViewerModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Fechar", show=False),
    ]

    def __init__(self, query_name: str, sql: str) -> None:
        super().__init__()
        self._query_name = query_name
        self._sql = sql

    def compose(self) -> ComposeResult:
        from dbqm.ui.widgets.sql_viewer import SqlViewer

        with Dialog(f"SQL: {self._query_name}", largura="lg", id="dialog"):
            yield SqlViewer(self._sql, id="sql-display")
            with Horizontal(id="buttons"):
                yield Button("Fechar", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Helper modal: Edit sub-menu
# ---------------------------------------------------------------------------

class EditMenuModal(ModalScreen[str | None]):
    """Modal to pick what to edit on a query."""

    DEFAULT_CSS = """
    EditMenuModal {
        align: center middle;
    }
    EditMenuModal Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Dialog("O que deseja editar?", largura="sm", id="dialog"):
            yield Button("Descricao", id="edit_description")
            yield Button("Conexao", id="edit_connection")
            yield Button("SQL", id="edit_sql")
            yield Button("Tabela", id="edit_table")
            yield Button("Parametros", id="edit_params")
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
# Helper modal: Edit SQL
# ---------------------------------------------------------------------------

class EditSqlModal(ModalScreen[str | None]):
    """Modal for editing a query's SQL."""

    DEFAULT_CSS = """
    EditSqlModal {
        align: center middle;
    }
    EditSqlModal TextArea {
        height: 12;
        margin-bottom: 1;
    }
    EditSqlModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }
    EditSqlModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, current_sql: str) -> None:
        super().__init__()
        self._current_sql = current_sql

    def compose(self) -> ComposeResult:
        with Dialog("Editar SQL", largura="lg", id="dialog"):
            yield TextArea(self._current_sql, id="sql-area", language="sql")
            with Horizontal(id="buttons"):
                yield Button("Salvar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#sql-area", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            sql = self.query_one("#sql-area", TextArea).text.strip()
            if not sql:
                self.notify("SQL nao pode ser vazio.", severity="warning")
                return
            self.dismiss(sql)
        elif event.button.id == "cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Helper modal: Folder selection
# ---------------------------------------------------------------------------

class FolderModal(ModalScreen[str | None]):
    """Modal to pick or type a folder name."""

    DEFAULT_CSS = """
    FolderModal {
        align: center middle;
    }
    FolderModal Input {
        width: 100%;
        margin-bottom: 1;
    }
    FolderModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }
    FolderModal Button {
        margin: 0 1;
    }
    FolderModal #existing {
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
        with Dialog("Pasta da Consulta", id="dialog"):
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
# Helper modal: Connection selector for duplicate
# ---------------------------------------------------------------------------

class ConnectionPickerModal(ModalScreen[str | None]):
    """Pick a connection for a duplicated query."""

    DEFAULT_CSS = """
    ConnectionPickerModal {
        align: center middle;
    }
    ConnectionPickerModal Select {
        width: 100%;
        margin-bottom: 1;
    }
    ConnectionPickerModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }
    ConnectionPickerModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, current_connection: str) -> None:
        super().__init__()
        self._current = current_connection

    def compose(self) -> ComposeResult:
        from dbqm.models.connection import load_connections

        connections = load_connections()
        options = [(c.name, c.name) for c in connections]

        with Dialog("Conexao para a copia", id="dialog"):
            yield Select(options, value=self._current, id="conn-pick")
            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            sel = self.query_one("#conn-pick", Select)
            if sel.value is not Select.BLANK:
                self.dismiss(str(sel.value))
            else:
                self.dismiss(None)
        elif event.button.id == "cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Main screen
# ---------------------------------------------------------------------------

class QueryManageScreen(Vertical):
    """Screen widget for managing queries (CRUD)."""

    DEFAULT_CSS = """
    QueryManageScreen {
        height: 1fr;
    }
    QueryManageScreen #qm-empty {
        height: 1fr;
        content-align: center middle;
        text-align: center;
    }
    QueryManageScreen DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "[dim]Nenhuma consulta configurada[/]",
            id="qm-empty",
            markup=True,
        )
        yield DataTable(id="qm-table")

    def on_mount(self) -> None:
        self._setup_table()
        self._load_queries()
        self._set_actions()
        self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        table = self.query_one("#qm-table", DataTable)
        if table.display:
            table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter on a row — view SQL of the selected query."""
        if event.data_table.id == "qm-table":
            self._handle_view_sql()

    def _setup_table(self) -> None:
        table = self.query_one("#qm-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "Pasta", "Nome", "Descricao", "Conexao", "Tabela", "Params", "Fav")

    def _load_queries(self) -> None:
        from dbqm.models.query import load_queries

        queries = load_queries()
        table = self.query_one("#qm-table", DataTable)
        empty_msg = self.query_one("#qm-empty", Static)

        table.clear()

        if not queries:
            empty_msg.display = True
            table.display = False
            return

        empty_msg.display = False
        table.display = True

        # Sort by folder then name
        sorted_queries = sorted(queries, key=lambda q: (q.folder or "", q.name))

        for i, q in enumerate(sorted_queries, 1):
            fav = "★" if q.is_favorite else ""
            table.add_row(
                str(i),
                q.folder or "",
                q.name,
                q.description[:40] if q.description else "",
                q.connection,
                q.table or "",
                str(len(q.params)),
                fav,
            )

    def _set_actions(self) -> None:
        try:
            action_bar = self.app.query_one(ActionBar)
        except Exception:
            return
        actions = [
            Action("Nova", "N", "qm_new"),
            Action("Ver SQL", "V", "qm_view_sql"),
            Action("Editar", "E", "qm_edit"),
            Action("DE-PARA", "M", "qm_depara"),
            Action("Renomear", "R", "qm_rename"),
            Action("Favorito", "F", "qm_favorite"),
            Action("Pasta", "P", "qm_folder"),
            Action("Duplicar", "C", "qm_duplicate"),
            Action("Remover", "D", "qm_remove"),
        ]
        action_bar.set_actions(actions)

    def _get_selected_name(self) -> str | None:
        """Get the query name from the currently selected table row."""
        table = self.query_one("#qm-table", DataTable)
        if not table.display or table.row_count == 0:
            return None
        try:
            row_key = table.cursor_row
            row = table.get_row_at(row_key)
            return str(row[2])  # Name column (index 2)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id
        handler = {
            "qm_new": self._handle_new,
            "qm_view_sql": self._handle_view_sql,
            "qm_edit": self._handle_edit,
            "qm_depara": self._handle_depara,
            "qm_rename": self._handle_rename,
            "qm_favorite": self._handle_favorite,
            "qm_folder": self._handle_folder,
            "qm_duplicate": self._handle_duplicate,
            "qm_remove": self._handle_remove,
        }.get(action)
        if handler:
            handler()

    # -- New --

    def _handle_new(self) -> None:
        # For now, go directly to paste mode
        # (Wizard mode can be added later as an enhancement)
        modal = SqlPasteModal()
        self.app.push_screen(modal, callback=self._on_new_result)

    def _on_new_result(self, result: dict | None) -> None:
        if result is None:
            return

        from dbqm.models.query import Query, QueryParam, load_queries, save_queries

        queries = load_queries()

        # Check duplicate name
        if any(q.name == result["name"] for q in queries):
            self.notify(f'Consulta "{result["name"]}" ja existe.', severity="error")
            return

        params = [
            QueryParam(name=p["name"], description=p.get("description", ""), default=p.get("default", ""))
            for p in result.get("params", [])
        ]

        query = Query(
            name=result["name"],
            connection=result["connection"],
            sql=result["sql"],
            table=result.get("table", ""),
            description=result.get("description", ""),
            params=params,
            columns=result.get("columns", []),
            order_by=result.get("order_by", ""),
        )
        queries.append(query)
        save_queries(queries)
        self._load_queries()
        self._update_status_bar()
        self.notify(f'Consulta "{query.name}" criada!')

    # -- View SQL --

    def _handle_view_sql(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma consulta.", severity="warning")
            return

        from dbqm.models.query import find_query

        query = find_query(name)
        if query is None:
            self.notify(f'Consulta "{name}" nao encontrada.', severity="error")
            return

        modal = SqlViewerModal(query.name, query.sql)
        self.app.push_screen(modal)

    # -- Edit --

    def _handle_edit(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma consulta.", severity="warning")
            return

        from dbqm.models.query import find_query

        query = find_query(name)
        if query is None:
            self.notify(f'Consulta "{name}" nao encontrada.', severity="error")
            return

        self._edit_query_name = name
        modal = EditMenuModal()
        self.app.push_screen(modal, callback=self._on_edit_menu_result)

    def _on_edit_menu_result(self, field: str | None) -> None:
        if field is None:
            return

        from dbqm.models.query import find_query

        name = self._edit_query_name
        query = find_query(name)
        if query is None:
            return

        if field == "description":
            from dbqm.ui.modals.text_input import TextInputModal
            modal = TextInputModal(
                title="Editar Descricao",
                message=f'Descricao para "{name}":',
                default=query.description,
            )
            self.app.push_screen(modal, callback=self._on_edit_description)

        elif field == "connection":
            from dbqm.models.connection import load_connections
            connections = load_connections()
            if not connections:
                self.notify("Nenhuma conexao disponivel.", severity="warning")
                return
            modal = ConnectionPickerModal(query.connection)
            self.app.push_screen(modal, callback=self._on_edit_connection)

        elif field == "sql":
            modal = EditSqlModal(query.sql)
            self.app.push_screen(modal, callback=self._on_edit_sql)

        elif field == "table":
            from dbqm.ui.modals.text_input import TextInputModal
            modal = TextInputModal(
                title="Editar Tabela",
                message=f'Tabela para "{name}":',
                default=query.table,
            )
            self.app.push_screen(modal, callback=self._on_edit_table)

        elif field == "params":
            self.notify("Edicao de parametros: use Editar SQL para ajustar.", severity="information")

    def _on_edit_description(self, value: str | None) -> None:
        if value is None:
            return
        self._update_query_field(self._edit_query_name, "description", value.strip())

    def _on_edit_connection(self, value: str | None) -> None:
        if value is None:
            return
        self._update_query_field(self._edit_query_name, "connection", value)

    def _on_edit_sql(self, sql: str | None) -> None:
        if sql is None:
            return

        from dbqm.core.query_engine import parse_sql, detect_params
        from dbqm.models.query import QueryParam, load_queries, save_queries

        queries = load_queries()
        for q in queries:
            if q.name == self._edit_query_name:
                q.sql = sql
                parsed = parse_sql(sql)
                q.table = parsed.get("table", q.table)
                q.columns = parsed.get("columns", q.columns)
                q.order_by = parsed.get("order_by", q.order_by)
                # Update params
                new_params = detect_params(sql)
                existing_names = {p.name for p in q.params}
                for pn in new_params:
                    if pn not in existing_names:
                        q.params.append(QueryParam(name=pn))
                break
        save_queries(queries)
        self._load_queries()
        self.notify(f'SQL de "{self._edit_query_name}" atualizado!')

    def _on_edit_table(self, value: str | None) -> None:
        if value is None:
            return
        self._update_query_field(self._edit_query_name, "table", value.strip())

    def _update_query_field(self, name: str, field: str, value: str) -> None:
        from dbqm.models.query import load_queries, save_queries

        queries = load_queries()
        for q in queries:
            if q.name == name:
                setattr(q, field, value)
                break
        save_queries(queries)
        self._load_queries()
        self.notify(f'"{name}" atualizado!')

    # -- DE-PARA --

    def _handle_depara(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma consulta.", severity="warning")
            return

        from dbqm.models.query import find_query

        query = find_query(name)
        if query is None:
            self.notify(f'Consulta "{name}" nao encontrada.', severity="error")
            return

        if not query.columns:
            self.notify("Consulta sem colunas detectadas.", severity="warning")
            return

        from dbqm.ui.modals.column_maps import ColumnMapsModal

        self._depara_query_name = name
        modal = ColumnMapsModal(columns=query.columns, current_maps=query.column_maps)
        self.app.push_screen(modal, callback=self._on_depara_result)

    def _on_depara_result(self, maps: dict | None) -> None:
        if maps is None:
            return

        from dbqm.models.query import load_queries, save_queries

        queries = load_queries()
        for q in queries:
            if q.name == self._depara_query_name:
                q.column_maps = maps
                break
        save_queries(queries)
        self.notify(f'DE-PARA de "{self._depara_query_name}" salvo!')

    # -- Rename --

    def _handle_rename(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma consulta.", severity="warning")
            return

        from dbqm.ui.modals.text_input import TextInputModal

        self._rename_old_name = name
        modal = TextInputModal(
            title="Renomear Consulta",
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

        from dbqm.models.query import load_queries, save_queries

        queries = load_queries()

        if any(q.name == new_name for q in queries):
            self.notify(f'Consulta "{new_name}" ja existe.', severity="error")
            return

        for q in queries:
            if q.name == old_name:
                q.name = new_name
                break
        save_queries(queries)

        # Update groups that reference the old query name
        from dbqm.models.group import load_groups, save_groups

        groups = load_groups()
        groups_updated = False
        for g in groups:
            if old_name in g.queries:
                g.queries = [new_name if qn == old_name else qn for qn in g.queries]
                groups_updated = True
        if groups_updated:
            save_groups(groups)

        self._load_queries()
        self.notify(f'Consulta renomeada: "{old_name}" -> "{new_name}"')

    # -- Favorite --

    def _handle_favorite(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma consulta.", severity="warning")
            return

        from dbqm.models.query import load_queries, save_queries

        queries = load_queries()
        for q in queries:
            if q.name == name:
                q.is_favorite = not q.is_favorite
                status = "marcada como favorita" if q.is_favorite else "removida dos favoritos"
                break
        else:
            self.notify(f'Consulta "{name}" nao encontrada.', severity="error")
            return

        save_queries(queries)
        self._load_queries()
        self.notify(f'"{name}" {status}!')

    # -- Folder --

    def _handle_folder(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma consulta.", severity="warning")
            return

        from dbqm.models.query import find_query, load_queries

        query = find_query(name)
        if query is None:
            self.notify(f'Consulta "{name}" nao encontrada.', severity="error")
            return

        # Collect existing folder names
        all_queries = load_queries()
        existing_folders = sorted({q.folder for q in all_queries if q.folder})

        self._folder_query_name = name
        modal = FolderModal(current_folder=query.folder, existing_folders=existing_folders)
        self.app.push_screen(modal, callback=self._on_folder_result)

    def _on_folder_result(self, folder: str | None) -> None:
        if folder is None:
            return

        from dbqm.models.query import load_queries, save_queries

        queries = load_queries()
        for q in queries:
            if q.name == self._folder_query_name:
                q.folder = folder
                break
        save_queries(queries)
        self._load_queries()
        label = f'"{folder}"' if folder else "(sem pasta)"
        self.notify(f'"{self._folder_query_name}" movida para {label}!')

    # -- Duplicate --

    def _handle_duplicate(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma consulta.", severity="warning")
            return

        from dbqm.ui.modals.text_input import TextInputModal

        self._dup_source_name = name
        modal = TextInputModal(
            title="Duplicar Consulta",
            message=f'Nome para a copia de "{name}":',
            default=f"{name}_copia",
        )
        self.app.push_screen(modal, callback=self._on_dup_name_result)

    def _on_dup_name_result(self, new_name: str | None) -> None:
        if new_name is None or not new_name.strip():
            return

        new_name = new_name.strip()

        from dbqm.models.query import Query, QueryParam, load_queries, save_queries, find_query

        queries = load_queries()
        if any(q.name == new_name for q in queries):
            self.notify(f'Consulta "{new_name}" ja existe.', severity="error")
            return

        source = find_query(self._dup_source_name)
        if source is None:
            self.notify(f'Consulta "{self._dup_source_name}" nao encontrada.', severity="error")
            return

        # Ask for connection change
        self._dup_new_name = new_name
        self._dup_source = source
        modal = ConnectionPickerModal(source.connection)
        self.app.push_screen(modal, callback=self._on_dup_conn_result)

    def _on_dup_conn_result(self, conn: str | None) -> None:
        from dbqm.models.query import Query, QueryParam, load_queries, save_queries
        from copy import deepcopy

        source = self._dup_source
        new_name = self._dup_new_name
        connection = conn if conn else source.connection

        queries = load_queries()

        new_query = Query(
            name=new_name,
            connection=connection,
            sql=source.sql,
            table=source.table,
            description=source.description,
            params=[QueryParam(name=p.name, description=p.description, default=p.default) for p in source.params],
            columns=list(source.columns),
            column_maps={col: dict(m) for col, m in source.column_maps.items()},
            order_by=source.order_by,
            folder=source.folder,
        )
        queries.append(new_query)
        save_queries(queries)
        self._load_queries()
        self._update_status_bar()
        self.notify(f'Consulta duplicada: "{new_name}"!')

    # -- Remove --

    def _handle_remove(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma consulta.", severity="warning")
            return

        from dbqm.ui.modals.confirm import ConfirmModal

        self._remove_name = name
        modal = ConfirmModal(message=f'Remover consulta "{name}"?')
        self.app.push_screen(modal, callback=self._on_remove_result)

    def _on_remove_result(self, confirmed: bool) -> None:
        if not confirmed:
            return

        from dbqm.models.query import delete_query

        name = self._remove_name
        if delete_query(name):
            self._load_queries()
            self._update_status_bar()
            self.notify(f'Consulta "{name}" removida!')
        else:
            self.notify(f'Consulta "{name}" nao encontrada.', severity="error")

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
