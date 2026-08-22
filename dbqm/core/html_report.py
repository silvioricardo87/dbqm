"""Generate standalone HTML comparison reports."""
from __future__ import annotations

from datetime import datetime
from html import escape as h
from typing import Any

from dbqm.core.group_engine import GroupResult
from dbqm.core.exporter import _build_filepath
from dbqm.design.tokens import TOKENS_CLARO, TOKENS_ESCURO


def css_variaveis(tokens: dict[str, str]) -> str:
    """Emite os design tokens como custom properties, para o <style> do relatorio."""
    linhas = "\n".join(f"  --{chave}: {valor};" for chave, valor in sorted(tokens.items()))
    return f":root {{\n{linhas}\n}}"


def _bloco_tema_claro(tokens: dict[str, str]) -> str:
    """Sobrescreve os tokens dentro de uma media query, para o SO/navegador do leitor.

    O relatorio e um arquivo HTML autonomo — nao ha tema ativo da TUI para
    herdar — entao ele responde a preferencia de cor do sistema em vez de
    ficar preso a uma variante fixa. A base (:root, tema escuro) ja carrega a
    paleta completa; aqui so a variante clara sobrescreve, entao nenhum token
    fica com definicao unica dentro da media query.
    """
    linhas = "\n".join(f"    --{chave}: {valor};" for chave, valor in sorted(tokens.items()))
    return f"@media (prefers-color-scheme: light) {{\n  :root {{\n{linhas}\n  }}\n}}"


def export_group_html(group_result: GroupResult, params: dict | None = None) -> str:
    """Export group comparison as a standalone HTML file. Returns file path."""
    query_names = list(group_result.query_results.keys())
    filepath = _build_filepath("grupos", group_result.group_name, params=params, ext="html")

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
{css_variaveis(TOKENS_ESCURO)}
{_bloco_tema_claro(TOKENS_CLARO)}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--fundo); color: var(--texto); padding: 24px; }}
    .header {{ background: var(--painel); border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
    .header h1 {{ color: var(--identidade); font-size: 1.4em; }}
    .header .meta {{ color: var(--texto-apoio); font-size: 0.85em; margin-top: 8px; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 0.85em; }}
    .badge.ok {{ background: color-mix(in srgb, var(--veredito-igual) 20%, var(--painel)); color: var(--veredito-igual); }}
    .badge.diff {{ background: color-mix(in srgb, var(--veredito-difere) 20%, var(--painel)); color: var(--veredito-difere); }}
    .params {{ margin: 12px 0; border-collapse: collapse; }}
    .params td {{ padding: 4px 16px 4px 0; color: var(--texto-apoio); font-size: 0.9em; }}
    h3 {{ color: var(--identidade); margin: 24px 0 8px; }}
    .filter-bar {{ margin-bottom: 8px; }}
    .filter-btn {{ background: var(--painel); color: var(--texto-apoio); border: 1px solid var(--borda); padding: 4px 12px; border-radius: 4px; cursor: pointer; margin-right: 4px; font-size: 0.8em; }}
    .filter-btn.active {{ background: var(--superficie-elevada); color: var(--identidade); border-color: var(--identidade); }}
    table.data {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 0.9em; }}
    table.data th {{ background: var(--painel); color: var(--identidade); padding: 8px 12px; text-align: left; border-bottom: 2px solid var(--borda); }}
    table.data td {{ padding: 6px 12px; border-bottom: 1px solid var(--borda); }}
    table.data tr:hover {{ background: var(--superficie-elevada); }}
    .key {{ color: var(--texto-forte); font-weight: 600; }}
    .ok {{ color: var(--veredito-igual); font-weight: 600; }}
    .diff {{ color: var(--veredito-difere); font-weight: 600; }}
    .absent {{ color: var(--veredito-ausente); font-weight: 600; }}
    .diff-row td {{ background: color-mix(in srgb, var(--veredito-difere) 10%, transparent); }}
    .absent-row td {{ background: color-mix(in srgb, var(--veredito-ausente) 10%, transparent); }}
    .summary {{ color: var(--texto-apoio); font-size: 0.85em; margin-bottom: 16px; padding: 8px 0; border-top: 1px solid var(--borda); }}
    .hidden {{ display: none; }}
    input.search {{ background: var(--painel); border: 1px solid var(--borda); color: var(--texto); padding: 6px 12px; border-radius: 4px; margin-bottom: 12px; width: 300px; }}
    input.search::placeholder {{ color: var(--texto-desabilitado); }}
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
