"""Ferramentas launcher screen — a lista que leva as cinco telas de ferramenta.

Ate a Task 8 desta fase o menu eram cinco botoes de largura total, um por
ferramenta, mais um "Voltar" dentro de cada painel hospedado. Os dois
padroes quebram a mesma regra da secao 7 da gramatica: **botao e acao,
nunca navegacao**. Cinco botoes empilhados que so trocam de tela sao cinco
botoes fingindo ser um menu.

O custo tambem era medido, e nao estetico: a 80x24 na DBQMApp real cada
botao ocupava 4 linhas (3 de botao + 1 de margem), 20 linhas num corpo de
14 — `Executar Rotina` e `Executar Grupo` nasciam abaixo da dobra. A lista
gasta 2 linhas por entrada e cabe inteira, com a desambiguacao de brinde.

A volta e o `Esc`, anunciado pela `ActionBar` — mesmo mecanismo que a tela
de Configuracoes usa para as duas telas que ela hospeda (`settings.py`).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import ContentSwitcher, OptionList

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.hierarchical_list import NamedOption, hierarchical_item
from dbqm.ui.widgets.panel import Panel


class ToolsScreen(Vertical):
    """Launcher that hosts five existing tool screens behind a list."""

    #: (chave, identidade, desambiguacao). A chave viaja como DADO na
    #: opcao (`NamedOption.nome`), nunca como `id` — o motivo esta na
    #: docstring de `NamedOption`. A ordem e a da tela: primeiro o que se
    #: gerencia, depois o que se executa.
    TOOLS = (
        (
            "grupos",
            "\U0001F465  Gerenciar Grupos",
            "criar, editar e remover grupos de consultas",
        ),
        (
            "templates",
            "\U0001F4C4  Gerenciar Templates",
            "modelos de SQL com parametros",
        ),
        (
            "packages",
            "\U0001F4E6  Package Editor",
            "editar spec e body de um package no banco",
        ),
        (
            "rotina",
            "▶  Executar Rotina",
            "chamar procedure ou function",
        ),
        (
            "executar",
            "▶  Executar Grupo",
            "rodar um grupo e comparar os resultados",
        ),
    )

    DEFAULT_CSS = """
    ToolsScreen {
        height: 1fr;
    }
    ToolsScreen ContentSwitcher {
        height: 1fr;
    }
    ToolsScreen #ferr-menu {
        height: 1fr;
        margin: 1 2;
    }
    /* `auto`: a lista mede as cinco entradas e para.
       Medido, e nao suposto: com `1fr` a REGIAO da lista cresce (altura
       10 -> 28 a 120x40), mas o pintado fica byte a byte igual, porque
       `#ferr-menu` ja e `height: 1fr` e as linhas extras sao vazias sobre
       o mesmo fundo. Apagar a regra tambem nao muda nada: `auto` e o
       padrao do OptionList. A redacao anterior dizia que com `1fr` "a
       moldura viraria uma caixa quase vazia com o conteudo no topo" — o
       painel ja e essa caixa, com ou sem a regra, e a frase descrevia
       `config_port.py`, onde o Panel e `height: auto` e a mesma troca
       MUDA a tela.
       A regra fica por ser a unica coisa que prende a altura da lista ao
       conteudo dela: no dia em que algo for montado abaixo da lista
       dentro deste painel, `1fr` engoliria o espaco e `auto` nao. */
    ToolsScreen #ferr-menu-list {
        height: auto;
    }
    ToolsScreen .ferr-tool-container {
        height: 1fr;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._loaded_tools: set[str] = set()

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="ferr-menu"):
            # So o menu ganha moldura. Cada painel de ferramenta hospeda
            # uma TELA inteira, que ja e composta de Panels — enquadrar de
            # novo aqui seria caixa dentro de caixa (diretriz 5).
            with Panel("\U0001F9F0  FERRAMENTAS", id="ferr-menu"):
                yield OptionList(id="ferr-menu-list")

            for chave, _identidade, _desambiguacao in self.TOOLS:
                # Vazio: a tela e montada aqui na primeira abertura, e nada
                # mais mora neste container — o "Voltar" que morava saiu
                # com a secao 7 (a saida agora e o `Esc`, ver `_set_actions`).
                yield Vertical(id=f"ferr-{chave}", classes="ferr-tool-container")

    def on_mount(self) -> None:
        lista = self.query_one("#ferr-menu-list", OptionList)
        lista.clear_options()
        for chave, identidade, desambiguacao in self.TOOLS:
            lista.add_option(
                NamedOption(hierarchical_item(identidade, desambiguacao), chave)
            )
        self._set_actions()

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

    def open_tool(self, name: str) -> None:
        """Switch to a tool's pane, building it on first use.

        Public (not just the list handler below) so a tool screen nested
        inside this launcher can send the user to a *sibling* tool — e.g.
        GroupRunScreen's EmptyState linking to "Gerenciar Grupos" when
        there is nothing to run yet.
        """
        if name not in self._loaded_tools:
            container = self.query_one(f"#ferr-{name}", Vertical)
            container.mount(self._build_tool(name))
            self._loaded_tools.add(name)
        self.query_one(ContentSwitcher).current = f"ferr-{name}"
        self._set_actions()

    def back_to_menu(self) -> None:
        """Volta da ferramenta para o menu; nao faz nada se ja estava nele.

        A ferramenta continua MONTADA, so escondida — como
        `SettingsScreen` faz com as duas telas que hospeda. Desmontar
        seria arrancar o widget debaixo de um worker vivo: a execucao de
        um grupo roda em thread e escreve o progresso nesta arvore.
        Voltar nao pode ser cancelar.
        """
        switcher = self.query_one(ContentSwitcher)
        if switcher.current == "ferr-menu":
            return
        switcher.current = "ferr-menu"
        self._set_actions()
        self.call_after_refresh(self._focus_list)

    def _focus_list(self) -> None:
        try:
            self.query_one("#ferr-menu-list", OptionList).focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Barra de acoes
    # ------------------------------------------------------------------

    def _set_actions(self) -> None:
        """Anuncia o `Esc` enquanto uma ferramenta estiver na frente.

        `DBQMApp.compose` nao rende um `Footer`, entao o
        `Binding("escape", "go_back", "Back")` do app nunca e DESENHADO:
        sem esta linha, a unica saida das cinco ferramentas seria uma
        tecla que nada na tela menciona. A secao 7 proibe um BOTAO que
        navega; nao proibe dizer qual tecla volta.

        O nome do metodo nao e enfeite:
        `DBQMApp.on_tabbed_content_tab_activated` procura
        `_set_actions`/`_set_list_actions` na tela da aba recem-ativada.
        Sem ele, sair da aba e voltar apagaria o anuncio com a ferramenta
        ainda na frente.

        E acao FIXA, nao uma `set_actions` comum, porque as ferramentas
        hospedadas escrevem na mesma barra no proprio `on_mount` — medido
        a 80x24 com `TemplateManageScreen`, o `Esc Voltar` sumia sob
        `N Novo  E Editar  R Renomear  D Remover`. Ver
        `ActionBar.set_pinned_action`.
        """
        try:
            barra = self.app.query_one(ActionBar)
        except Exception:
            return
        try:
            atual = self.query_one(ContentSwitcher).current
        except Exception:
            atual = "ferr-menu"
        dentro = atual != "ferr-menu"

        # Limpa a lista da tela ANTES de fixar: sem isto, voltar para esta
        # aba com uma ferramenta aberta deixaria na barra as acoes da aba
        # anterior (e este metodo e justamente o que o app chama ao
        # reativar a aba).
        barra.set_actions([])
        barra.set_pinned_action(
            Action("Voltar", "Esc", "ferramentas-voltar") if dentro else None
        )
        if dentro:
            self._reask_tool(atual)

    def _reask_tool(self, container_id: str) -> None:
        """Pede a ferramenta visivel que redesenhe as acoes DELA.

        Mesma convencao que `DBQMApp.on_tabbed_content_tab_activated` usa
        com as telas de aba (`_set_actions`/`_set_list_actions`), aplicada
        um nivel abaixo. O `try` cobre o instante da PRIMEIRA abertura, em
        que a tela acabou de ser montada e ainda nao tem seus filhos no
        DOM — ali quem preenche a barra e o `on_mount` da propria
        ferramenta, logo em seguida.
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
        if message.action_id == "ferramentas-voltar":
            self.back_to_menu()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        # Filtrado pelo id: as ferramentas hospedadas tem `OptionList`
        # proprias, e os eventos delas sobem por aqui.
        if event.option_list.id != "ferr-menu-list":
            return
        event.stop()
        chave = getattr(event.option, "name", "")
        if any(chave == c for c, _i, _d in self.TOOLS):
            self.open_tool(chave)
