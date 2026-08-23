"""Config portability screen — export/import configurations."""
from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Checkbox, Input, OptionList, Static

from dbqm.ui.widgets.hierarchical_list import NamedOption, hierarchical_item
from dbqm.ui.widgets.panel import Panel


class ConfigPortScreen(Vertical):
    """Screen widget for exporting and importing configurations.

    Export flow: select items, enter password, create .dbqm bundle.
    Import flow: enter file path, enter password, import.

    Pass initial_mode="export" or "import" to skip mode selection.

    A saida desta tela e o `Esc`, tratado por quem a hospeda
    (`SettingsScreen.back_to_start`, alcancado por
    `DBQMApp.action_go_back`) e anunciado por
    `SettingsScreen._set_actions`. Houve aqui um botao "Voltar" que
    montava uma `SettingsScreen` nova dentro de `#screen-area`, container
    removido em e02b8a8 (v1.17.0): por seis semanas ele so notificava
    "Erro: No nodes match '#screen-area'". A Task 7 ressuscitou a rota e a
    Task 8 tirou o botao — voltar e navegacao, e a secao 7 da gramatica
    proibe botao que navega. Sair do formulario de exportacao leva de
    volta as Configuracoes, nao a escolha de modo; reentrar pela lista
    reabre na escolha de modo (`on_reopen`).
    """

    #: (chave, identidade, desambiguacao) das duas fases fundas. A chave
    #: viaja como DADO na opcao (`NamedOption.nome`), nunca como `id`.
    MODOS = (
        ("export", "Exportar", "gera um .dbqm protegido por senha"),
        ("import", "Importar", "le um .dbqm gerado por outro dbqm"),
    )

    DEFAULT_CSS = """
    ConfigPortScreen {
        height: 1fr;
        padding: 1 2;
        /* Medido em 80x24 (`tests/design/test_transbordo_vertical.py`):
           quem passa da dobra e o formulario de EXPORTACAO — 29 linhas,
           tres checkboxes mais dois pares rotulo+senha mais a barra de
           acoes, contra 22 do de importacao e 22 da escolha de modo, que
           cabem. Como `Panel` tem `height: auto` aqui, o painel cresce
           alem da tela e e ESTE `overflow-y` que rola: sem ele o botao
           Exportar ficaria fora de alcance. */
        overflow-y: auto;
    }
    ConfigPortScreen Panel {
        height: auto;
    }
    /* `auto`: a lista mede as duas entradas e para. Com `1fr` ela
       esticaria ate o fim do painel e a moldura viraria uma caixa quase
       vazia com o conteudo encostado no topo. */
    ConfigPortScreen #cp-mode-list {
        height: auto;
    }

    /* -- Export phase -- */
    ConfigPortScreen .cp-checks {
        height: auto;
        margin-bottom: 1;
    }
    ConfigPortScreen .cp-checks Checkbox {
        margin-bottom: 0;
        height: auto;
    }
    ConfigPortScreen .cp-password-row {
        height: auto;
        margin-bottom: 1;
    }
    ConfigPortScreen .cp-password-row Input {
        width: 40;
    }
    ConfigPortScreen .cp-password-row Static {
        width: auto;
        padding: 0 0 0 0;
    }

    /* -- Import phase -- */
    ConfigPortScreen .cp-field {
        height: auto;
        margin-bottom: 1;
    }
    ConfigPortScreen .cp-field-label {
        height: auto;
        text-style: bold;
    }
    ConfigPortScreen .cp-field Input {
        width: 60;
    }

    /* -- Actions -- */
    /* Ancoradas a esquerda, encostadas no formulario que executam
       (secao 7 da gramatica). Sobrou UM botao por fase: o "Voltar" que
       dividia a barra com ele era navegacao, e navegacao nao e botao. */
    ConfigPortScreen .cp-actions {
        height: auto;
        margin-top: 1;
    }
    ConfigPortScreen .cp-actions Button {
        margin-right: 1;
    }
    """

    def __init__(self, initial_mode: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._initial_mode = initial_mode

    def compose(self) -> ComposeResult:
        # Phase 1: mode selection
        # Lista, e nao dois botoes: escolher entre exportar e importar e
        # NAVIGATION — leva a um formulario, nao executa nada. Dois botoes
        # lado a lado eram um menu disfarcado, a mesma forma que o menu de
        # Ferramentas tinha (secao 7 da gramatica).
        with Panel("🔄  EXPORTAR OU IMPORTAR", id="cp-mode-phase"):
            yield OptionList(id="cp-mode-list")

        # Phase 2: export form
        with Panel("⬆️  EXPORTAR CONFIGURACOES", id="cp-export-phase"):
            with Vertical(classes="cp-checks"):
                yield Checkbox("Conexoes", id="cp-chk-connections", value=True)
                yield Checkbox("Consultas", id="cp-chk-queries", value=True)
                yield Checkbox("Grupos", id="cp-chk-groups", value=True)
            with Vertical(classes="cp-password-row"):
                yield Static("Senha:", classes="cp-field-label")
                yield Input(placeholder="Senha para proteger o arquivo", password=True, id="cp-export-password")
            with Vertical(classes="cp-password-row"):
                yield Static("Confirmar senha:", classes="cp-field-label")
                yield Input(placeholder="Confirme a senha", password=True, id="cp-export-password-confirm")
            with Horizontal(classes="cp-actions"):
                yield Button("Exportar", id="cp-do-export", variant="primary")

        # Phase 3: import form
        with Panel("⬇️  IMPORTAR CONFIGURACOES", id="cp-import-phase"):
            with Vertical(classes="cp-field"):
                yield Static("Caminho do arquivo .dbqm:", classes="cp-field-label")
                yield Input(placeholder="Ex: C:\\exports\\config.dbqm", id="cp-import-path")
            with Vertical(classes="cp-field"):
                yield Static("Senha do arquivo:", classes="cp-field-label")
                yield Input(placeholder="Senha usada na exportacao", password=True, id="cp-import-password")
            with Horizontal(classes="cp-actions"):
                yield Button("Importar", id="cp-do-import", variant="primary")

    def on_mount(self) -> None:
        lista = self.query_one("#cp-mode-list", OptionList)
        lista.clear_options()
        for chave, identidade, desambiguacao in self.MODOS:
            lista.add_option(
                NamedOption(hierarchical_item(identidade, desambiguacao), chave)
            )
        if self._initial_mode == "export":
            self._show_export_phase()
        elif self._initial_mode == "import":
            self._show_import_phase()
        else:
            self._show_mode_phase()
        self.call_after_refresh(self._set_initial_focus)

    def on_reopen(self) -> None:
        """Volta a fase inicial quando a tela e reaberta pela lista.

        A tela continua MONTADA depois do `Esc` — e ate aqui reabria na fase
        em que tinha ficado: quem exportou uma vez reencontrava o formulario
        de exportacao, sem o formulario de importacao a vista, embora a
        entrada que acabou de escolher se chame "Exportar / Importar".

        A restricao que mantem as telas montadas protege um worker vivo (o
        download de 150+ MB do Instant Client, que escreve na propria
        arvore). Aqui nao ha nada disso: a fase e so qual dos tres paineis
        esta com `display` ligado, os workers de exportar/importar acham
        seus campos por id independentemente da fase visivel, e o que a
        pessoa digitou continua nos `Input`.
        """
        self.on_mount()

    def _set_initial_focus(self) -> None:
        try:
            if self._initial_mode == "export":
                self.query_one("#cp-chk-connections", Checkbox).focus()
            elif self._initial_mode == "import":
                self.query_one("#cp-import-path", Input).focus()
            else:
                self.query_one("#cp-mode-list", OptionList).focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    def _show_mode_phase(self) -> None:
        self.query_one("#cp-mode-phase").display = True
        self.query_one("#cp-export-phase").display = False
        self.query_one("#cp-import-phase").display = False

    def _show_export_phase(self) -> None:
        self.query_one("#cp-mode-phase").display = False
        self.query_one("#cp-export-phase").display = True
        self.query_one("#cp-import-phase").display = False

    def _show_import_phase(self) -> None:
        self.query_one("#cp-mode-phase").display = False
        self.query_one("#cp-export-phase").display = False
        self.query_one("#cp-import-phase").display = True

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        if event.option_list.id != "cp-mode-list":
            return
        event.stop()
        chave = getattr(event.option, "name", "")
        if chave == "export":
            self._show_export_phase()
        elif chave == "import":
            self._show_import_phase()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "cp-do-export":
            self._handle_export()
        elif btn_id == "cp-do-import":
            self._handle_import()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _handle_export(self) -> None:
        password = self.query_one("#cp-export-password", Input).value.strip()
        password_confirm = self.query_one("#cp-export-password-confirm", Input).value.strip()

        if not password:
            self.notify("Senha obrigatoria para exportar.", severity="warning")
            return

        if password != password_confirm:
            self.notify("Senhas nao conferem.", severity="error")
            return

        include_connections = self.query_one("#cp-chk-connections", Checkbox).value
        include_queries = self.query_one("#cp-chk-queries", Checkbox).value
        include_groups = self.query_one("#cp-chk-groups", Checkbox).value

        if not (include_connections or include_queries or include_groups):
            self.notify("Selecione ao menos um item para exportar.", severity="warning")
            return

        self._run_export(password, include_connections, include_queries, include_groups)

    @work(thread=True)
    def _run_export(
        self,
        password: str,
        include_connections: bool,
        include_queries: bool,
        include_groups: bool,
    ) -> None:
        from dbqm.core.config_portability import export_configs

        try:
            path = export_configs(
                password=password,
                include_connections=include_connections,
                include_queries=include_queries,
                include_groups=include_groups,
            )
            self.app.call_from_thread(
                self.notify, f"Configuracoes exportadas: {path}", severity="information", timeout=8
            )
            self.app.call_from_thread(self._clear_export_form)
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Erro ao exportar: {e}", severity="error", timeout=8
            )

    def _clear_export_form(self) -> None:
        self.query_one("#cp-export-password", Input).value = ""
        self.query_one("#cp-export-password-confirm", Input).value = ""

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _handle_import(self) -> None:
        filepath = self.query_one("#cp-import-path", Input).value.strip().strip('"').strip("'")
        password = self.query_one("#cp-import-password", Input).value.strip()

        if not filepath:
            self.notify("Informe o caminho do arquivo .dbqm.", severity="warning")
            return

        if not Path(filepath).exists():
            self.notify("Arquivo nao encontrado.", severity="error")
            return

        if not password:
            self.notify("Informe a senha do arquivo.", severity="warning")
            return

        self._run_import(filepath, password)

    @work(thread=True)
    def _run_import(self, filepath: str, password: str) -> None:
        from dbqm.core.config_portability import import_configs

        try:
            summary = import_configs(filepath, password)
            total = summary["connections"] + summary["queries"] + summary["groups"]
            parts = []
            if summary["connections"]:
                parts.append(f'{summary["connections"]} conexoes')
            if summary["queries"]:
                parts.append(f'{summary["queries"]} consultas')
            if summary["groups"]:
                parts.append(f'{summary["groups"]} grupos')
            if summary["skipped"]:
                parts.append(f'{summary["skipped"]} ignorados (duplicados)')

            if total > 0:
                msg = f"Importado: {', '.join(parts)}"
                self.app.call_from_thread(self.notify, msg, severity="information", timeout=8)
            else:
                msg = f"Nenhuma configuracao nova importada. {summary['skipped']} duplicados ignorados."
                self.app.call_from_thread(self.notify, msg, severity="warning", timeout=8)

            self.app.call_from_thread(self._clear_import_form)
            self.app.call_from_thread(self._update_status_bar)
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Erro ao importar: {e}", severity="error", timeout=8
            )

    def _clear_import_form(self) -> None:
        self.query_one("#cp-import-path", Input).value = ""
        self.query_one("#cp-import-password", Input).value = ""

    def _update_status_bar(self) -> None:
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
