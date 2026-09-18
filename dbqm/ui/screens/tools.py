"""Ferramentas launcher screen — the list that leads to the five tool screens.

Up to Task 8 of this phase the menu was five full-width buttons, one per
tool, plus a "Voltar" inside each hosted pane. Both patterns break the same
rule from section 7 of the grammar: **a button is an action, never
navigation**. Five stacked buttons that only switch screens are five buttons
pretending to be a menu.

The cost was measured too, not aesthetic: at 80x24 in the real DBQMApp each
button took 4 lines (3 of button + 1 of margin), 20 lines in a body of
14 — `Executar Rotina` and `Executar Grupo` were born below the fold. The
list spends 2 lines per entry and fits whole, with the disambiguation free.

Going back is the `Esc`, announced by the `ActionBar` — the same mechanism
the Configuracoes screen uses for the two screens it hosts (`settings.py`).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import ContentSwitcher, OptionList

from dbqm.i18n import t
from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.hierarchical_list import NamedOption, hierarchical_item
from dbqm.ui.widgets.panel import Panel


class ToolsScreen(Vertical):
    """Launcher that hosts five existing tool screens behind a list."""

    def tools(self) -> tuple[tuple[str, str, str], ...]:
        """(key, identity, disambiguation) per tool. The key travels as
        DATA in the option (`NamedOption.name`), never as `id` -- the
        reason is in `NamedOption`'s docstring. The order is the
        screen's: first what is managed, then what is run.

        A method, not a class attribute: a class body runs at import,
        before the app resolves the language, so labels built there
        would stay in the default one for the life of the process."""
        return (
            ("groups", t("tools.manage_groups"), t("tools.manage_groups_hint")),
            ("templates", t("tools.manage_templates"), t("tools.manage_templates_hint")),
            ("packages", t("tools.package_editor"), t("tools.package_editor_hint")),
            ("routine", t("tools.run_routine"), t("tools.run_routine_hint")),
            ("run-group", t("tools.run_group"), t("tools.run_group_hint")),
        )

    DEFAULT_CSS = """
    ToolsScreen {
        height: 1fr;
    }
    ToolsScreen ContentSwitcher {
        height: 1fr;
    }
    ToolsScreen #tools-menu {
        height: 1fr;
        margin: 1 2;
    }
    /* `auto`: a lista mede as cinco entradas e para.
       Medido, e nao suposto: com `1fr` a REGIAO da lista cresce (altura
       10 -> 28 a 120x40), mas o pintado fica byte a byte igual, porque
       `#tools-menu` ja e `height: 1fr` e as linhas extras sao vazias sobre
       o mesmo fundo. Apagar a regra tambem nao muda nada: `auto` e o
       padrao do OptionList. A redacao anterior dizia que com `1fr` "a
       moldura viraria uma caixa quase vazia com o conteudo no topo" — o
       painel ja e essa caixa, com ou sem a regra, e a frase descrevia
       `config_port.py`, onde o Panel e `height: auto` e a mesma troca
       MUDA a tela.
       A regra fica por ser a unica coisa que prende a altura da lista ao
       conteudo dela: no dia em que algo for montado abaixo da lista
       dentro deste painel, `1fr` engoliria o espaco e `auto` nao. */
    ToolsScreen #tools-menu-list {
        height: auto;
    }
    ToolsScreen .tools-container {
        height: 1fr;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._loaded_tools: set[str] = set()

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="tools-menu"):
            # Only the menu gets a frame. Each tool pane hosts a whole
            # SCREEN, which is already composed of Panels — framing it
            # again here would be a box inside a box (guideline 5).
            with Panel(t("panel.tools"), id="tools-menu"):
                yield OptionList(id="tools-menu-list")

            for chave, _identidade, _desambiguacao in self.tools():
                # Empty: the screen is mounted here on first opening, and
                # nothing else lives in this container — the "Voltar" that
                # lived here left with section 7 (the exit is now the `Esc`,
                # see `_set_actions`).
                yield Vertical(id=f"tool-{chave}", classes="tools-container")

    def on_mount(self) -> None:
        lista = self.query_one("#tools-menu-list", OptionList)
        lista.clear_options()
        for chave, identidade, desambiguacao in self.tools():
            lista.add_option(
                NamedOption(hierarchical_item(identidade, desambiguacao), chave)
            )
        self._set_actions()

    def _build_tool(self, name: str):
        """Lazily import and instantiate the tool screen widget for `name`."""
        if name == "groups":
            from dbqm.ui.screens.group_manage import GroupManageScreen
            return GroupManageScreen(id="tools-groups-inner")
        if name == "templates":
            from dbqm.ui.screens.template_manage import TemplateManageScreen
            return TemplateManageScreen(id="tools-templates-inner")
        if name == "packages":
            from dbqm.ui.screens.package_editor import PackageEditorScreen
            return PackageEditorScreen(id="tools-packages-inner")
        if name == "routine":
            from dbqm.ui.screens.exec_routine import ExecRoutineScreen
            return ExecRoutineScreen(id="tools-routine-inner")
        if name == "run-group":
            from dbqm.ui.screens.group_run import GroupRunScreen
            return GroupRunScreen(id="tools-rungroup-inner")
        raise ValueError(f"Unknown tool: {name}")

    def open_tool(self, name: str) -> None:
        """Switch to a tool's pane, building it on first use.

        Public (not just the list handler below) so a tool screen nested
        inside this launcher can send the user to a *sibling* tool — e.g.
        GroupRunScreen's EmptyState linking to "Gerenciar Grupos" when
        there is nothing to run yet.
        """
        if name not in self._loaded_tools:
            container = self.query_one(f"#tool-{name}", Vertical)
            container.mount(self._build_tool(name))
            self._loaded_tools.add(name)
        self.query_one(ContentSwitcher).current = f"tool-{name}"
        self._set_actions()

    def back_to_menu(self) -> None:
        """Goes back from the tool to the menu; does nothing if already there.

        The tool stays MOUNTED, only hidden — as `SettingsScreen` does
        with the two screens it hosts. Unmounting would be ripping the
        widget out from under a live worker: running a group runs in a
        thread and writes the progress into this tree. Going back cannot
        mean cancelling.
        """
        switcher = self.query_one(ContentSwitcher)
        if switcher.current == "tools-menu":
            return
        switcher.current = "tools-menu"
        self._set_actions()
        self.call_after_refresh(self._focus_list)

    def _focus_list(self) -> None:
        try:
            self.query_one("#tools-menu-list", OptionList).focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Action bar
    # ------------------------------------------------------------------

    def _set_actions(self) -> None:
        """Announces the `Esc` while a tool is in front.

        `DBQMApp.compose` does not render a `Footer`, so the app's
        `Binding("escape", "go_back", "Back")` is never DRAWN: without this
        line, the only exit from the five tools would be a key that nothing
        on screen mentions. Section 7 forbids a BUTTON that navigates; it
        does not forbid saying which key goes back.

        The method name is not decoration:
        `DBQMApp.on_tabbed_content_tab_activated` looks for
        `_set_actions`/`_set_list_actions` on the screen of the tab that
        was just activated. Without it, leaving the tab and coming back
        would erase the announcement with the tool still in front.

        It is a PINNED action, not an ordinary `set_actions`, because the
        hosted tools write to the same bar in their own `on_mount` —
        measured at 80x24 with `TemplateManageScreen`, the `Esc Voltar`
        disappeared under `N Novo  E Editar  R Renomear  D Remover`. See
        `ActionBar.set_pinned_action`.
        """
        try:
            barra = self.app.query_one(ActionBar)
        except Exception:
            return
        try:
            atual = self.query_one(ContentSwitcher).current
        except Exception:
            atual = "tools-menu"
        dentro = atual != "tools-menu"

        # Clears the screen's list BEFORE pinning: without this, coming back
        # to this tab with a tool open would leave the previous tab's actions
        # in the bar (and this method is precisely what the app calls when
        # reactivating the tab).
        barra.set_actions([])
        barra.set_pinned_action(
            Action(t("action.back"), "Esc", "tools-back") if dentro else None
        )
        if dentro:
            self._reask_tool(atual)

    def _reask_tool(self, container_id: str) -> None:
        """Asks the visible tool to redraw ITS actions.

        Same convention that `DBQMApp.on_tabbed_content_tab_activated`
        uses with the tab screens (`_set_actions`/`_set_list_actions`),
        applied one level below. The `try` covers the instant of the FIRST
        opening, in which the screen has just been mounted and does not
        yet have its children in the DOM — there, what fills the bar is
        the tool's own `on_mount`, right afterwards.
        """
        try:
            tela = next(iter(self.query_one(f"#{container_id}").children))
        except Exception:
            return
        for nome in ("_set_actions", "_set_list_actions"):
            setter = getattr(tela, nome, None)
            if callable(setter):
                try:
                    setter()
                except Exception:
                    pass
                return

    def on_action_selected(self, message: ActionSelected) -> None:
        if message.action_id == "tools-back":
            self.back_to_menu()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        # Filtered by id: the hosted tools have `OptionList`s of their own,
        # and their events bubble up through here.
        if event.option_list.id != "tools-menu-list":
            return
        event.stop()
        chave = getattr(event.option, "name", "")
        if any(chave == c for c, _i, _d in self.tools()):
            self.open_tool(chave)
