"""GroupResultWidget — displays group comparison results in flat or pivoted mode."""

from __future__ import annotations

from textual.containers import Vertical, VerticalScroll
from textual.content import Content
from textual.reactive import reactive
from textual.widgets import DataTable, Static

from dbqm.core.group_engine import GroupResult, ComparisonResult
from dbqm.ui.utils import sanitize_id
from dbqm.ui.widgets.veredito import marcar_veredito

# Os status internos do motor de comparacao (dbqm.core.group_engine) usam um
# vocabulario proprio, historico; o componente de veredito usa outro. Este
# dict e a unica ponte entre os dois — nao se espalha essa traducao pelo
# resto do arquivo.
_STATUS_PARA_VEREDITO: dict[str, str] = {
    "OK": "igual",
    "OK*": "igual-normalizado",
    "DIFF": "difere",
    "ABSENT": "ausente",
}


def _status_cell(status: str) -> Content:
    """Celula de status pronta para `DataTable.add_row`.

    `add_row` parseia string com o Rich puro, que nao resolve `$token`
    (levanta `rich.errors.MarkupError`); por isso o markup do veredito
    precisa passar por `Content.from_markup` antes de chegar la — o mesmo
    padrao usado em `dbqm/ui/screens/history.py`.

    Um status fora do vocabulario conhecido explode aqui (KeyError vira
    ValueError via `marcar_veredito`), nunca renderiza uma celula sem cor
    silenciosamente.
    """
    if status not in _STATUS_PARA_VEREDITO:
        raise ValueError(f"status de comparacao desconhecido: {status!r}")
    return Content.from_markup(marcar_veredito(_STATUS_PARA_VEREDITO[status]))


class GroupResultWidget(Vertical, can_focus=False):
    """Widget that displays group comparison results with flat/pivoted toggle and status filtering."""

    DEFAULT_CSS = """
    GroupResultWidget {
        height: 1fr;
    }
    GroupResultWidget #gr-scroll {
        height: 1fr;
    }
    GroupResultWidget .gr-summary {
        height: auto;
        padding: 1 1;
        background: $surface;
        color: $text-muted;
    }
    GroupResultWidget .gr-section-title {
        height: auto;
        padding: 0 1;
        color: $accent;
        text-style: bold;
    }
    GroupResultWidget DataTable {
        height: auto;
        max-height: 30;
        margin: 0 1 1 1;
    }
    """

    mode: reactive[str] = reactive("flat")

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._group_result: GroupResult | None = None
        self._status_filter: set[str] | None = None
        self._hide_status: bool = False

    def compose(self):
        yield VerticalScroll(id="gr-scroll")
        yield Static("", classes="gr-summary", id="gr-summary")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_result(self, group_result: GroupResult, hide_status: bool = False) -> None:
        """Populate widget from a GroupResult."""
        self._group_result = group_result
        self._status_filter = None
        self._hide_status = hide_status
        self._refresh_view()

    def toggle_mode(self) -> None:
        """Switch between flat and pivoted display modes."""
        self.mode = "pivoted" if self.mode == "flat" else "flat"
        self._refresh_view()

    def filter_status(self, statuses: set[str]) -> None:
        """Only show rows matching given statuses. Pass empty set or None to clear."""
        if not statuses:
            self._status_filter = None
        else:
            self._status_filter = statuses
        self._refresh_view()

    @property
    def group_result(self) -> GroupResult | None:
        return self._group_result

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _refresh_view(self) -> None:
        if self._group_result is None:
            return

        scroll = self.query_one("#gr-scroll", VerticalScroll)
        scroll.remove_children()

        if self.mode == "flat":
            self._render_flat(scroll)
        else:
            self._render_pivoted(scroll)

        self._render_summary()
        # Auto-focus first DataTable for keyboard navigation
        self.call_after_refresh(self._focus_first_table)

    def _focus_first_table(self) -> None:
        """Focus the first DataTable in the results."""
        try:
            tables = self.query(DataTable)
            if tables:
                tables.first().focus()
                if tables.first().row_count > 0:
                    tables.first().move_cursor(row=0)
        except Exception:
            pass

    def _render_flat(self, container) -> None:
        """Render flat mode: one DataTable per compare column."""
        gr = self._group_result
        query_names = list(gr.query_results.keys())

        for comp in gr.comparisons:
            # Section title
            container.mount(
                Static(f"Coluna: {str(comp.column)}", classes="gr-section-title")
            )

            table = DataTable()
            table.add_column("Chave", key="key")
            for qn in query_names:
                table.add_column(str(qn), key=sanitize_id(str(qn)))
            if not self._hide_status:
                table.add_column("Status", key="status")

            rows = comp.rows
            if self._status_filter and not self._hide_status:
                rows = [r for r in rows if r.status in self._status_filter]

            for row in rows:
                cells = [str(row.key_value)]
                for qn in query_names:
                    val = row.values.get(qn)
                    cells.append(str(val) if val is not None else "-")
                if not self._hide_status:
                    cells.append(_status_cell(row.status))
                table.add_row(*cells, key=str(row.key_value))

            container.mount(table)

    def _render_pivoted(self, container) -> None:
        """Render pivoted mode: one DataTable per join key value."""
        gr = self._group_result
        query_names = list(gr.query_results.keys())
        compare_columns = [c.column for c in gr.comparisons]

        # Build lookup: {(key_value, column): ComparisonRow}
        lookup = {}
        all_keys = []
        for comp in gr.comparisons:
            for row in comp.rows:
                lookup[(row.key_value, comp.column)] = row
                if row.key_value not in all_keys:
                    all_keys.append(row.key_value)

        # Filter keys by status if active
        if self._status_filter:
            filtered_keys = []
            for key in all_keys:
                for comp in gr.comparisons:
                    cr = lookup.get((key, comp.column))
                    if cr and cr.status in self._status_filter:
                        if key not in filtered_keys:
                            filtered_keys.append(key)
                        break
            all_keys = filtered_keys

        for key in all_keys:
            container.mount(
                Static(f"Chave: {str(key)}", classes="gr-section-title")
            )

            table = DataTable()
            table.add_column("Consulta", key="__consulta__")
            for col in compare_columns:
                table.add_column(str(col), key=f"__col_{col}__")
            if not self._hide_status:
                table.add_column("Status", key="__status__")

            # One row per query
            for qn in query_names:
                cells = [str(qn)]
                for col in compare_columns:
                    cr = lookup.get((key, col))
                    val = cr.values.get(qn) if cr else None
                    cells.append(str(val) if val is not None else "-")
                if not self._hide_status:
                    cells.append("")  # no per-query status
                table.add_row(*cells, key=f"q::{qn}")

            # Result row at the bottom (only when showing status)
            if not self._hide_status:
                result_cells = ["Resultado"]
                worst_statuses = []
                for col in compare_columns:
                    cr = lookup.get((key, col))
                    status = str(cr.status) if cr else "ABSENT"
                    worst_statuses.append(status)
                    result_cells.append(_status_cell(status))
                priority = {"ABSENT": 3, "DIFF": 2, "OK*": 1, "OK": 0}
                overall = max(worst_statuses, key=lambda s: priority.get(s, 0))
                result_cells.append(_status_cell(overall))
                table.add_row(*result_cells, key="__resultado__")

            container.mount(table)

    def _render_summary(self) -> None:
        """Render summary section with counts per column."""
        gr = self._group_result
        if gr is None:
            return

        summary = self.query_one("#gr-summary", Static)

        if self._hide_status:
            summary.update("[dim]Exibindo valores originais (sem mapeamento)[/]")
            return

        lines = []
        overall = "CONSISTENTE" if gr.all_match else "DIVERGENTE"
        overall_status = "igual" if gr.all_match else "difere"
        lines.append(f"[bold]{marcar_veredito(overall_status, texto=overall)}[/]")
        lines.append("")

        for comp in gr.comparisons:
            col_name = str(comp.column) if comp.column is not None else ""
            lines.append(f"[bold]{col_name}[/]:")
            lines.append(f"  {marcar_veredito('igual', texto='Iguais:')}      {comp.equal_count}/{comp.total_keys}")
            if comp.normalized_count > 0:
                lines.append(f"  {marcar_veredito('igual-normalizado', texto='Normalizados:')} {comp.normalized_count}/{comp.total_keys}")
            lines.append(f"  {marcar_veredito('difere', texto='Diferentes:')}  {comp.diff_count}/{comp.total_keys}")
            lines.append(f"  {marcar_veredito('ausente', texto='Ausentes:')}    {comp.absent_count}/{comp.total_keys}")

        summary.update("\n".join(lines))
