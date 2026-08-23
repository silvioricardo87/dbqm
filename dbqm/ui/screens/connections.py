"""Connection management screen — master list + embedded edit form."""
from __future__ import annotations

import textwrap

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, OptionList, Select, Static, TextArea
from textual.widgets.option_list import Option
from textual import work

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.lista_hierarquica import item_hierarquico, largura_de_quebra
from dbqm.ui.widgets.panel import Panel


DB_TYPE_LABELS = {
    "oracle": "Oracle",
    "sqlserver": "SQL Server",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
}

DB_TYPE_OPTIONS = [
    ("Oracle", "oracle"),
    ("SQL Server", "sqlserver"),
    ("PostgreSQL", "postgresql"),
    ("MySQL", "mysql"),
]

ORACLE_MODE_OPTIONS = [
    ("Conexao direta (host/port/service)", "direct"),
    ("TNS (tnsnames.ora)", "tns"),
]

DEFAULT_PORTS = {
    "oracle": "1521",
    "sqlserver": "1433",
    "postgresql": "5432",
    "mysql": "3306",
}

DEFAULT_HOSTS = {
    "postgresql": "localhost",
    "mysql": "localhost",
}

# Largura de #conn-list-panel (CSS abaixo). Constante de modulo, unica
# fonte pro CSS e pra derivacao da largura de quebra logo adiante — os
# dois nao podem divergir (motivo da rodada anterior: 60 de largura
# assumida contra um painel de 42 inteiro, que so por si ja era menor que
# o "limite" da descricao).
_LARGURA_PAINEL_LISTA = 42

# Largura de fato disponivel pro TEXTO da descricao: o que sobra do
# painel depois da borda do Panel, do padding do corpo, do padding do
# OptionList, da barra de rolagem (pior caso) e do recuo que a propria
# linha de contexto consome. A conta em si mora em `lista_hierarquica`
# (`largura_de_quebra`), junto do recuo que ela desconta e do relato das
# quatro rodadas que ela custou; o que fica aqui e so a largura DESTE
# painel, que e escolha desta tela. Medido nos dois estados: com poucas
# conexoes (sem rolagem), OptionList.content_region.width fica em 36
# (bate com a conta sem o desconto da barra); com conexoes suficientes
# pra rolar, OptionList.scrollable_content_region.width cai pra 34 —
# exatamente os 2 da barra a menos.
_DESCRICAO_LARGURA = largura_de_quebra(_LARGURA_PAINEL_LISTA)
_DESCRICAO_MAX_LINHAS = 2


def _format_description(description: str) -> str:
    """Preview da descricao em ate `_DESCRICAO_MAX_LINHAS` linhas.

    Corta por LINHAS renderizadas (aproximadas por `_DESCRICAO_LARGURA`),
    nao pelo total de caracteres: sem nenhum limite, uma descricao longa
    empurraria as outras conexoes da lista pra fora da tela — o contexto
    de `item_hierarquico` ja da a ela sua propria linha recuada, mas isso
    nao limita quantas linhas ela toma.
    """
    if not description:
        return ""
    flat = " ".join(description.split())
    linhas = textwrap.wrap(flat, width=_DESCRICAO_LARGURA) or [""]
    if len(linhas) <= _DESCRICAO_MAX_LINHAS:
        return "\n".join(linhas)
    linhas = linhas[:_DESCRICAO_MAX_LINHAS]
    ultima = linhas[-1].rstrip()
    if len(ultima) > _DESCRICAO_LARGURA - 3:
        ultima = ultima[: _DESCRICAO_LARGURA - 3].rstrip()
    linhas[-1] = ultima + "..."
    return "\n".join(linhas)


class ConnectionsScreen(Vertical):
    """Screen widget for managing database connections.

    Master-detail layout: a connection list (CONEXOES) on the left and an
    embedded edit form (EDICAO) on the right. Selecting an item in the list
    loads it into the form; Nova/Testar/Salvar/Excluir act on the form.
    """

    DEFAULT_CSS = """
    ConnectionsScreen {
        height: 1fr;
    }
    ConnectionsScreen #conn-body {
        height: 1fr;
    }
    ConnectionsScreen #conn-list-panel {
        width: __LARGURA_PAINEL_LISTA__;
    }
    ConnectionsScreen #conn-form-panel {
        width: 1fr;
    }
    ConnectionsScreen #conn-empty {
        height: auto;
    }
    ConnectionsScreen #conn-list {
        height: 1fr;
    }
    ConnectionsScreen #conn-btn-new {
        width: 100%;
        margin-top: 1;
    }
    ConnectionsScreen #conn-form-scroll {
        height: 1fr;
    }
    ConnectionsScreen .field-label {
        margin-top: 1;
        height: 1;
        color: $text-muted;
    }
    ConnectionsScreen Input {
        width: 100%;
    }
    ConnectionsScreen Select {
        width: 100%;
    }
    ConnectionsScreen #conn-form-desc {
        height: 5;
        width: 100%;
    }
    ConnectionsScreen #conn-form-buttons {
        margin-top: 1;
        height: auto;
        width: 100%;
        /* Ancorado a esquerda, na coluna dos campos do formulario que
           estes botoes operam (secao 7 da gramatica). */
    }
    ConnectionsScreen #conn-form-buttons Button {
        margin: 0 1 0 0;
    }
    /* Acao destrutiva SEPARADA das demais (secao 7): quatro colunas de
       respiro em vez de uma, para que Excluir nao fique encostado em
       Salvar. Afastamento horizontal e nao uma fila propria de proposito
       — uma segunda fila custaria tres linhas do formulario, que a 80x24
       ja transborda.

       DOIS ids no seletor, e nao um: a regra acima
       (`#conn-form-buttons Button`) vale 1 id + 1 tipo e o `margin`
       curto dela zera o `margin-left`. Com um id so esta regra PERDIA e
       virava CSS morto — visto no renderizado a 120 colunas, onde o
       espaco antes de Excluir continuava sendo de uma coluna.

       O que as tres colunas custam, medido na DBQMApp real (aba Conexoes,
       30 linhas, uma largura por vez): a caixa do `Excluir` so fica
       inteira a partir de 97 colunas com esta margem, contra 94 sem ela;
       o rotulo, 94 contra 93. Nenhum acesso se perde — `X Excluir`
       continua na ActionBar, e a 80x24 o botao ja estava fora de vista
       antes desta fase. Fica escrito porque a separacao da acao
       destrutiva e uma escolha com preco, nao um ganho puro. */
    ConnectionsScreen #conn-form-buttons #conn-btn-delete {
        margin-left: 4;
    }
    """.replace("__LARGURA_PAINEL_LISTA__", str(_LARGURA_PAINEL_LISTA))

    # Maps a logical field name to its (label id, widget id) — used to
    # show/hide field groups depending on the selected db type/mode.
    _FIELD_GROUPS = {
        "mode": ("#conn-form-mode-label", "#conn-form-mode"),
        "service": ("#conn-form-service-label", "#conn-form-service"),
        "database": ("#conn-form-database-label", "#conn-form-database"),
        "tns_path": ("#conn-form-tns-path-label", "#conn-form-tns-path"),
        "tns_name": ("#conn-form-tns-name-label", "#conn-form-tns-name"),
        "host": ("#conn-form-host-label", "#conn-form-host"),
        "port": ("#conn-form-port-label", "#conn-form-port"),
    }

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._loaded_name: str | None = None
        self._remove_name: str | None = None
        self._rename_old_name: str | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="conn-body"):
            with Panel("🔌  CONEXOES", id="conn-list-panel"):
                yield EmptyState(
                    o_que="Conexoes",
                    porque="O dbqm precisa de pelo menos uma conexao para executar consultas",
                    acao_rotulo="Adicionar conexao",
                    acao_id="adicionar-conexao",
                    id="conn-empty",
                )
                yield OptionList(id="conn-list")
                yield Button("Nova", id="conn-btn-new")

            with Panel("📝  EDICAO", accent=True, id="conn-form-panel"):
                with VerticalScroll(id="conn-form-scroll"):
                    yield Static("Nome:", classes="field-label")
                    yield Input(id="conn-form-name")

                    yield Static("Tipo de banco:", classes="field-label")
                    yield Select(
                        DB_TYPE_OPTIONS, prompt="Selecione o tipo", id="conn-form-type"
                    )

                    yield Static("Modo:", classes="field-label", id="conn-form-mode-label")
                    yield Select(
                        ORACLE_MODE_OPTIONS, prompt="Selecione o modo", id="conn-form-mode"
                    )

                    yield Static("Host:", classes="field-label", id="conn-form-host-label")
                    yield Input(id="conn-form-host")

                    yield Static("Porta:", classes="field-label", id="conn-form-port-label")
                    yield Input(id="conn-form-port")

                    yield Static(
                        "Service Name:", classes="field-label", id="conn-form-service-label"
                    )
                    yield Input(id="conn-form-service")

                    yield Static(
                        "Caminho tnsnames.ora:",
                        classes="field-label",
                        id="conn-form-tns-path-label",
                    )
                    yield Input(id="conn-form-tns-path")

                    yield Static(
                        "TNS Name:", classes="field-label", id="conn-form-tns-name-label"
                    )
                    yield Input(id="conn-form-tns-name")

                    yield Static(
                        "Database:", classes="field-label", id="conn-form-database-label"
                    )
                    yield Input(id="conn-form-database")

                    yield Static("Usuario:", classes="field-label")
                    yield Input(id="conn-form-user")

                    yield Static("Senha:", classes="field-label")
                    yield Input(password=True, id="conn-form-pass")

                    yield Static("Descricao (opcional):", classes="field-label")
                    yield TextArea(id="conn-form-desc")

                with Horizontal(id="conn-form-buttons"):
                    yield Button("Testar", variant="warning", id="conn-btn-test")
                    yield Button("Salvar", variant="primary", id="conn-btn-save")
                    yield Button("Excluir", variant="error", id="conn-btn-delete")

    def on_mount(self) -> None:
        self._load_connections()
        # Widgets already start blank/unselected as composed — just apply
        # the "no type selected" field visibility instead of writing to
        # every field (avoids a burst of reactive Changed messages during
        # the initial mount cascade that raced with tab-activation timing).
        self._apply_field_visibility("", "")
        self._set_actions()
        self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        # This runs from a deferred call_after_refresh scheduled at mount
        # time. If the user has already switched to another tab by the time
        # it fires, focusing a widget here would steal focus back and flip
        # TabbedContent.active (it tracks focus location via TabPaneFocused)
        # — so bail out when this screen's hosting tab is no longer active.
        # (No-op when not hosted inside a TabbedContent, e.g. in tests.)
        try:
            from textual.widgets import TabbedContent, TabPane

            tab_pane = next(
                (a for a in self.ancestors_with_self if isinstance(a, TabPane)), None
            )
            if tab_pane is not None:
                tabbed = self.app.query_one(TabbedContent)
                if tabbed.active != tab_pane.id:
                    return
        except Exception:
            pass

        option_list = self.query_one("#conn-list", OptionList)
        if option_list.display and option_list.option_count:
            option_list.focus()
        else:
            self.query_one("#conn-form-name", Input).focus()

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def _load_connections(self) -> None:
        from dbqm.models.connection import load_connections

        connections = load_connections()
        option_list = self.query_one("#conn-list", OptionList)
        empty_msg = self.query_one("#conn-empty", EmptyState)
        new_btn = self.query_one("#conn-btn-new", Button)

        option_list.clear_options()

        if not connections:
            empty_msg.display = True
            option_list.display = False
            # A acao de criar ja vive dentro do EmptyState; duplicar o botao
            # "Nova" aqui so repetiria a mesma acao duas vezes na tela.
            new_btn.display = False
            return

        empty_msg.display = False
        option_list.display = True
        new_btn.display = True

        for conn in connections:
            db_label = DB_TYPE_LABELS.get(conn.db_type, conn.db_type)
            if conn.db_type == "oracle" and conn.mode == "tns":
                db_label = "Oracle/TNS"
            # Identidade e o nome, sozinho: e o que a pessoa procura numa
            # lista de conexoes. Tipo+alvo desambiguam entradas parecidas;
            # a descricao e contexto opcional, recuado e apagado.
            desambiguacao = f"{db_label} - {conn.display_target()}"
            contexto = _format_description(conn.description)
            item = item_hierarquico(conn.name, desambiguacao, contexto)
            option_list.add_option(Option(item, id=conn.name))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "conn-list":
            return
        name = str(event.option.id) if event.option.id else None
        if not name:
            return
        from dbqm.models.connection import find_connection

        conn = find_connection(name)
        if conn is None:
            self.notify(f'Conexao "{name}" nao encontrada.', severity="error")
            return
        self._load_into_form(conn)

    def _get_selected_name(self) -> str | None:
        """Get the connection name currently highlighted in the list."""
        option_list = self.query_one("#conn-list", OptionList)
        if not option_list.display or option_list.option_count == 0:
            return None
        idx = option_list.highlighted
        if idx is None:
            return None
        try:
            option = option_list.get_option_at_index(idx)
        except Exception:
            return None
        return str(option.id) if option.id else None

    def _select_in_list(self, name: str) -> None:
        """Highlight and load a connection by name, if present in the list."""
        option_list = self.query_one("#conn-list", OptionList)
        try:
            idx = option_list.get_option_index(name)
        except Exception:
            return
        option_list.highlighted = idx
        from dbqm.models.connection import find_connection

        conn = find_connection(name)
        if conn is not None:
            self._load_into_form(conn)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _set_actions(self) -> None:
        try:
            action_bar = self.app.query_one(ActionBar)
        except Exception:
            return
        actions = [
            Action("Nova", "N", "conn_new"),
            Action("Testar", "T", "conn_test"),
            Action("Salvar", "S", "conn_save"),
            Action("Renomear", "R", "conn_rename"),
            Action("Excluir", "X", "conn_remove"),
        ]
        action_bar.set_actions(actions)

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id
        if action == "conn_new":
            self._handle_new()
        elif action == "conn_test":
            self._handle_test()
        elif action == "conn_save":
            self._handle_save()
        elif action == "conn_rename":
            self._handle_rename()
        elif action == "conn_remove":
            self._handle_remove()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id in ("conn-btn-new", "adicionar-conexao"):
            self._handle_new()
        elif btn_id == "conn-btn-test":
            self._handle_test()
        elif btn_id == "conn-btn-save":
            self._handle_save()
        elif btn_id == "conn-btn-delete":
            self._handle_remove()

    # ------------------------------------------------------------------
    # Form — load / clear / field visibility
    # ------------------------------------------------------------------

    def _load_into_form(self, conn) -> None:
        """Populate the embedded form with an existing connection."""
        from dbqm.core.crypto import decrypt

        self._loaded_name = conn.name

        name_input = self.query_one("#conn-form-name", Input)
        name_input.value = conn.name
        name_input.disabled = True

        type_select = self.query_one("#conn-form-type", Select)
        valid_types = [v for _, v in DB_TYPE_OPTIONS]
        if conn.db_type in valid_types:
            type_select.value = conn.db_type
        else:
            type_select.clear()

        mode = conn.mode or "direct"
        if conn.db_type == "oracle":
            mode_select = self.query_one("#conn-form-mode", Select)
            valid_modes = [v for _, v in ORACLE_MODE_OPTIONS]
            mode_select.value = mode if mode in valid_modes else "direct"

        self._apply_field_visibility(conn.db_type, mode)

        self.query_one("#conn-form-host", Input).value = conn.host or ""
        self.query_one("#conn-form-port", Input).value = str(conn.port) if conn.port else ""
        self.query_one("#conn-form-service", Input).value = conn.service_name or ""
        self.query_one("#conn-form-tns-path", Input).value = conn.tns_path or ""
        self.query_one("#conn-form-tns-name", Input).value = conn.tns_name or ""
        self.query_one("#conn-form-database", Input).value = conn.database or ""
        self.query_one("#conn-form-user", Input).value = conn.user or ""

        password = ""
        if conn.password:
            try:
                password = decrypt(conn.password)
            except Exception:
                password = ""
        self.query_one("#conn-form-pass", Input).value = password

        self.query_one("#conn-form-desc", TextArea).text = conn.description or ""

    def _clear_form(self) -> None:
        """Reset the form to a blank state, ready for a new connection."""
        self._loaded_name = None

        name_input = self.query_one("#conn-form-name", Input)
        name_input.value = ""
        name_input.disabled = False

        self.query_one("#conn-form-type", Select).clear()
        self.query_one("#conn-form-mode", Select).clear()

        for field_id in (
            "#conn-form-host",
            "#conn-form-port",
            "#conn-form-service",
            "#conn-form-tns-path",
            "#conn-form-tns-name",
            "#conn-form-database",
            "#conn-form-user",
            "#conn-form-pass",
        ):
            self.query_one(field_id, Input).value = ""

        self.query_one("#conn-form-desc", TextArea).text = ""
        self._apply_field_visibility("", "")

    def _current_db_type(self) -> str:
        val = self.query_one("#conn-form-type", Select).value
        return "" if val == Select.NULL else str(val)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "conn-form-type":
            db_type = "" if event.value == Select.NULL else str(event.value)
            mode_select = self.query_one("#conn-form-mode", Select)
            if db_type == "oracle":
                if mode_select.value == Select.NULL:
                    mode_select.value = "direct"
                mode = str(mode_select.value)
            else:
                mode = ""
            self._apply_defaults(db_type)
            self._apply_field_visibility(db_type, mode)
        elif event.select.id == "conn-form-mode":
            db_type = self._current_db_type()
            mode = "" if event.value == Select.NULL else str(event.value)
            self._apply_field_visibility(db_type, mode)

    def _apply_defaults(self, db_type: str) -> None:
        """Fill sensible default host/port for a freshly-selected db type
        (only when the field is still empty, so edits are never clobbered)."""
        host_input = self.query_one("#conn-form-host", Input)
        port_input = self.query_one("#conn-form-port", Input)
        if not host_input.value:
            host_input.value = DEFAULT_HOSTS.get(db_type, "")
        if not port_input.value:
            port_input.value = DEFAULT_PORTS.get(db_type, "")

    def _apply_field_visibility(self, db_type: str, mode: str) -> None:
        is_oracle = db_type == "oracle"
        is_tns = is_oracle and mode == "tns"
        has_type = bool(db_type)

        self._set_visible("mode", is_oracle)
        self._set_visible("service", is_oracle and not is_tns)
        self._set_visible("database", has_type and not is_oracle)
        self._set_visible("tns_path", is_tns)
        self._set_visible("tns_name", is_tns)
        self._set_visible("host", has_type and not is_tns)
        self._set_visible("port", has_type and not is_tns)

    def _set_visible(self, key: str, visible: bool) -> None:
        label_id, field_id = self._FIELD_GROUPS[key]
        self.query_one(label_id).display = visible
        self.query_one(field_id).display = visible

    # ------------------------------------------------------------------
    # New
    # ------------------------------------------------------------------

    def _handle_new(self) -> None:
        self._clear_form()
        self.query_one("#conn-form-name", Input).focus()

    # ------------------------------------------------------------------
    # Test
    # ------------------------------------------------------------------

    def _handle_test(self) -> None:
        name = self.query_one("#conn-form-name", Input).value.strip()
        if not name:
            self.notify("Informe o nome da conexao.", severity="warning")
            return
        self.notify(f"Testando {name}...")
        self._run_test(name)

    @work(thread=True)
    def _run_test(self, name: str) -> None:
        from dbqm.core.db_manager import test_connection
        from dbqm.models.connection import find_connection

        try:
            conn = find_connection(name)
            if conn is None:
                self.app.call_from_thread(
                    self.notify, f'Conexao "{name}" nao encontrada.', severity="error"
                )
                return

            success, msg = test_connection(conn)
            severity = "information" if success else "error"
            self.app.call_from_thread(self.notify, msg, severity=severity, timeout=6)
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Erro ao testar conexao: {e}", severity="error", timeout=8
            )

    # ------------------------------------------------------------------
    # Save (create or update)
    # ------------------------------------------------------------------

    def _val(self, field_id: str) -> str:
        return self.query_one(field_id, Input).value.strip()

    def _int_val(self, field_id: str, default: int) -> int:
        val = self._val(field_id)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _collect_form_values(self) -> dict | None:
        """Collect all form field values into a dict, validating required ones."""
        name = self.query_one("#conn-form-name", Input).value.strip()
        if not name:
            self.notify("Nome obrigatorio.", severity="error")
            return None

        type_select = self.query_one("#conn-form-type", Select)
        if type_select.value == Select.NULL:
            self.notify("Selecione o tipo de banco.", severity="error")
            return None
        db_type = str(type_select.value)

        result: dict = {"name": name, "db_type": db_type}

        if db_type == "oracle":
            mode_select = self.query_one("#conn-form-mode", Select)
            mode = str(mode_select.value) if mode_select.value != Select.NULL else "direct"
            result["mode"] = mode

            if mode == "tns":
                result["tns_path"] = self._val("#conn-form-tns-path")
                result["tns_name"] = self._val("#conn-form-tns-name")
            else:
                result["host"] = self._val("#conn-form-host")
                result["port"] = self._int_val("#conn-form-port", 1521)
                result["service_name"] = self._val("#conn-form-service")
        else:
            result["host"] = self._val("#conn-form-host")
            result["port"] = self._int_val("#conn-form-port", int(DEFAULT_PORTS.get(db_type, "0")))
            result["database"] = self._val("#conn-form-database")

        result["user"] = self._val("#conn-form-user")
        result["password"] = self._val("#conn-form-pass")

        desc_widget = self.query_one("#conn-form-desc", TextArea)
        result["description"] = desc_widget.text.strip()

        return result

    def _handle_save(self) -> None:
        values = self._collect_form_values()
        if values is None:
            return

        from dbqm.core.crypto import encrypt
        from dbqm.models.connection import Connection, load_connections, save_connections

        connections = load_connections()
        name = values["name"]
        existing = next((c for c in connections if c.name == name), None)

        password = values.get("password", "")
        if password:
            password = encrypt(password)
        elif existing is not None:
            password = existing.password
        else:
            password = ""

        if existing is not None:
            existing.db_type = values["db_type"]
            existing.user = values.get("user", "")
            existing.password = password
            existing.mode = values.get("mode")
            existing.host = values.get("host")
            existing.port = values.get("port")
            existing.service_name = values.get("service_name")
            existing.database = values.get("database")
            existing.tns_path = values.get("tns_path")
            existing.tns_name = values.get("tns_name")
            existing.description = values.get("description", "")
            message = f'Conexao "{name}" atualizada!'
        else:
            conn = Connection(
                name=name,
                db_type=values["db_type"],
                user=values.get("user", ""),
                password=password,
                mode=values.get("mode"),
                host=values.get("host"),
                port=values.get("port"),
                service_name=values.get("service_name"),
                database=values.get("database"),
                tns_path=values.get("tns_path"),
                tns_name=values.get("tns_name"),
                description=values.get("description", ""),
            )
            connections.append(conn)
            message = f'Conexao "{name}" criada!'

        save_connections(connections)
        self._load_connections()
        self._update_status_bar()
        self._select_in_list(name)
        self.notify(message)

    # ------------------------------------------------------------------
    # Rename
    # ------------------------------------------------------------------

    def _handle_rename(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma conexao.", severity="warning")
            return

        from dbqm.ui.modals.text_input import TextInputModal

        modal = TextInputModal(title="Renomear Conexao", message=f'Novo nome para "{name}":', default=name)
        self._rename_old_name = name
        self.app.push_screen(modal, callback=self._on_rename_result)

    def _on_rename_result(self, new_name: str | None) -> None:
        if new_name is None or not new_name.strip():
            return

        new_name = new_name.strip()
        old_name = self._rename_old_name

        if new_name == old_name:
            return

        from dbqm.models.connection import load_connections, save_connections

        connections = load_connections()

        if any(c.name == new_name for c in connections):
            self.notify(f'Conexao "{new_name}" ja existe.', severity="error")
            return

        for conn in connections:
            if conn.name == old_name:
                conn.name = new_name
                break
        save_connections(connections)

        # Update queries that reference the old name
        from dbqm.models.query import load_queries, save_queries

        queries = load_queries()
        updated = False
        for q in queries:
            if q.connection == old_name:
                q.connection = new_name
                updated = True
        if updated:
            save_queries(queries)

        self._load_connections()
        if self._loaded_name == old_name:
            self._select_in_list(new_name)
        self.notify(f'Conexao renomeada: "{old_name}" -> "{new_name}"')

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _handle_remove(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma conexao.", severity="warning")
            return

        from dbqm.ui.modals.confirm import ConfirmModal

        self._remove_name = name
        modal = ConfirmModal(message=f'Remover conexao "{name}"?')
        self.app.push_screen(modal, callback=self._on_remove_result)

    def _on_remove_result(self, confirmed: bool) -> None:
        if not confirmed:
            return

        from dbqm.models.connection import delete_connection

        name = self._remove_name
        if delete_connection(name):
            if self._loaded_name == name:
                self._clear_form()
            self._load_connections()
            self._update_status_bar()
            self.notify(f'Conexao "{name}" removida!')
        else:
            self.notify(f'Conexao "{name}" nao encontrada.', severity="error")

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
