"""Tests for HTML report generation."""
from pathlib import Path
from html import escape

from dbqm.core.html_report import export_group_html, _status_class, _status_label, _build_html


class TestHelpers:
    def test_status_class(self):
        assert _status_class("OK") == "ok"
        assert _status_class("DIFF") == "diff"
        assert _status_class("ABSENT") == "absent"
        assert _status_class("UNKNOWN") == ""

    def test_status_label(self):
        assert _status_label("OK") == "OK"
        assert _status_label("DIFF") == "DIFF"
        assert _status_label("ABSENT") == "AUSENTE"


class TestBuildHtml:
    def test_html_structure(self, sample_group_result):
        html = _build_html(sample_group_result, ["q1", "q2"], {"param": "val"})
        assert "<!DOCTYPE html>" in html
        assert "test_group" in html
        assert "DIVERGENTE" in html
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


def test_relatorio_usa_as_cores_do_design_system():
    """O relatorio tinha paleta propria so porque core/ nao podia importar ui/."""
    from dbqm.core.html_report import css_variaveis
    from dbqm.design.tokens import TOKENS_ESCURO

    css = css_variaveis(TOKENS_ESCURO)
    for chave, valor in TOKENS_ESCURO.items():
        assert f"--{chave}: {valor}" in css


def test_relatorio_nao_carrega_mais_a_paleta_antiga():
    fonte = Path("dbqm/core/html_report.py").read_text(encoding="utf-8")
    for orfa in ("#00d4ff", "#16213e", "#4caf50", "#ff9800", "#f44336"):
        assert orfa not in fonte, f"{orfa} sobrou da paleta paralela"
