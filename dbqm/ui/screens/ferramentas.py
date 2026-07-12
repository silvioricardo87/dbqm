"""Ferramentas launcher screen — groups tool screens behind a simple menu."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, ContentSwitcher, Label


class FerramentasScreen(Vertical):
    """Launcher that hosts five existing tool screens behind a menu."""

    DEFAULT_CSS = """
    FerramentasScreen {
        height: 1fr;
    }
    FerramentasScreen ContentSwitcher {
        height: 1fr;
    }
    FerramentasScreen #ferr-menu {
        height: 1fr;
        padding: 1 2;
    }
    FerramentasScreen #ferr-menu-title {
        text-style: bold;
        margin-bottom: 1;
    }
    FerramentasScreen #ferr-menu Button {
        width: 100%;
        margin-bottom: 1;
    }
    FerramentasScreen .ferr-tool-container {
        height: 1fr;
    }
    FerramentasScreen .ferr-tool-container > Button {
        margin: 0 0 1 0;
        width: auto;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._loaded_tools: set[str] = set()

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="ferr-menu"):
            with Vertical(id="ferr-menu"):
                yield Label("Ferramentas", id="ferr-menu-title")
                yield Button("\U0001F465  Gerenciar Grupos", id="ferr-open-grupos")
                yield Button("\U0001F4C4  Gerenciar Templates", id="ferr-open-templates")
                yield Button("\U0001F4E6  Package Editor", id="ferr-open-packages")
                yield Button("▶  Executar Rotina", id="ferr-open-rotina")
                yield Button("▶  Executar Grupo", id="ferr-open-executar")

            for name in ("grupos", "templates", "packages", "rotina", "executar"):
                with Vertical(id=f"ferr-{name}", classes="ferr-tool-container"):
                    yield Button("←  Voltar", id=f"ferr-back-{name}")

    def _build_tool(self, name: str):
        """Lazily import and instantiate the tool screen widget for `name`."""
        if name == "grupos":
            from dbqm.ui.screens.group_manage import GroupManageScreen
            return GroupManageScreen(id="ferr-grupos-inner")
        if name == "templates":
            from dbqm.ui.screens.template_manage import TemplateManageScreen
            return TemplateManageScreen(id="ferr-templates-inner")
        if name == "packages":
            from dbqm.ui.screens.package_editor import PackageEditorScreen
            return PackageEditorScreen(id="ferr-packages-inner")
        if name == "rotina":
            from dbqm.ui.screens.exec_routine import ExecRoutineScreen
            return ExecRoutineScreen(id="ferr-rotina-inner")
        if name == "executar":
            from dbqm.ui.screens.group_run import GroupRunScreen
            return GroupRunScreen(id="ferr-executar-inner")
        raise ValueError(f"Unknown tool: {name}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("ferr-open-"):
            name = button_id.removeprefix("ferr-open-")
            if name not in self._loaded_tools:
                container = self.query_one(f"#ferr-{name}", Vertical)
                container.mount(self._build_tool(name))
                self._loaded_tools.add(name)
            self.query_one(ContentSwitcher).current = f"ferr-{name}"
            event.stop()
        elif button_id.startswith("ferr-back-"):
            self.query_one(ContentSwitcher).current = "ferr-menu"
            event.stop()
