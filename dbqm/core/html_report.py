"""Generate standalone HTML comparison reports."""
from __future__ import annotations

from datetime import datetime
from html import escape as h
from typing import Any

from dbqm.core.group_engine import GroupResult
from dbqm.core.exporter import _build_filepath


def export_group_html(group_result: GroupResult, params: dict | None = None) -> str:
    """Export group comparison as a standalone HTML file. Returns file path."""
    query_names = list(group_result.query_results.keys())
    filepath = _build_filepath("grupo", group_result.group_name, params, "html")

    html = _build_html(group_result, query_names, params)
    filepath.write_text(html, encoding="utf-8")
    return str(filepath)


def _status_class(status: str) -> str:
    return {"OK": "ok", "OK*": "ok", "DIFF": "diff", "ABSENT": "absent"}.get(status, "")


def _status_label(status: str) -> str:
    return {"OK": "OK", "OK*": "OK*", "DIFF": "DIFF", "ABSENT": "AUSENTE"}.get(status, status)


def _build_html(group_result: GroupResult, query_names: list[str], params: dict | None) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    overall = "CONSISTENTE" if group_result.all_match else "DIVERGENTE"
    overall_class = "ok" if group_result.all_match else "diff"

    params_html = ""
    if params:
        rows = "".join(f"<tr><td><strong>{h(str(k))}</strong></td><td>{h(str(v))}</td></tr>" for k, v in params.items())
        params_html = f'<table class="params">{rows}</table>'

    tables_html = ""
    for comp in group_result.comparisons:
        header_cols = "".join(f"<th>{h(str(qn))}</th>" for qn in query_names)
        rows_html = ""
        for row in comp.rows:
            sc = _status_class(row.status)
            cells = f'<td class="key">{h(str(row.key_value))}</td>'
            for qn in query_names:
                val = row.values.get(qn)
                cells += f"<td>{h(str(val)) if val is not None else '-'}</td>"
            cells += f'<td class="{h(sc)}">{h(_status_label(row.status))}</td>'
            rows_html += f'<tr class="{h(sc)}-row">{cells}</tr>'

        tables_html += f"""
        <h3>{h(str(comp.column))}</h3>
        <div class="filter-bar">
            <button class="filter-btn active" data-filter="all">Todos ({comp.total_keys})</button>
            <button class="filter-btn" data-filter="diff">Divergentes ({comp.diff_count})</button>
            <button class="filter-btn" data-filter="absent">Ausentes ({comp.absent_count})</button>
            <button class="filter-btn" data-filter="ok">Iguais ({comp.equal_count})</button>
        </div>
        <table class="data">
            <thead><tr><th>Chave</th>{header_cols}<th>Status</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <div class="summary">
            Iguais: {comp.equal_count}/{comp.total_keys} |
            Divergentes: {comp.diff_count}/{comp.total_keys} |
            Ausentes: {comp.absent_count}/{comp.total_keys}
            {"| Normalizados: " + str(comp.normalized_count) + "/" + str(comp.total_keys) if comp.normalized_count > 0 else ""}
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatorio - {h(group_result.group_name)}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 24px; }}
    .header {{ background: #16213e; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
    .header h1 {{ color: #00d4ff; font-size: 1.4em; }}
    .header .meta {{ color: #888; font-size: 0.85em; margin-top: 8px; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 0.85em; }}
    .badge.ok {{ background: #0d4d2e; color: #4caf50; }}
    .badge.diff {{ background: #4d2d0d; color: #ff9800; }}
    .params {{ margin: 12px 0; border-collapse: collapse; }}
    .params td {{ padding: 4px 16px 4px 0; color: #aaa; font-size: 0.9em; }}
    h3 {{ color: #00d4ff; margin: 24px 0 8px; }}
    .filter-bar {{ margin-bottom: 8px; }}
    .filter-btn {{ background: #16213e; color: #888; border: 1px solid #333; padding: 4px 12px; border-radius: 4px; cursor: pointer; margin-right: 4px; font-size: 0.8em; }}
    .filter-btn.active {{ background: #0a3d62; color: #00d4ff; border-color: #00d4ff; }}
    table.data {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 0.9em; }}
    table.data th {{ background: #16213e; color: #00d4ff; padding: 8px 12px; text-align: left; border-bottom: 2px solid #333; }}
    table.data td {{ padding: 6px 12px; border-bottom: 1px solid #222; }}
    table.data tr:hover {{ background: #16213e; }}
    .key {{ color: #fff; font-weight: 600; }}
    .ok {{ color: #4caf50; font-weight: 600; }}
    .diff {{ color: #ff9800; font-weight: 600; }}
    .absent {{ color: #f44336; font-weight: 600; }}
    .diff-row td {{ background: rgba(255,152,0,0.05); }}
    .absent-row td {{ background: rgba(244,67,54,0.05); }}
    .summary {{ color: #888; font-size: 0.85em; margin-bottom: 16px; padding: 8px 0; border-top: 1px solid #333; }}
    .hidden {{ display: none; }}
    input.search {{ background: #16213e; border: 1px solid #333; color: #e0e0e0; padding: 6px 12px; border-radius: 4px; margin-bottom: 12px; width: 300px; }}
    input.search::placeholder {{ color: #555; }}
</style>
</head>
<body>
<div class="header">
    <h1>DB Query Manager - Relatorio Comparativo</h1>
    <div class="meta">
        Grupo: <strong>{h(group_result.group_name)}</strong> |
        Data: {now} |
        <span class="badge {overall_class}">{overall}</span>
    </div>
    {params_html}
</div>

<input type="text" class="search" placeholder="Buscar por chave..." oninput="filterSearch(this.value)">

{tables_html}

<script>
document.querySelectorAll('.filter-bar').forEach(bar => {{
    bar.querySelectorAll('.filter-btn').forEach(btn => {{
        btn.addEventListener('click', () => {{
            bar.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const filter = btn.dataset.filter;
            const tbody = bar.parentElement.querySelector('table.data tbody');
            tbody.querySelectorAll('tr').forEach(row => {{
                if (filter === 'all') {{ row.classList.remove('hidden'); return; }}
                const hasClass = row.classList.contains(filter + '-row');
                row.classList.toggle('hidden', !hasClass);
            }});
        }});
    }});
}});

function filterSearch(term) {{
    term = term.toLowerCase();
    document.querySelectorAll('table.data tbody tr').forEach(row => {{
        const key = row.querySelector('.key');
        if (!key) return;
        row.classList.toggle('hidden', !key.textContent.toLowerCase().includes(term));
    }});
}}
</script>
</body>
</html>"""
