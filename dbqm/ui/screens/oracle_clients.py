"""Manage Oracle Instant Client installations under ~/.dbqm/clients/.

Shows the detected host platform, currently installed clients, and the
catalog of downloadable Basic packages for that platform. Install runs
in a background worker so the UI stays responsive on a 150+ MB download.
"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, DataTable, ProgressBar, Static
from textual import work

from dbqm.core import oracle_client_installer as oci
from dbqm.core.paths import CLIENTS_DIR
from dbqm.ui.modals.confirm import ConfirmModal
from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.panel import Panel


class OracleClientsScreen(Vertical):
    """Screen for downloading/extracting/removing Oracle Instant Clients."""

    DEFAULT_CSS = """
    OracleClientsScreen {
        height: 1fr;
        padding: 1 2;
        /* With one client installed the three framed sections go past the
           fold of a 24-line terminal (41 lines measured at 80x24, see
           `tests/design/test_vertical_overflow.py`) and the screen
           scrolls, with the overflow visible. The unframed version of this
           screen measured 59 and did NOT scroll — `Vertical` is born with
           `overflow: hidden`, and the DISPONIVEIS section simply did not
           exist for anyone who only had 24 lines. It is this `overflow-y`
           that pays for the chrome. */
        overflow-y: auto;
    }
    OracleClientsScreen Panel {
        height: auto;
        margin-bottom: 1;
    }
    /* A button bar is as tall as a button. Without this it inherits
       `Horizontal`'s own `height: 1fr` and, inside a panel body of
       automatic height, stretches up to the height of the CONTAINER: the
       two bottom panels were born with 23 lines each (instead of 12 and
       14) and pushed the DISPONIVEIS section to y=23, below the fold. */
    OracleClientsScreen .oc-actions {
        height: auto;
    }
    /* Two lines of information do not call for an 11-line box. With the
       body's vertical padding and one margin per line, this panel spent 11
       to state the platform and the directory — and it was the one pushing
       CLIENTS INSTALADOS off the screen when the initial focus landed
       there (`_set_initial_focus`). Dense and marginless it fits in 6, and
       the screen opens showing the first two panels. */
    OracleClientsScreen #oc-platform {
        height: auto;
    }
    OracleClientsScreen #oc-clients-dir {
        height: auto;
    }
    OracleClientsScreen #oc-installed-table {
        height: auto;
        max-height: 8;
        margin-bottom: 1;
    }
    OracleClientsScreen #oc-available-table {
        height: auto;
        max-height: 8;
        margin-bottom: 1;
    }
    OracleClientsScreen #oc-progress-row {
        height: auto;
        margin-top: 1;
        display: none;
    }
    OracleClientsScreen #oc-progress-bar {
        width: 1fr;
    }
    OracleClientsScreen #oc-status {
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }
    OracleClientsScreen Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._host = oci.detect_host_platform()
        self._available: list[oci.ClientPackage] = list(oci.available_clients(self._host))
        self._installed: list[oci.InstalledClient] = []
        self._busy = False

    def compose(self) -> ComposeResult:
        with Panel(
            "🖥️  PLATAFORMA DETECTADA",
            id="oc-platform-panel",
            dense=True,
        ):
            yield Static(
                f"[b]{oci.host_platform_label(self._host)}[/b]   "
                f"[dim]({self._host[0]}/{self._host[1]})[/dim]",
                id="oc-platform",
                markup=True,
            )
            yield Static(
                f"[dim]Diretorio de instalacao:[/] {CLIENTS_DIR}",
                id="oc-clients-dir",
                markup=True,
            )

        with Panel("📦  CLIENTS INSTALADOS", id="oc-installed-panel"):
            yield EmptyState(
                what="Clients instalados",
                why="O Oracle Instant Client permite conectar a bancos Oracle sem instalacao completa",
                action_label="Escolher client",
                action_id="escolher-client",
                id="oc-installed-empty",
            )
            yield DataTable(id="oc-installed-table", cursor_type="row")
            with Horizontal(classes="oc-actions"):
                yield Button("Usar este client", variant="primary", id="oc-use-btn")
                yield Button("Remover selecionado", variant="error", id="oc-remove-btn")
                yield Button("Atualizar lista", variant="default", id="oc-refresh-btn")

        with Panel("⬇️  DISPONIVEIS PARA DOWNLOAD", id="oc-available-panel"):
            yield DataTable(id="oc-available-table", cursor_type="row")
            with Horizontal(classes="oc-actions"):
                yield Button("Instalar selecionado", variant="primary", id="oc-install-btn")

        yield Static("", id="oc-status", markup=True)
        with Horizontal(id="oc-progress-row"):
            yield ProgressBar(id="oc-progress-bar", show_eta=False)

    def on_mount(self) -> None:
        installed = self.query_one("#oc-installed-table", DataTable)
        installed.add_columns("Diretorio", "Versao")

        available = self.query_one("#oc-available-table", DataTable)
        available.add_columns("Versao", "Arquitetura", "Formato")

        self._refresh_installed()
        self._refresh_available()
        self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        """Starts on the FIRST interactive panel, and not on the last.

        The screen is taller than 24 lines and scrolls, and Textual scrolls
        to whatever receives focus. Focusing the DISPONIVEIS table — the
        third panel — made the manager open already scrolled down to it: the
        first thing after choosing the list entry was a table with no header
        and no title above it. Focusing here, the screen opens on a panel
        WITH a title, and whoever wants to install reaches DISPONIVEIS by
        Tab (or through the empty state's "Escolher client" button, which
        exists for that).

        We do not force a scroll to the top after focusing: that puts the
        focus out of view, which is worse than starting one panel down. What
        pays for the top is the height of the platform panel, trimmed along
        with it.
        """
        try:
            if self._installed:
                self.query_one("#oc-installed-table", DataTable).focus()
            else:
                self.query_one("#oc-installed-empty", EmptyState).query_one(
                    Button
                ).focus()
        except Exception:
            pass

    def _refresh_installed(self) -> None:
        self._installed = oci.list_installed_clients()
        table = self.query_one("#oc-installed-table", DataTable)
        empty = self.query_one("#oc-installed-empty", EmptyState)
        table.clear()
        if not self._installed:
            empty.display = True
            table.display = False
            return
        empty.display = False
        table.display = True
        for c in self._installed:
            table.add_row(c.path.name, c.version or "[dim]?[/]")

    def _refresh_available(self) -> None:
        table = self.query_one("#oc-available-table", DataTable)
        table.clear()
        if not self._available:
            table.add_row(
                "[dim]Sem pacotes catalogados para esta plataforma.[/]", "", "",
            )
            return
        for pkg in self._available:
            table.add_row(pkg.version, pkg.arch_key, pkg.archive_type)

    def _set_status(self, text: str, level: str = "info") -> None:
        color = {"info": "$ds-text-muted", "ok": "$ds-text-muted", "err": "$ds-op-failure"}.get(
            level, "$ds-text-muted"
        )
        self.query_one("#oc-status", Static).update(f"[{color}]{text}[/]")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.query_one("#oc-progress-row").display = busy
        for bid in ("oc-install-btn", "oc-remove-btn", "oc-refresh-btn"):
            try:
                self.query_one(f"#{bid}", Button).disabled = busy
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "oc-refresh-btn":
            self._refresh_installed()
            self._set_status("Lista atualizada.")
        elif event.button.id == "oc-install-btn":
            self._start_install()
        elif event.button.id == "oc-remove-btn":
            self._start_remove()
        elif event.button.id == "oc-use-btn":
            self._use_selected()
        elif event.button.id == "escolher-client":
            # The label describes exactly what this button does: it takes
            # the focus to the list of available packages. Actually
            # installing requires a row selected there (_start_install), so
            # promising "Instalar client" here would promise more than a
            # single Enter delivers.
            self.query_one("#oc-available-table", DataTable).focus()

    def _use_selected(self) -> None:
        """Pin the selected install in dbqm settings so it wins over ORACLE_HOME."""
        from dbqm.core.db_manager import validate_oracle_client_dir
        from dbqm.models.settings import load_settings, save_settings

        selected = self._selected_installed()
        if selected is None:
            self._set_status("Selecione um client instalado.", "err")
            return
        problem = validate_oracle_client_dir(str(selected.path))
        if problem:
            self._set_status(problem, "err")
            return
        settings = load_settings()
        settings.oracle_client_dir = str(selected.path)
        save_settings(settings)
        self._set_status(
            f"Client definido: {selected.path.name}. "
            "Reabra o dbqm para que a mudanca tenha efeito.",
            "ok",
        )

    def _selected_available(self) -> oci.ClientPackage | None:
        if not self._available:
            return None
        table = self.query_one("#oc-available-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._available):
            return None
        return self._available[row]

    def _selected_installed(self) -> oci.InstalledClient | None:
        if not self._installed:
            return None
        table = self.query_one("#oc-installed-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._installed):
            return None
        return self._installed[row]

    def _start_install(self) -> None:
        if self._busy:
            return
        pkg = self._selected_available()
        if pkg is None:
            self.notify("Selecione um pacote disponivel.", severity="warning")
            return
        dest = CLIENTS_DIR / pkg.install_dirname
        if dest.exists() and any(dest.iterdir()):
            self.notify(
                f"Ja existe instalacao em {dest.name}. Remova antes de reinstalar.",
                severity="warning",
                timeout=6,
            )
            return
        self._set_busy(True)
        self._set_status(f"Baixando {pkg.display_label}...")
        try:
            bar = self.query_one("#oc-progress-bar", ProgressBar)
            bar.update(total=100, progress=0)
        except Exception:
            pass
        self._run_install(pkg)

    @work(thread=True, exclusive=True)
    def _run_install(self, pkg: oci.ClientPackage) -> None:
        def progress(done: int, total: int | None) -> None:
            self.app.call_from_thread(self._on_progress, done, total)
        try:
            path = oci.install_client(pkg, progress=progress)
            self.app.call_from_thread(self._on_install_done, pkg, path)
        except Exception as e:
            self.app.call_from_thread(self._on_install_error, pkg, str(e))

    def _on_progress(self, done: int, total: int | None) -> None:
        try:
            bar = self.query_one("#oc-progress-bar", ProgressBar)
            if total:
                bar.update(total=total, progress=done)
                pct = (done * 100) // total
                self._set_status(f"Baixando... {pct}% ({done // (1024 * 1024)} MB)")
            else:
                self._set_status(f"Baixando... {done // (1024 * 1024)} MB")
        except Exception:
            pass

    def _on_install_done(self, pkg: oci.ClientPackage, path: Path) -> None:
        self._set_busy(False)
        self._set_status(f"Instalado: {path}", level="ok")
        self.notify(f"Oracle Instant Client {pkg.version} instalado.")
        self._refresh_installed()

    def _on_install_error(self, pkg: oci.ClientPackage, msg: str) -> None:
        self._set_busy(False)
        self._set_status(f"Falha ao instalar {pkg.version}: {msg}", level="err")
        self.notify(f"Erro: {msg}", severity="error", timeout=8)

    def _start_remove(self) -> None:
        if self._busy:
            return
        item = self._selected_installed()
        if item is None:
            self.notify("Selecione um client instalado.", severity="warning")
            return

        def _decide(yes: bool | None) -> None:
            if not yes:
                return
            try:
                oci.remove_client(item.path)
                self._set_status(f"Removido: {item.path.name}", level="ok")
                self.notify("Client removido.")
                self._refresh_installed()
            except Exception as e:
                self.notify(f"Erro ao remover: {e}", severity="error")

        self.app.push_screen(
            ConfirmModal(
                f"Remover {item.path.name}?",
                title="Remover client",
            ),
            _decide,
        )
