"""Main Textual application for DB Query Manager."""
from __future__ import annotations

import traceback

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Header, TabbedContent, TabPane

from dbqm.ui.theme import GITHUB_DARK, GITHUB_LIGHT
from dbqm.ui.widgets.status_bar import StatusBar
from dbqm.ui.widgets.action_bar import ActionBar, ActionSelected
from dbqm.ui.widgets.templates_sidebar import TemplatesSidebar


class DBQMApp(App):
    """DB Query Manager — single tabbed dashboard shell."""

    #: Maps each tab id to the id of the screen widget it hosts.
    TAB_TO_SCREEN: dict[str, str] = {
        "tab-coleta": "adhoc-screen",
        "tab-conexoes": "connections-screen",
        "tab-objetos": "browser-screen",
        "tab-multiexec": "group-exec-screen",
        "tab-historico": "history-screen",
        "tab-config": "settings-screen",
        "tab-consultas": "query-exec-screen",
        "tab-ferramentas": "ferramentas-screen",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from dbqm._version import __version__
        self.title = f"DB Query Manager v{__version__}"

    BINDINGS = [
        Binding("f1", "switch_tab('tab-coleta')", "Coleta", show=False),
        Binding("f2", "switch_tab('tab-conexoes')", "Conexoes", show=False),
        Binding("f3", "switch_tab('tab-objetos')", "Objetos", show=False),
        Binding("f4", "switch_tab('tab-multiexec')", "Multi-Exec", show=False),
        Binding("f5", "switch_tab('tab-historico')", "Historico", show=False),
        Binding("f6", "switch_tab('tab-config')", "Configuracoes", show=False),
        Binding("f7", "switch_tab('tab-consultas')", "Consultas", show=False),
        Binding("f8", "switch_tab('tab-ferramentas')", "Ferramentas", show=False),
        Binding("ctrl+b", "toggle_sidebar", "Templates"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("escape", "go_back", "Back"),
        Binding("question_mark", "show_help", "Ajuda", show=False),
        Binding("slash", "search", "Buscar", show=False),
        # Action bar shortcut keys — bound at app level to guarantee they work
        # regardless of which widget has focus. The action_shortcut handler
        # checks if the key matches a current action bar entry.
        Binding("n", "shortcut('n')", "", show=False, priority=True),
        Binding("t", "shortcut('t')", "", show=False, priority=True),
        Binding("e", "shortcut('e')", "", show=False, priority=True),
        Binding("r", "shortcut('r')", "", show=False, priority=True),
        Binding("d", "shortcut('d')", "", show=False, priority=True),
        Binding("v", "shortcut('v')", "", show=False, priority=True),
        Binding("f", "shortcut('f')", "", show=False, priority=True),
        Binding("s", "shortcut('s')", "", show=False, priority=True),
        Binding("h", "shortcut('h')", "", show=False, priority=True),
        Binding("i", "shortcut('i')", "", show=False, priority=True),
        Binding("m", "shortcut('m')", "", show=False, priority=True),
        Binding("p", "shortcut('p')", "", show=False, priority=True),
        Binding("c", "shortcut('c')", "", show=False, priority=True),
        Binding("b", "shortcut('b')", "", show=False, priority=True),
        Binding("x", "shortcut('x')", "", show=False, priority=True),
        Binding("q", "shortcut('q')", "", show=False, priority=True),
    ]

    def compose(self) -> ComposeResult:
        # First-run (no connections) opens on the Conexoes tab. Decided here so
        # TabbedContent starts on the right tab with no deferred switch that
        # could race with early user input.
        from dbqm.models.connection import load_connections
        try:
            initial_tab = "tab-coleta" if load_connections() else "tab-conexoes"
        except Exception:
            initial_tab = "tab-coleta"

        yield Header()
        with Horizontal(id="body"):
            yield TemplatesSidebar(id="templates-sidebar")
            with TabbedContent(id="main-tabs", initial=initial_tab):
                with TabPane("🔍  Coleta", id="tab-coleta"):
                    from dbqm.ui.screens.adhoc import AdhocScreen
                    yield AdhocScreen(id="adhoc-screen")
                with TabPane("🔌  Conexoes", id="tab-conexoes"):
                    from dbqm.ui.screens.connections import ConnectionsScreen
                    yield ConnectionsScreen(id="connections-screen")
                with TabPane("📂  Objetos", id="tab-objetos"):
                    from dbqm.ui.screens.browser import BrowserScreen
                    yield BrowserScreen(id="browser-screen")
                with TabPane("📊  Multi-Exec", id="tab-multiexec"):
                    from dbqm.ui.screens.group_exec import GroupExecScreen
                    yield GroupExecScreen(id="group-exec-screen")
                with TabPane("📜  Historico", id="tab-historico"):
                    from dbqm.ui.screens.history import HistoryScreen
                    yield HistoryScreen(id="history-screen")
                with TabPane("⚙️  Configuracoes", id="tab-config"):
                    from dbqm.ui.screens.settings import SettingsScreen
                    yield SettingsScreen(id="settings-screen")
                with TabPane("📝  Consultas", id="tab-consultas"):
                    from dbqm.ui.screens.query_exec import QueryExecScreen
                    yield QueryExecScreen(id="query-exec-screen")
                with TabPane("🧰  Ferramentas", id="tab-ferramentas"):
                    from dbqm.ui.screens.ferramentas import FerramentasScreen
                    yield FerramentasScreen(id="ferramentas-screen")
        yield ActionBar()
        yield StatusBar()

    def on_mount(self) -> None:
        """Load settings, register themes, and set initial state."""
        from dbqm.models.settings import load_settings
        from dbqm.models.connection import load_connections
        from dbqm.models.query import load_queries
        from dbqm.models.group import load_groups

        settings = load_settings()

        self.register_theme(GITHUB_DARK)
        self.register_theme(GITHUB_LIGHT)
        self.theme = settings.theme

        connections = load_connections()
        queries = load_queries()
        groups = load_groups()

        status_bar = self.query_one(StatusBar)
        status_bar.update_counts(
            queries=len(queries),
            connections=len(connections),
            groups=len(groups),
        )

        # Disable every pane except the initially-active one. The hosted
        # phase-based screens focus a widget on mount, and focusing a widget
        # inside an inactive pane would otherwise activate that pane. Disabling
        # the inactive panes makes their descendants non-focusable, so only the
        # active screen can take focus and the intended tab always wins.
        try:
            self._sync_panes(self.query_one("#main-tabs", TabbedContent).active)
        except Exception:
            pass

        # First-run: no connections configured. The Conexoes tab is already
        # active (chosen in compose); just welcome the user.
        if not connections:
            self.notify(
                "Bem-vindo! Nenhuma conexao configurada. "
                "Crie uma conexao para comecar.",
                severity="warning",
                timeout=10,
            )

    def _sync_panes(self, active_id: str) -> None:
        """Enable the active pane and disable the rest.

        Disabled panes hold hidden, non-focusable content so their screens
        cannot steal focus (and thereby hijack the active tab).
        """
        try:
            tabbed = self.query_one("#main-tabs", TabbedContent)
            for pane in tabbed.query(TabPane):
                pane.disabled = (pane.id != active_id)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Tab navigation
    # ------------------------------------------------------------------

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch to the given tab.

        Blur focus first, then enable the target pane (and disable the rest)
        before activating it. Textual reactivates the tab that owns the
        currently focused descendant; clearing focus and disabling the other
        panes keeps a programmatic switch from being reverted. The
        tab-activated handler restores focus into the newly active pane.
        """
        try:
            self.set_focus(None)
            self._sync_panes(tab_id)
            self.query_one("#main-tabs", TabbedContent).active = tab_id
        except Exception:
            pass

    def _active_screen(self):
        """Return the screen widget hosted in the currently active tab."""
        try:
            tabbed = self.query_one("#main-tabs", TabbedContent)
            screen_id = self.TAB_TO_SCREEN.get(tabbed.active)
            if screen_id:
                return self.query_one(f"#{screen_id}")
        except Exception:
            pass
        return None

    def on_tabbed_content_tab_activated(self, event) -> None:
        """When a tab becomes active, normalize the action bar to that screen
        and focus its first focusable widget.

        Screens that expose an initial action-setter (``_set_actions`` or
        ``_set_list_actions``) get it re-invoked so their contextual actions
        are restored when switching back. Everything else clears the bar.
        This is best-effort and never hard-codes phase ids.
        """
        # Keep pane enabled-state in sync with whatever became active (covers
        # activation via a tab click, not just action_switch_tab).
        try:
            self._sync_panes(self.query_one("#main-tabs", TabbedContent).active)
        except Exception:
            pass

        screen = self._active_screen()
        if screen is None:
            try:
                self.query_one(ActionBar).set_actions([])
            except Exception:
                pass
            return

        setter = None
        for name in ("_set_actions", "_set_list_actions"):
            candidate = getattr(screen, name, None)
            if callable(candidate):
                setter = candidate
                break
        try:
            if setter is not None:
                setter()
            else:
                self.query_one(ActionBar).set_actions([])
        except Exception:
            try:
                self.query_one(ActionBar).set_actions([])
            except Exception:
                pass

        try:
            target = self.query_one("#main-tabs", TabbedContent).active
        except Exception:
            return
        self.call_after_refresh(lambda: self._focus_active_screen(target))

    def _focus_active_screen(self, tab_id: str) -> None:
        """Focus the first widget of ``tab_id``'s screen, but only if that tab
        is still the active one — prevents a stale scheduled focus from a
        previously active pane reverting a fresh tab switch.
        """
        try:
            tabbed = self.query_one("#main-tabs", TabbedContent)
            if tabbed.active != tab_id:
                return
            screen_id = self.TAB_TO_SCREEN.get(tab_id)
            if not screen_id:
                return
            screen = self.query_one(f"#{screen_id}")
        except Exception:
            return
        self._focus_screen_widget(screen)

    def action_toggle_sidebar(self) -> None:
        """Collapse or expand the Templates sidebar."""
        try:
            self.query_one(TemplatesSidebar).toggle()
        except Exception:
            pass

    def on_templates_sidebar_template_chosen(self, message) -> None:
        """Inject template SQL into the active tab's editor if it has one."""
        from textual.widgets import TextArea

        screen = self._active_screen()
        try:
            editor = screen.query(TextArea).first()
            editor.text = message.sql
        except Exception:
            self.notify("Aba atual nao aceita template.", severity="warning")

    # ------------------------------------------------------------------
    # Keyboard navigation
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        """Use arrow keys to navigate between widgets in the active tab.

        DataTable, ListView, TextArea, and OptionList handle arrows
        internally. For other widgets (Button, Switch, Input, Select),
        arrows move focus. Disabled when a modal is active so modals
        handle their own navigation.
        """
        if event.key not in ("up", "down"):
            return

        if len(self.screen_stack) > 1:
            return

        from textual.widgets import DataTable, ListView, TextArea, OptionList

        focused = self.focused
        if focused is None:
            return

        widget_chain = [focused] + list(focused.ancestors)
        for w in widget_chain:
            if isinstance(w, (DataTable, ListView, TextArea, OptionList)):
                return

        self._focus_within_section(forward=(event.key == "down"))
        event.prevent_default()
        event.stop()

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        """Disable bindings contextually based on focused widget."""
        if action == "shortcut":
            # Block shortcuts when a modal screen is active
            if len(self.screen_stack) > 1:
                return False
            from textual.widgets import Input, TextArea
            focused = self.focused
            if isinstance(focused, (Input, TextArea)):
                return False
            try:
                action_bar = self.query_one(ActionBar)
            except Exception:
                return False
            key = parameters[0] if parameters else ""
            for act in action_bar._actions:
                if act.key and act.key.lower() == key.lower():
                    return True
            return False

        return True

    def _focus_within_section(self, forward: bool) -> None:
        """Navigate focus within the widgets of the active tab pane only."""
        focused = self.focused
        if focused is None:
            return

        from textual.widgets import Select

        try:
            tabbed = self.query_one("#main-tabs", TabbedContent)
            pane = tabbed.get_pane(tabbed.active)
        except Exception:
            return
        if pane is None:
            return

        # Get all focusable widgets inside the active pane only.
        # Exclude pure layout containers that shouldn't receive focus.
        focusable = []
        for w in pane.query("*"):
            if not w.can_focus or not w.display:
                continue
            # Select inherits from Vertical, so include it explicitly first.
            if isinstance(w, Select):
                focusable.append(w)
            elif w.__class__.__name__ in (
                "Vertical", "Horizontal", "Container",
                "VerticalScroll", "HorizontalScroll",
                "NavVerticalScroll", "SettingsScreen",
                "TabPane", "ContentSwitcher",
            ):
                continue
            else:
                focusable.append(w)

        if not focusable:
            return

        current_idx = -1
        for i, w in enumerate(focusable):
            if w is focused or w in focused.ancestors:
                current_idx = i
                break

        if current_idx < 0:
            focusable[0 if forward else -1].focus()
            return

        if forward:
            next_idx = min(current_idx + 1, len(focusable) - 1)
        else:
            next_idx = max(current_idx - 1, 0)

        focusable[next_idx].focus()

    # ------------------------------------------------------------------
    # Action bar routing
    # ------------------------------------------------------------------

    def action_shortcut(self, key: str) -> None:
        """Handle action bar shortcut keys (N, T, E, R, etc.)."""
        try:
            action_bar = self.query_one(ActionBar)
        except Exception:
            return

        for action in action_bar._actions:
            if action.key and action.key.lower() == key.lower():
                # Post to the active tab's screen so it receives the message.
                screen = self._active_screen()
                if screen is not None:
                    screen.post_message(ActionSelected(action.action_id))
                else:
                    action_bar.post_message(ActionSelected(action.action_id))
                return

    def on_action_selected(self, message: ActionSelected) -> None:
        """Forward ActionSelected from action bar clicks to the active screen.

        This is only needed for CLICK-based actions on the ActionBar markup.
        Shortcut-based actions already post directly to the screen widget.
        """
        # Only forward if this came from the ActionBar (bubbled up),
        # not from a screen (would cause infinite loop).
        if isinstance(message._sender, ActionBar):
            screen = self._active_screen()
            if screen is not None:
                screen.post_message(ActionSelected(message.action_id))
            message.stop()

    def _focus_screen_widget(self, screen_widget) -> None:
        """Set focus to the first interactive widget within a screen."""
        try:
            for widget in screen_widget.query("*"):
                if widget.can_focus and widget.display:
                    widget.focus()
                    return
            screen_widget.focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Back navigation
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        """Go back within the active tab's screen, if it has a deeper phase.

        Compact dispatch keyed on the active screen id — each screen that
        supports drill-down exposes a matching ``go_back_*`` method. Guarded
        end to end; a no-op when nothing applies.
        """
        try:
            tabbed = self.query_one("#main-tabs", TabbedContent)
            screen_id = self.TAB_TO_SCREEN.get(tabbed.active)
            if not screen_id:
                return
            screen = self.query_one(f"#{screen_id}")
        except Exception:
            return

        try:
            if screen_id == "adhoc-screen":
                if screen.query_one("#adhoc-results-phase").display:
                    screen.go_back_to_input()
                    self.query_one(ActionBar).set_actions([])
            elif screen_id == "query-exec-screen":
                if screen.query_one("#results-phase").display:
                    screen.go_back_to_selection()
                    self.query_one(ActionBar).set_actions([])
            elif screen_id == "group-exec-screen":
                if screen.query_one("#ge-results-phase").display:
                    screen.go_back_to_selection()
                    self.query_one(ActionBar).set_actions([])
            elif screen_id == "browser-screen":
                if screen.query_one("#br-data-phase").display:
                    screen.go_back_to_detail()
                elif screen.query_one("#br-detail-phase").display:
                    screen.go_back_to_list()
                elif screen.query_one("#br-list-phase").display:
                    screen.go_back_to_select()
            elif screen_id == "history-screen":
                if screen.query_one("#hist-detail-phase").display:
                    screen.go_back_to_list()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Global handlers / overlays
    # ------------------------------------------------------------------

    def _handle_exception(self, error: Exception) -> None:
        """Global error handler — show error modal instead of crashing."""
        from dbqm.ui.modals.error import ErrorModal
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        detail = "".join(tb)
        # Escape Rich markup in the traceback
        detail = detail.replace("[", "\\[")
        title = f"Erro: {type(error).__name__}"
        try:
            self.push_screen(ErrorModal(title, detail))
        except Exception:
            # Last resort: use notification
            self.notify(f"{title}: {error}", severity="error", timeout=10)
        return  # Don't re-raise — app stays alive

    def on_worker_state_changed(self, event) -> None:
        """Catch worker thread errors and show them in a modal."""
        from textual.worker import WorkerState
        if event.state == WorkerState.ERROR and event.worker.error:
            self._handle_exception(event.worker.error)

    def action_show_help(self) -> None:
        """Show the help overlay with keyboard shortcuts."""
        from dbqm.ui.modals.help import HelpModal
        self.push_screen(HelpModal())

    def action_search(self) -> None:
        """Trigger search/filter on the active QueryListWidget if present."""
        from dbqm.ui.widgets.query_list import QueryListWidget
        try:
            ql = self.query_one(QueryListWidget)
            ql.action_start_search()
        except Exception:
            pass
