"""Multi-Exec screen — run one ad-hoc SQL across a checkbox-selected set of
connections and compare the results (redesign "Option 3").

The old query-based group execution lives in ``group_run.py`` (Ferramentas tab).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Select, SelectionList, TextArea
from textual.widgets.selection_list import Selection
from textual import work

from dbqm.ui.utils import escape_markup
from dbqm.ui.widgets.skeleton import Skeleton
from dbqm.ui.widgets.panel import Panel
from dbqm.ui.widgets.group_result import GroupResultWidget
from dbqm.ui.widgets.progress import ProgressIndicator


class GroupExecScreen(Vertical):
    """Run one SQL across several connections and compare the results.

    Left: target panel (saved ad-hoc group Select + connection checklist).
    Right: SQL editor above, comparison display below.
    """

    DEFAULT_CSS = """
    GroupExecScreen {
        height: 1fr;
    }
    GroupExecScreen #ge-body {
        height: 1fr;
    }
    GroupExecScreen #ge-target-panel {
        width: 42;
    }
    GroupExecScreen #ge-right {
        width: 1fr;
    }
    GroupExecScreen #ge-group-btns {
        height: auto;
    }
    GroupExecScreen #ge-group-btns Button {
        margin: 0 1 0 0;
    }
    GroupExecScreen #group-saved-select {
        width: 100%;
        margin-bottom: 1;
    }
    GroupExecScreen #conn-checklist {
        height: 1fr;
        margin-top: 1;
    }
    GroupExecScreen #ge-execute {
        width: 100%;
        margin-top: 1;
    }
    GroupExecScreen #ge-editor-panel {
        height: 40%;
    }
    GroupExecScreen #group-sql {
        height: 1fr;
    }
    GroupExecScreen #ge-results-skeleton {
        display: none;
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

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="ge-body"):
            with Panel("🎯  ALVO DA EXECUCAO", accent=True, id="ge-target-panel"):
                yield Select([], prompt="Grupo salvo", id="group-saved-select")
                with Horizontal(id="ge-group-btns"):
                    yield Button("Carregar", id="ge-load-group")
                    yield Button("Salvar selecao", id="ge-save-group")
                yield SelectionList(id="conn-checklist")
                yield Button(
                    "Executar (Ctrl+Enter)",
                    variant="primary",
                    id="ge-execute",
                )
            with Vertical(id="ge-right"):
                with Panel("✏️  SQL DO GRUPO", id="ge-editor-panel"):
                    yield TextArea("", language="sql", id="group-sql")
                with Panel("📊  COMPARACAO DE RESULTADOS", id="ge-results-panel"):
                    # The shape of the comparison to come, not a spinner: it
                    # reserves the right amount of space while the
                    # connections execute.
                    # 9 is the median of the maintainer's 68 saved queries
                    # (min 1, max 36), surveyed in phase 1 of this plan — not
                    # reproducible from the config/queries.json of this
                    # repository, which is another, smaller set. It is the
                    # best guess available (much better than the arbitrary
                    # 4), not a truth of the domain: a skeleton with the
                    # wrong shape causes the very layout jump it exists to
                    # prevent.
                    yield Skeleton(rows=8, columns=9, id="ge-results-skeleton")
                    yield GroupResultWidget(id="group-results")
        yield ProgressIndicator()

    def on_mount(self) -> None:
        self._populate_connections(set())
        self._refresh_saved_groups()

    # ------------------------------------------------------------------
    # Population helpers
    # ------------------------------------------------------------------

    def _populate_connections(self, checked: set[str]) -> None:
        """(Re)build the connection checklist, pre-checking ``checked`` names."""
        from dbqm.models.connection import load_connections

        checklist = self.query_one("#conn-checklist", SelectionList)
        checklist.clear_options()
        for c in load_connections():
            label = f"{c.name}  ({c.db_type} - {c.display_target()})"
            checklist.add_option(Selection(label, c.name, c.name in checked))

    def _refresh_saved_groups(self) -> None:
        """Load ONLY ad-hoc groups into the saved-group Select."""
        from dbqm.models.group import load_groups

        groups = [g for g in load_groups() if g.adhoc_sql]
        options = [(g.name, g.name) for g in sorted(groups, key=lambda g: g.name.lower())]
        select = self.query_one("#group-saved-select", Select)
        select.set_options(options)

    # ------------------------------------------------------------------
    # Buttons / shortcuts
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        if event.key == "ctrl+enter":
            event.prevent_default()
            event.stop()
            self._handle_execute()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "ge-execute":
            self._handle_execute()
        elif btn_id == "ge-load-group":
            self._load_group()
        elif btn_id == "ge-save-group":
            self._save_selection()

    # ------------------------------------------------------------------
    # Load / save saved groups
    # ------------------------------------------------------------------

    def _load_group(self) -> None:
        from dbqm.models.group import find_group

        select = self.query_one("#group-saved-select", Select)
        name = select.value
        if name is Select.BLANK or not isinstance(name, str):
            self.notify("Selecione um grupo salvo.", severity="warning")
            return

        group = find_group(name)
        if group is None or not group.adhoc_sql:
            self.notify(f"Grupo '{name}' nao encontrado.", severity="error")
            return

        self.query_one("#group-sql", TextArea).load_text(group.adhoc_sql)
        self._populate_connections(set(group.connections))
        self.notify(f"Grupo '{name}' carregado.", timeout=3)

    def _save_selection(self) -> None:
        sql = self.query_one("#group-sql", TextArea).text
        checked = list(self.query_one("#conn-checklist", SelectionList).selected)
        if not sql.strip():
            self.notify("Digite o SQL antes de salvar.", severity="warning")
            return
        if not checked:
            self.notify("Marque ao menos uma conexao.", severity="warning")
            return

        from dbqm.ui.modals.text_input import TextInputModal

        modal = TextInputModal(
            "Salvar selecao como grupo",
            message="Nome do grupo",
        )
        self.app.push_screen(modal, callback=self._on_save_name)

    def _on_save_name(self, name: str | None) -> None:
        if name is None:
            return
        name = name.strip()
        if not name:
            self.notify("Nome invalido.", severity="warning")
            return

        from dbqm.models.group import Group, load_groups, save_groups

        sql = self.query_one("#group-sql", TextArea).text
        checked = list(self.query_one("#conn-checklist", SelectionList).selected)

        new_group = Group(
            name=name,
            description="",
            queries=[],
            join_key="",
            adhoc_sql=sql,
            connections=checked,
        )

        groups = load_groups()
        groups = [g for g in groups if g.name != name]
        groups.append(new_group)
        save_groups(groups)

        self._refresh_saved_groups()
        self.notify(f"Grupo '{name}' salvo.", timeout=3)

    # ------------------------------------------------------------------
    # Execution + comparison
    # ------------------------------------------------------------------

    def _handle_execute(self) -> None:
        sql = self.query_one("#group-sql", TextArea).text.strip()
        checked = list(self.query_one("#conn-checklist", SelectionList).selected)
        if not sql:
            self.notify("Digite o SQL a executar.", severity="warning")
            return
        if len(checked) < 1:
            self.notify("Marque ao menos uma conexao.", severity="warning")
            return

        self.query_one(ProgressIndicator).start(
            f"Executando em {len(checked)} conexao(oes)..."
        )
        # Shape of the comparison that is coming, in place of whatever the
        # panel showed before (empty on first run, a stale comparison on a
        # re-run) — avoids a jump when the real table lands.
        self.query_one("#group-results", GroupResultWidget).display = False
        self.query_one("#ge-results-skeleton", Skeleton).display = True
        self._run(sql, checked)

    @work(thread=True)
    def _run(self, sql: str, conn_names: list[str]) -> None:
        """Run the same SQL on each connection and compare the results."""
        from dbqm.models.connection import find_connection
        from dbqm.core.query_engine import execute_adhoc
        from dbqm.core.group_engine import run_comparison, GroupResult

        try:
            results = {}
            for cname in conn_names:
                conn = find_connection(cname)
                if conn is None:
                    self.app.call_from_thread(
                        self.notify,
                        f"Conexao '{cname}' nao encontrada.",
                        severity="warning",
                    )
                    continue

                self.app.call_from_thread(
                    self._update_progress,
                    f"Executando em [bold]{escape_markup(cname)}[/]...",
                )

                try:
                    res = execute_adhoc(sql, conn, {})
                except Exception as e:
                    self.app.call_from_thread(
                        self.notify,
                        f"Erro em '{cname}': {e}",
                        severity="error",
                        timeout=8,
                    )
                    continue

                # DML without auto_commit returns (AdhocResult, db_connection).
                if isinstance(res, tuple):
                    res = res[0]

                if not res.success:
                    self.app.call_from_thread(
                        self.notify,
                        f"Erro em '{cname}': {res.error}",
                        severity="error",
                        timeout=8,
                    )
                    continue

                results[cname] = res

            if len(results) < 1:
                self.app.call_from_thread(
                    self._on_error, "Nenhuma conexao executou com sucesso."
                )
                return

            # Auto-derive the join key + compare columns from the columns that
            # are common to every result (defensive intersection).
            first = next(iter(results))
            base_cols = list(results[first].columns)
            common = [
                c for c in base_cols
                if all(c in r.columns for r in results.values())
            ]
            if not common:
                self.app.call_from_thread(
                    self._on_error, "Consultas nao retornaram colunas comparaveis."
                )
                return

            join_key = common[0]
            compare_columns = common[1:]

            comparisons = run_comparison(results, join_key, compare_columns)
            all_match = all(
                c.diff_count == 0 and c.absent_count == 0 for c in comparisons
            )
            group_result = GroupResult(
                group_name="(ad-hoc)",
                query_results=results,
                comparisons=comparisons,
                all_match=all_match,
            )

            self.app.call_from_thread(self._show_result, group_result)
        except Exception as e:
            self.app.call_from_thread(self._on_error, f"Erro inesperado: {e}")

    def _update_progress(self, msg: str) -> None:
        progress = self.query_one(ProgressIndicator)
        if progress:
            progress.update_message(msg)

    def _on_error(self, message: str) -> None:
        self.query_one(ProgressIndicator).stop()
        self.query_one("#ge-results-skeleton", Skeleton).display = False
        self.query_one("#group-results", GroupResultWidget).display = True
        self.notify(message, severity="error", timeout=8)

    def _show_result(self, group_result) -> None:
        self.query_one(ProgressIndicator).stop()
        self.query_one("#ge-results-skeleton", Skeleton).display = False
        grw = self.query_one("#group-results", GroupResultWidget)
        grw.display = True
        grw.load_result(group_result)
