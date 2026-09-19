"""Tests for HTML report generation."""
from pathlib import Path
from html import escape

from dbqm.core.html_report import (
    export_group_html,
    export_query_html,
    _status_class,
    _status_label,
    _build_html,
)


class TestHelpers:
    def test_status_class(self):
        assert _status_class("OK") == "ok"
        assert _status_class("DIFF") == "diff"
        assert _status_class("ABSENT") == "absent"
        assert _status_class("UNKNOWN") == ""

    def test_status_label(self):
        assert _status_label("OK") == "OK"
        assert _status_label("DIFF") == "DIFFERS"
        assert _status_label("ABSENT") == "ABSENT"


class TestBuildHtml:
    def test_html_structure(self, sample_group_result):
        html = _build_html(sample_group_result, ["q1", "q2"], {"param": "val"})
        assert "<!DOCTYPE html>" in html
        assert "test_group" in html
        assert "DIVERGENT" in html
        assert "param" in html
        assert "val" in html

    def test_html_escaping(self, sample_group_result):
        """Ensure XSS-safe output."""
        sample_group_result.group_name = '<script>alert("xss")</script>'
        html = _build_html(sample_group_result, ["q1", "q2"], None)
        assert "<script>alert" not in html
        assert escape('<script>alert("xss")</script>') in html

    def test_export_creates_file(self, tmp_config_dir, sample_group_result):
        path = export_group_html(sample_group_result)
        assert Path(path).exists()
        assert path.endswith(".html")


def test_report_uses_design_system_colors():
    """O relatorio tinha paleta propria so porque core/ nao podia importar ui/."""
    from dbqm.core.html_report import css_variables
    from dbqm.design.tokens import DARK_TOKENS

    css = css_variables(DARK_TOKENS)
    for chave, valor in DARK_TOKENS.items():
        assert f"--{chave}: {valor}" in css


def test_report_no_longer_carries_the_old_palette():
    fonte = Path("dbqm/core/html_report.py").read_text(encoding="utf-8")
    for orfa in ("#00d4ff", "#16213e", "#4caf50", "#ff9800", "#f44336"):
        assert orfa not in fonte, f"{orfa} sobrou da paleta paralela"


def _result(rows=None, columns=None):
    from dbqm.core.query_engine import QueryResult
    return QueryResult(
        query_name="clientes",
        connection_name="prod",
        columns=columns if columns is not None else ["ID", "NOME"],
        rows=rows if rows is not None else [[1, "Ana"], [2, None]],
        row_count=2,
        elapsed=0.25,
    )


def test_query_html_writes_an_html_file(tmp_path, monkeypatch):
    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    caminho = export_query_html(_result())
    assert caminho.endswith(".html")
    assert Path(caminho).exists()


def test_query_html_renders_every_cell(tmp_path, monkeypatch):
    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    texto = Path(export_query_html(_result())).read_text(encoding="utf-8")
    assert "<td>Ana</td>" in texto
    assert "ID" in texto and "NOME" in texto


def test_query_html_renders_none_as_an_empty_cell(tmp_path, monkeypatch):
    """A None must not reach the page as the literal string 'None'."""
    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    texto = Path(export_query_html(_result())).read_text(encoding="utf-8")
    assert "<td></td>" in texto
    assert ">None<" not in texto


def test_query_html_escapes_values(tmp_path, monkeypatch):
    """A value is data, never markup."""
    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    linhas = [["<script>alert(1)</script>", "x"]]
    texto = Path(export_query_html(_result(rows=linhas))).read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in texto
    assert escape("<script>alert(1)</script>") in texto


def test_query_html_escapes_column_names(tmp_path, monkeypatch):
    """A column name is data too -- an expression alias can carry anything."""
    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    resultado = _result(columns=["<b>ID</b>", "NOME"], rows=[[1, "Ana"]])
    texto = Path(export_query_html(resultado)).read_text(encoding="utf-8")
    assert "<th><b>ID</b></th>" not in texto
    assert escape("<b>ID</b>") in texto


def test_query_html_survives_zero_rows(tmp_path, monkeypatch):
    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    texto = Path(export_query_html(_result(rows=[]))).read_text(encoding="utf-8")
    assert "<table" in texto


def test_query_html_carries_the_design_tokens(tmp_path, monkeypatch):
    """Same shell as the group report -- not a second, drifting stylesheet."""
    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    texto = Path(export_query_html(_result())).read_text(encoding="utf-8")
    assert "prefers-color-scheme: light" in texto
    assert "--" in texto and ":root" in texto


def test_query_html_lands_beside_its_csv_sibling(tmp_path, monkeypatch):
    """The four exports of one query belong in one directory. This asserts
    parity with the existing exporter rather than re-deriving the layout --
    if the convention moves, both move together or this fails."""
    from dbqm.core.exporter import export_query_csv

    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    csv_path = Path(export_query_csv(_result()))
    html_path = Path(export_query_html(_result()))
    assert html_path.parent == csv_path.parent
    assert html_path.suffix == ".html"


def test_query_html_names_the_file_after_the_connection(tmp_path, monkeypatch):
    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    caminho = export_query_html(_result())
    assert "prod" in Path(caminho).name


def test_query_html_renders_zero_as_itself_not_as_an_empty_cell(tmp_path, monkeypatch):
    """0 and "" are legitimate values, not missing data -- only None is missing.
    `h(str(v)) if v else ""` would blank a real 0 exactly like it blanks a
    None; this fixture has a 0 and a None side by side so that distinction is
    actually exercised, unlike a fixture whose only falsy value is None."""
    monkeypatch.setattr("dbqm.core.exporter.EXPORTS_DIR", tmp_path)
    resultado = _result(columns=["QTD", "OBS", "STATUS"], rows=[[0, "", None]])
    texto = Path(export_query_html(resultado)).read_text(encoding="utf-8")
    assert "<td>0</td>" in texto
    assert texto.count("<td></td>") >= 2
