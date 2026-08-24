"""Settings screen — one panel per subject (layout grammar, section 4).

Before this task the screen had ONE panel called "CONFIG DA APLICACAO" with
four subjects inside it (theme, auditing, export and Oracle Instant Client),
separated only by a bold label, and three buttons that pretended to be a menu.
The maintainer's complaint was literal: "a tela de configuracoes esta horrivel
com um monte de botao alinhado no centro e dentro da tela de configuracoes do
sistema, esta tudo muito confuso".

Now each subject has its own frame, and the navigation to the two deeper
screens (portability and the clients manager) is a LIST, not a button —
section 7 of the grammar: a button is an action, never navigation. The buttons
that remain open a dialog about the subject of the panel they live in.
"""
from __future__ import annotations

import re
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, ContentSwitcher, OptionList, Select, Static, Switch

from dbqm.ui.theme import get_theme
from dbqm.ui.utils import NavSelect, NavVerticalScroll
from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.hierarchical_list import NamedOption, hierarchical_item
from dbqm.ui.widgets.panel import Panel

#: One character, and not "...": the path label has 30 cells in a
#: terminal of 80, and each column spent on the marker is one column
#: less of path.
RETICENCIA = "\u2026"

#: Path separators of both families, captured so that the cut can
#: reassemble the original text byte by byte (a Windows path may mix the
#: two: `C:\\Users\\ricar/exports`).
_SEPARATOR = re.compile(r"([\\/])")


def elide_path(path: str, width: int) -> str:
    """Shortens *path* so it fits in *width* columns by cutting the MIDDLE.

    The start and the end of a path are what identify it — the root says
    which tree it comes from, the last segment says which directory or file
    it is about. The middle is the disposable part. The alternative Textual
    gives for free (letting the text wrap on its own) does the opposite of
    what is needed: it breaks in the middle of a NAME and, when the panel
    runs out, it is precisely the end of the path that disappears. The screen
    was painting
    `C:\\Users\\ricar\\AppData\\Local\\Tem` / `p\\pytest-of-ricar\\pytest-626\\tes`
    and nothing after that.

    The cut prefers to fall between segments: half of a directory name
    identifies nothing, and still looks like a real name. Only when there is
    no usable separator is the cut made by character — which is still better
    than cutting only the end.

    The result never exceeds *width*, including at the absurd widths: that is
    where the test that sweeps width by width comes from.
    """
    texto = str(path)
    if width <= 0:
        return ""
    if len(texto) <= width:
        return texto
    if width <= len(RETICENCIA):
        return RETICENCIA[:width]

    # `split` with a capturing group interleaves segments and separators:
    # ['C:', '/', 'Users', '/', ...]. Even index = segment, odd = separator.
    pecas = _SEPARATOR.split(texto)

    # The head goes up to the first NAMED segment. In an ordinary path that
    # is `pecas[:3]` (`C:` + `\` + `Users`). In a UNC it is not:
    # `\\servidor\share` splits into ['', '\\', '', '\\', 'servidor', ...] —
    # the first two segments are empty — and stopping at the third would
    # give a head of a single slash. Two folders on two different servers
    # would elide IDENTICALLY, and in a UNC the server is precisely the root
    # this function promises to preserve ("which tree the path comes from").
    corte = 2
    while corte + 2 < len(pecas) and not pecas[corte]:
        corte += 2

    if len(pecas) >= corte + 3:  # head + separator + at least one segment
        cabeca = "".join(pecas[: corte + 1])
        if len(cabeca) + len(RETICENCIA) < width:
            cauda = ""
            i = len(pecas) - 1
            while i >= corte + 1:
                candidata = "".join(pecas[i:])
                if len(cabeca) + len(RETICENCIA) + len(candidata) > width:
                    break
                cauda = candidata
                i -= 2
            if cauda:
                return cabeca + RETICENCIA + cauda

    sobra = width - len(RETICENCIA)
    frente = (sobra + 1) // 2
    fim = sobra - frente
    return texto[:frente] + RETICENCIA + (texto[len(texto) - fim:] if fim else "")


class PathLabel(Static):
    """`Static` that asks for a repaint when its OWN width changes.

    The SCREEN's `on_resize` does not cover this case: what changes size
    here is the label, not the screen. At mount time the column does not
    yet know it will need a scrollbar, and the label measures 33 cells
    where it will have 32 — elided against 33 the path went over by ONE
    cell and the automatic wrap threw the last character alone onto the
    line below, which is the very defect `elide_path` exists to avoid,
    arriving through another door. `events.Resize` does not bubble
    (`bubble=False` in `textual/events.py`), so nobody above would find out.

    Only the WIDTH counts. Repainting changes the label's height, which
    generates another `Resize`; without this comparison the repaint-event
    pair would feed itself.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._largura_vista = -1

    def on_resize(self, event) -> None:
        # `event.size` is the NEW width; `content_region` only becomes the
        # new one after the next layout — that is why the repaint is
        # deferred, and not done in here.
        if event.size.width == self._largura_vista:
            return
        self._largura_vista = event.size.width
        for ancestral in self.ancestors:
            if isinstance(ancestral, SettingsScreen):
                ancestral.call_after_refresh(ancestral._paint_paths)
                return


class SettingsScreen(Vertical):
    """Settings screen: one panel per subject, in two columns.

    It also hosts the two deeper screens of the settings area
    (`ConfigPortScreen` and `OracleClientsScreen`) in a `ContentSwitcher` —
    the same mechanism `ToolsScreen` already uses to host whole screens
    inside a tab. See `_open_tool`.
    """

    DEFAULT_CSS = """
    SettingsScreen {
        height: 1fr;
    }
    SettingsScreen ContentSwitcher {
        height: 1fr;
    }
    SettingsScreen #settings-main {
        height: 1fr;
    }
    /* Sem padding VERTICAL: as duas linhas que ele custava (uma no topo,
       uma no rodape) sao 10% da viewport num terminal de 24, e sem elas o
       painel MAIS CONFIGURACOES — a unica porta para as duas telas que
       esta fase ressuscitou — passa de "titulo com zero entradas" para as
       duas entradas desenhadas. Medido a 80x24 na DBQMApp real, em
       `test_settings_at_80x24_does_not_hide_the_door`. */
    SettingsScreen .settings-column {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }
    /* `auto` mede o conteudo desde a Task 6; a coluna e que rola quando a
       soma dos paineis passa da tela. Sem isto cada painel esticaria ate a
       altura da COLUNA e so o primeiro de cada uma apareceria. */
    SettingsScreen .settings-column > Panel {
        height: auto;
        margin-bottom: 1;
    }
    SettingsScreen .settings-host {
        height: 1fr;
    }
    SettingsScreen #settings-theme-select {
        width: 1fr;
    }
    SettingsScreen .settings-row {
        height: auto;
    }
    SettingsScreen .settings-note {
        height: auto;
        color: $ds-text-muted;
    }
    SettingsScreen .settings-actions {
        height: auto;
    }
    SettingsScreen .settings-actions Button {
        margin: 0 1 0 0;
    }
    SettingsScreen #settings-ferramentas-list {
        height: auto;
    }
    """

    ORACLE_CLIENT_ORIGINS = {
        "config": "configuracao do dbqm",
        "clients": "clients instalados pelo dbqm",
        "package": "pasta clients/ do pacote",
        "ORACLE_HOME": "variavel de ambiente ORACLE_HOME",
        "scan": "deteccao automatica no sistema",
    }

    #: The hosted screens: (key, identity, disambiguation). The key travels
    #: as DATA in the option (`NamedOption.nome`), never as `id` — the
    #: reason is in `NamedOption`'s docstring.
    #:
    #: The text is SHORT out of a layout requirement, not out of taste: the
    #: list column has 30 cells in a terminal of 80, and a line wider than
    #: that wraps on its own at render — the continuation goes back to
    #: column 0, the same one as the identity of the next entry, which is
    #: exactly the confusion this phase exists to undo. `hierarchical_item`
    #: has no way to indent the automatic wrap (it is written in its own
    #: docstring). `test_more_settings_list_does_not_wrap_at_80_columns`
    #: enforces it.
    TOOLS = (
        (
            "oracle-clients",
            "Oracle Instant Clients",
            "instalar, remover, escolher",
        ),
        (
            "portabilidade",
            "Exportar / Importar",
            "bundle .dbqm com senha",
        ),
    )

    #: Key -> id of the container where that screen is mounted.
    _HOSTS = {
        "oracle-clients": "settings-host-oracle-clients",
        "portabilidade": "settings-host-portabilidade",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dir_exportacao = ""
        #: key -> the hosted screen already mounted (see `_open_tool`).
        self._montadas: dict[str, Vertical] = {}
        self._client_oracle: tuple[str | None, str] = (None, "none")
        self._client_oracle_erro = ""

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="settings-main"):
            with Horizontal(id="settings-main"):
                with NavVerticalScroll(
                    id="settings-col-esquerda", classes="settings-column"
                ):
                    with Panel("🎨  TEMA", id="settings-panel-tema", dense=True):
                        yield NavSelect(
                            [
                                ("Plano Escuro", "plano-escuro"),
                                ("Plano Claro", "plano-claro"),
                            ],
                            id="settings-theme-select",
                            allow_blank=False,
                        )

                    with Panel("📋  AUDITORIA", id="settings-panel-auditoria", dense=True):
                        with Vertical(classes="settings-row"):
                            yield Switch(id="settings-audit-switch")
                            yield Static(
                                "Registra execucoes de consultas e grupos.",
                                id="settings-audit-desc",
                                classes="settings-note",
                            )

                    with Panel(
                        "📁  EXPORTACAO",
                        id="settings-panel-exportacao",
                        dense=True,
                    ):
                        yield Static(
                            "Onde os arquivos exportados sao salvos.",
                            classes="settings-note",
                        )
                        yield PathLabel(
                            "", id="settings-export-dir-current", markup=True
                        )
                        with Horizontal(classes="settings-actions"):
                            yield Button(
                                "Alterar diretorio",
                                variant="primary",
                                id="btn-export-dir",
                            )
                        with Vertical(classes="settings-row"):
                            yield Switch(id="settings-export-subdirs-switch")
                            yield Static(
                                "Subdiretorios por tipo (grupos, DDL, SQL).",
                                classes="settings-note",
                            )

                with NavVerticalScroll(
                    id="settings-col-direita", classes="settings-column"
                ):
                    with Panel(
                        "🔌  ORACLE INSTANT CLIENT",
                        id="settings-panel-oracle",
                        dense=True,
                    ):
                        # Short on purpose: each line of prose here is one
                        # line less for the MAIS CONFIGURACOES list, which
                        # in a terminal of 24 sits right below this
                        # panel.
                        yield Static(
                            "Vence o ORACLE_HOME, que pode "
                            "ser de outra arquitetura.",
                            classes="settings-note",
                        )
                        yield PathLabel(
                            "", id="settings-oracle-client-current", markup=True
                        )
                        with Horizontal(classes="settings-actions"):
                            yield Button(
                                "Definir caminho",
                                variant="primary",
                                id="btn-oracle-client-dir",
                            )

                    # Right below the Oracle panel on purpose: the clients
                    # manager entry sits right against the status that makes
                    # someone want to open it.
                    with Panel(
                        "🧰  MAIS CONFIGURACOES",
                        id="settings-panel-ferramentas",
                        dense=True,
                    ):
                        yield OptionList(id="settings-ferramentas-list")

                    with Panel(
                        "🔑  FERNET KEY",
                        id="settings-panel-fernet",
                        dense=True,
                    ):
                        yield PathLabel("", id="settings-fernet-status", markup=True)

            yield Vertical(
                id="settings-host-portabilidade", classes="settings-host"
            )
            yield Vertical(
                id="settings-host-oracle-clients", classes="settings-host"
            )

    def on_mount(self) -> None:
        from dbqm.models.settings import load_settings

        settings = load_settings()

        theme_select = self.query_one("#settings-theme-select", Select)
        theme_select.value = get_theme(settings.theme).name

        audit_switch = self.query_one("#settings-audit-switch", Switch)
        audit_switch.value = settings.audit_log_enabled

        subdirs_switch = self.query_one("#settings-export-subdirs-switch", Switch)
        subdirs_switch.value = settings.create_export_subdirs

        lista = self.query_one("#settings-ferramentas-list", OptionList)
        lista.clear_options()
        for chave, identidade, desambiguacao in self.TOOLS:
            lista.add_option(
                NamedOption(hierarchical_item(identidade, desambiguacao), chave)
            )

        self._dir_exportacao = settings.default_export_dir
        self._refresh_oracle_client_status()
        self._paint_paths()

        self.call_after_refresh(self._set_initial_focus)

    def on_resize(self, event) -> None:
        """Repaints the paths: the usable width has changed.

        The two columns are `1fr`, so a label's width depends on the
        terminal — 30 cells at 80 columns, 52 at 120. Eliding against a
        constant would get one width right and all the others wrong.
        `call_after_refresh` because during the resize event itself the
        children's regions are still the old ones.
        """
        self.call_after_refresh(self._paint_paths)

    # ------------------------------------------------------------------
    # Long paths
    # ------------------------------------------------------------------

    def _paint_paths(self) -> None:
        """Repaints the three labels that carry a path.

        Repainting does not SWEEP the disk. It touches the disk once, and
        that is all: `_paint_fernet` calls `KEY_FILE.exists()` — a `stat` on
        a known path. It is the Instant Client detection
        (`resolve_oracle_client_dir`) that sweeps the system's common
        installation directories, and that is why it lives in
        `_refresh_oracle_client_status`, called when the answer may have
        changed, and not here, which runs on every terminal resize.
        """
        self._paint_export_dir()
        self._paint_oracle_client()
        self._paint_fernet()

    @staticmethod
    def _usable_width(label: Static) -> int:
        """How many columns the label has to paint into.

        Measured on the mounted widget: `content_region` already discounts
        the panel border, the body padding and the label's own. While the
        layout has not happened it measures 0 — and in that state nothing is
        elided, because eliding against zero would erase the whole path.
        `on_resize` repaints as soon as the region exists.
        """
        return label.content_region.width

    def _refresh_export_dir_label(self, configured: str) -> None:
        self._dir_exportacao = configured
        self._paint_export_dir()

    def _paint_export_dir(self) -> None:
        rotulo = self.query_one("#settings-export-dir-current", Static)
        largura = self._usable_width(rotulo)
        if self._dir_exportacao:
            caminho = self._dir_exportacao
            sufixo = ""
        else:
            caminho = str(Path.cwd())
            sufixo = "\n[$ds-text-disabled](diretorio de execucao)[/]"
        if largura:
            caminho = elide_path(caminho, largura)
        rotulo.update(f"[b]Diretorio atual:[/]\n{caminho}{sufixo}")

    def _refresh_oracle_client_status(self) -> None:
        """Rediscovers which Instant Client is in use, and where it came from.

        Does I/O (see `resolve_oracle_client_dir`): it is only called when
        the answer may have changed — at mount time and after the path modal
        saves. A path that is configured but unusable is reported as an
        ERROR, and not silently replaced: that silence is what made the
        ORACLE_HOME conflict so hard to diagnose.
        """
        from dbqm.core.db_manager import OracleClientConfigError, resolve_oracle_client_dir

        try:
            self._client_oracle = resolve_oracle_client_dir()
            self._client_oracle_erro = ""
        except OracleClientConfigError as e:
            self._client_oracle = (None, "none")
            self._client_oracle_erro = str(e)
        self._paint_oracle_client()

    def _paint_oracle_client(self) -> None:
        label = self.query_one("#settings-oracle-client-current", Static)
        if self._client_oracle_erro:
            label.update(f"[b]Client em uso:[/] [$ds-op-failure]{self._client_oracle_erro}[/]")
            return
        path, origin = self._client_oracle
        if not path:
            label.update(
                "[b]Client em uso:[/] [$ds-text-muted]nenhum encontrado[/] "
                "[$ds-text-disabled](thick mode indisponivel)[/]"
            )
            return
        source = self.ORACLE_CLIENT_ORIGINS.get(origin, origin)
        largura = self._usable_width(label)
        mostrado = elide_path(str(path), largura) if largura else str(path)
        label.update(f"[b]Client em uso:[/]\n{mostrado}\n[b]Origem:[/] {source}")

    #: Of the three labels with a path, this is the only one that puts the
    #: path on the SAME line as its label — the other two break the line
    #: first. The prefix cells are not available for the path, and charging
    #: the whole width made the line run past the box and burn a line on the
    #: automatic wrap (37 cells against 32 of box, measured at 80x24).
    FERNET_PREFIX = "Local: "

    def _paint_fernet(self) -> None:
        from dbqm.core.paths import KEY_FILE

        status = self.query_one("#settings-fernet-status", Static)
        exists = KEY_FILE.exists()
        state = "Presente" if exists else "[$ds-text-muted]Sera gerada no primeiro uso[/]"
        orcamento = self._usable_width(status) - len(self.FERNET_PREFIX)
        local = str(KEY_FILE)
        if orcamento > 0:
            local = elide_path(local, orcamento)
        status.update(
            f"[b]Status:[/b] {state}\n"
            f"[b]{self.FERNET_PREFIX}[/b][$ds-text-disabled]{local}[/]\n\n"
            "[$ds-text-disabled]Criptografa as senhas de conexao salvas. "
            "Nao ha acao manual: ela e criada automaticamente.[/]"
        )

    def _set_initial_focus(self) -> None:
        try:
            self.query_one("#settings-theme-select", Select).focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Hosted screens
    # ------------------------------------------------------------------

    def _build_tool(self, key: str):
        if key == "oracle-clients":
            from dbqm.ui.screens.oracle_clients import OracleClientsScreen

            return OracleClientsScreen(id="settings-oracle-clients-screen")
        if key == "portabilidade":
            from dbqm.ui.screens.config_port import ConfigPortScreen

            return ConfigPortScreen(id="settings-config-port-screen")
        raise ValueError(f"ferramenta de configuracao desconhecida: {key}")

    def _open_tool(self, key: str) -> None:
        """Swaps the settings area for the *key* screen, mounting it the 1st time.

        These two screens were UNREACHABLE from v1.17.0 until here: the
        buttons that opened them queried `#screen-area`, removed in
        e02b8a8 when the app became a single tabbed shell, and the
        `except Exception` turned the failure into an error toast. They
        come back through the mechanism the shell already has for hosting a
        whole screen inside a tab — the same `ContentSwitcher` as
        `ToolsScreen` — instead of a `push_screen`, which would take the
        header, the tabs and the action bar out of sight.
        """
        hospede = self.query_one(f"#{self._HOSTS[key]}", Vertical)
        if key not in self._montadas:
            tela = self._build_tool(key)
            hospede.mount(tela)
            self._montadas[key] = tela
        else:
            # Reopening a screen that is still mounted showed the phase it
            # WAS LEFT in: whoever exported, left with `Esc` and came back
            # would meet the export form again, while the list entry
            # promised "Exportar / Importar". The one that knows whether
            # there is state that must survive the round trip is the screen
            # itself — the clients manager does not implement this precisely
            # because it has a 150+ MB download writing into its tree.
            reabrir = getattr(self._montadas[key], "on_reopen", None)
            if callable(reabrir):
                reabrir()
        self.query_one(ContentSwitcher).current = self._HOSTS[key]
        self._set_actions()

    def back_to_start(self) -> None:
        """Goes back from the hosted screen to the panels; a no-op if already there.

        It no longer returns an "the `Esc` was consumed here": the two
        callers (`DBQMApp.action_go_back` and the action bar's `Voltar`,
        which arrives via `on_action_selected`) discarded the bool, and
        neither of them has a second `Esc` route to try in case this one
        does not take. There were three until
        `ConfigPortScreen._go_back_to_settings` was removed in the task that
        resurrected the dead routes; a third caller that is cited and does
        not exist sends the next person looking for code that is not there.
        Documenting a value as load-bearing when nobody carries anything
        with it is the same class of silent lie the rest of this phase
        has been undoing.

        The hosted screen stays MOUNTED, only hidden — as `ToolsScreen`
        already does with its five. Unmounting would be ripping the widget
        out from under a live worker: installing an Instant Client
        downloads 150+ MB in the background and writes progress into this
        tree. Going back cannot mean cancelling.
        """
        switcher = self.query_one(ContentSwitcher)
        if switcher.current == "settings-main":
            return
        switcher.current = "settings-main"
        self._set_actions()
        self.call_after_refresh(self._reenter_panels)

    def _reenter_panels(self) -> None:
        """Shows the panels again: resyncs and gives focus back to the list.

        After the refresh, and not during the `Esc`: the path elision
        measures the width on the mounted label, and while the
        `ContentSwitcher` has not redone the layout that width is still the
        one of whatever was hidden.
        """
        self._resync_with_disk()
        self._focus_tool_list()

    def _resync_with_disk(self) -> None:
        """Reconciles the panels with what the hosted screens wrote.

        `OracleClientsScreen._use_selected` writes `oracle_client_dir` and
        saves — and the `Client em uso` label kept showing the PREVIOUS
        client. It is not just any staleness: the route to the manager was
        drawn around that label (the list entry sits against it on
        purpose), so it went stale exactly at the moment the person acted
        on it — the screen contradicting the setting they had just written.

        It repaints BOTH labels that come out of `settings.json`, and not
        only the Oracle one: the cost is one file read on a key press, and
        the alternative is depending on somebody remembering to add a line
        here the next time a hosted screen writes a setting.
        """
        from dbqm.models.settings import load_settings

        try:
            self._dir_exportacao = load_settings().default_export_dir
        except Exception:
            pass
        self._paint_export_dir()
        self._refresh_oracle_client_status()

    def _focus_tool_list(self) -> None:
        try:
            self.query_one("#settings-ferramentas-list", OptionList).focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Action bar
    # ------------------------------------------------------------------

    def _set_actions(self) -> None:
        """Announces the `Esc` while a hosted screen is in front.

        `DBQMApp.compose` does not render a `Footer`, so the app's
        `Binding("escape", "go_back", "Back")` is never DRAWN: the only
        exit from `OracleClientsScreen` — which has no back button — was a
        key that nothing on screen mentioned. Section 7 of the grammar
        forbids a BUTTON that navigates; it does not forbid saying which
        key goes back, and that is what the action bar does for the rest of
        the app.

        The method name is not decoration: `DBQMApp.on_tabbed_content_tab_
        activated` looks for `_set_actions`/`_set_list_actions` on the
        screen of the tab just activated. Without it, leaving the tab and
        coming back would erase the announcement with the hosted screen
        still in front.
        """
        try:
            barra = self.app.query_one(ActionBar)
        except Exception:
            return
        try:
            dentro = self.query_one(ContentSwitcher).current != "settings-main"
        except Exception:
            dentro = False
        barra.set_actions(
            [Action("Voltar", "Esc", "settings-voltar")] if dentro else []
        )

    def on_action_selected(self, message: ActionSelected) -> None:
        if message.action_id == "settings-voltar":
            self.back_to_start()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "settings-ferramentas-list":
            return
        event.stop()
        chave = getattr(event.option, "name", "")
        if chave in self._HOSTS:
            self._open_tool(chave)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "settings-theme-select":
            return
        if event.value is None or event.value is Select.BLANK:
            return

        from dbqm.models.settings import load_settings, save_settings

        settings = load_settings()
        new_theme = str(event.value)
        # Compare with the NORMALIZED theme, not with the raw text of the
        # file. `on_mount` fills the Select with
        # `get_theme(settings.theme).name`, and `Select._on_mount` itself
        # re-emits `Changed` afterwards — out of reach of any `prevent` put
        # here (measured). On the first opening after upgrading from 1.17.x
        # the file still says `github-dark` and the Select says
        # `plano-escuro`: with the raw comparison this passed for a theme
        # change, wrote it and announced "Tema alterado: plano-escuro" to
        # someone who changed no theme at all. They are the same theme —
        # `github-dark` was only renamed.
        if new_theme == get_theme(settings.theme).name:
            return
        settings.theme = new_theme
        save_settings(settings)
        try:
            self.app.theme = settings.theme
        except Exception:
            pass
        self.notify(f"Tema alterado: {settings.theme}")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        from dbqm.models.settings import load_settings, save_settings

        # `Switch.Changed` does not prove that anyone touched the switch:
        # `on_mount` itself assigns `Switch.value` to SHOW what is already
        # saved, and every time the saved value differs from the `Switch`'s
        # factory `False` the assignment emits `Changed`. It happened on
        # every opening of the app, with nobody touching anything:
        # `create_export_subdirs` is born `True` (a notice on any config),
        # and `audit_log_enabled` is born `False` but turns `True` as soon
        # as the person switches auditing on (a notice from then on). Each
        # one became a notice AND a rewrite of `settings.json` — measured: 1
        # write with a fresh config, 2 with auditing on.
        #
        # The guard is by EQUALITY, not by mount instant: if the value that
        # arrived is already the one recorded, nothing happened — that holds
        # both for the mount echo and for any other re-emitter, and does not
        # depend on getting right when the mount storm settles.
        if event.switch.id == "settings-audit-switch":
            settings = load_settings()
            if settings.audit_log_enabled == event.value:
                return
            settings.audit_log_enabled = event.value
            save_settings(settings)
            status = "ativado" if event.value else "desativado"
            self.notify(f"Log de auditoria {status}!")
        elif event.switch.id == "settings-export-subdirs-switch":
            settings = load_settings()
            if settings.create_export_subdirs == event.value:
                return
            settings.create_export_subdirs = event.value
            save_settings(settings)
            status = "ativado" if event.value else "desativado"
            self.notify(f"Subdiretorios por tipo: {status}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-oracle-client-dir":
            self._open_oracle_client_dir_modal()
        elif event.button.id == "btn-export-dir":
            self._open_export_dir_modal()

    def _open_export_dir_modal(self) -> None:
        """Open the export dir setup modal in edit mode."""
        from dbqm.models.settings import load_settings
        from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal

        settings = load_settings()
        modal = ExportDirSetupModal(
            initial_use_cwd=not settings.default_export_dir,
            initial_path=settings.default_export_dir,
        )
        self.app.push_screen(modal, callback=self._on_export_dir_saved)

    def _on_export_dir_saved(self, saved: bool | None) -> None:
        if not saved:
            return
        from dbqm.models.settings import load_settings

        settings = load_settings()
        self._refresh_export_dir_label(settings.default_export_dir)
        self.notify("Diretorio de exportacao atualizado!")

    def _open_oracle_client_dir_modal(self) -> None:
        """Open the Instant Client directory modal seeded with the current setting."""
        from dbqm.models.settings import load_settings
        from dbqm.ui.modals.oracle_client_dir import OracleClientDirModal

        modal = OracleClientDirModal(initial_path=load_settings().oracle_client_dir)
        self.app.push_screen(modal, callback=self._on_oracle_client_dir_saved)

    def _on_oracle_client_dir_saved(self, saved: bool | None) -> None:
        if not saved:
            return
        self._refresh_oracle_client_status()
        self.notify("Oracle Instant Client atualizado! Reabra o dbqm para aplicar.")
