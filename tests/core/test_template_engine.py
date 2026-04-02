"""Tests for template rendering engine."""
import pytest

from dbqm.core.template_engine import (
    extract_placeholders,
    resolve_auto_fields,
    get_input_fields,
    render_template,
)
from dbqm.core.query_engine import QueryResult
from dbqm.core.group_engine import GroupResult, ComparisonResult


class TestExtractPlaceholders:
    def test_basic(self):
        assert extract_placeholders("{{a}} and {{b}}") == ["a", "b"]

    def test_duplicates(self):
        assert extract_placeholders("{{x}} {{x}} {{y}}") == ["x", "y"]

    def test_no_placeholders(self):
        assert extract_placeholders("plain text") == []

    def test_nested_braces_ignored(self):
        assert extract_placeholders("{not} {{yes}}") == ["yes"]

    def test_multiline(self):
        content = "Line 1 {{a}}\nLine 2 {{b}}\n{{c}}"
        assert extract_placeholders(content) == ["a", "b", "c"]


class TestResolveAutoFields:
    @pytest.fixture
    def group_result(self):
        qr1 = QueryResult(
            query_name="ASD_CORRETOR",
            connection_name="conn1",
            columns=["CD_INTERNO", "SUSEP", "TP_DOCUMENTO"],
            rows=[[108866, "00000202098947", "CGC"]],
            row_count=1,
            elapsed=0.1,
        )
        qr2 = QueryResult(
            query_name="VW_ESTRUTURA",
            connection_name="conn1",
            columns=["CD_INTERNO", "STATUS"],
            rows=[],
            row_count=0,
            elapsed=0.05,
        )
        return GroupResult(
            group_name="test",
            query_results={"ASD_CORRETOR": qr1, "VW_ESTRUTURA": qr2},
            comparisons=[],
            all_match=False,
        )

    def test_param_source(self, group_result):
        fields = {"titulo": "param:CORRETOR"}
        params = {"CORRETOR": "108866"}
        resolved = resolve_auto_fields(group_result, params, fields)
        assert resolved["titulo"] == "108866"

    def test_query_count(self, group_result):
        fields = {"count": "query:ASD_CORRETOR:_count"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["count"] == "1"

    def test_query_count_label(self, group_result):
        fields = {"label": "query:ASD_CORRETOR:_count_label"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["label"] == "1 registro"

    def test_query_count_label_plural(self, group_result):
        # VW_ESTRUTURA has 0 rows
        fields = {"label": "query:VW_ESTRUTURA:_count_label"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["label"] == "0 registros"

    def test_query_column_value(self, group_result):
        fields = {"susep": "query:ASD_CORRETOR:SUSEP"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["susep"] == "00000202098947"

    def test_query_column_empty_rows(self, group_result):
        fields = {"status": "query:VW_ESTRUTURA:STATUS"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["status"] == ""

    def test_query_status_ok(self, group_result):
        fields = {"s": "query:ASD_CORRETOR:_status"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["s"] == "OK"

    def test_query_status_empty(self, group_result):
        fields = {"s": "query:VW_ESTRUTURA:_status"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["s"] == "VAZIO"

    def test_query_name(self, group_result):
        fields = {"n": "query:ASD_CORRETOR:_name"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["n"] == "ASD_CORRETOR"

    def test_literal_source(self, group_result):
        fields = {"header": "literal:INVESTIGACAO"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["header"] == "INVESTIGACAO"

    def test_empty_source_skipped(self, group_result):
        fields = {"manual": ""}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert "manual" not in resolved

    def test_unknown_query_skipped(self, group_result):
        fields = {"x": "query:NONEXISTENT:_count"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert "x" not in resolved

    def test_unknown_column_skipped(self, group_result):
        fields = {"x": "query:ASD_CORRETOR:NO_SUCH_COL"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert "x" not in resolved

    def test_row_index(self, group_result):
        fields = {"v": "query:ASD_CORRETOR:SUSEP:0"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["v"] == "00000202098947"

    def test_row_index_out_of_range(self, group_result):
        fields = {"v": "query:ASD_CORRETOR:SUSEP:5"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["v"] == ""


class TestGetInputFields:
    def test_basic(self):
        placeholders = ["a", "b", "c"]
        resolved = {"a": "val_a"}
        assert get_input_fields(placeholders, resolved) == ["b", "c"]

    def test_all_resolved(self):
        assert get_input_fields(["a"], {"a": "x"}) == []

    def test_none_resolved(self):
        assert get_input_fields(["a", "b"], {}) == ["a", "b"]


class TestRenderTemplate:
    def test_basic(self):
        result = render_template("Hello {{name}}!", {"name": "World"})
        assert result == "Hello World!"

    def test_multiple(self):
        result = render_template("{{a}} + {{b}} = {{c}}", {"a": "1", "b": "2", "c": "3"})
        assert result == "1 + 2 = 3"

    def test_unresolved_kept(self):
        result = render_template("{{known}} {{unknown}}", {"known": "yes"})
        assert result == "yes {{unknown}}"

    def test_multiline(self):
        content = "Line 1: {{x}}\nLine 2: {{y}}"
        result = render_template(content, {"x": "A", "y": "B"})
        assert result == "Line 1: A\nLine 2: B"

    def test_empty_value(self):
        result = render_template("{{field}}", {"field": ""})
        assert result == ""

    def test_realistic_template(self):
        content = (
            "INVESTIGACAO - {{titulo}}\n\n"
            "ANALISE: {{analise}}\n\n"
            "ETAPAS:\n"
            "- ({{etapa1_fonte}}): {{etapa1_count}} registros. {{etapa1_status}}.\n"
            "- ({{etapa2_fonte}}): {{etapa2_count}} registros. {{etapa2_status}}.\n"
        )
        values = {
            "titulo": "CONSULTA APOLICE",
            "analise": "Corretora nao consegue cotar",
            "etapa1_fonte": "ASD_CORRETOR",
            "etapa1_count": "1",
            "etapa1_status": "OK",
            "etapa2_fonte": "VW_ESTRUTURA",
            "etapa2_count": "0",
            "etapa2_status": "PROBLEMA IDENTIFICADO",
        }
        result = render_template(content, values)
        assert "INVESTIGACAO - CONSULTA APOLICE" in result
        assert "1 registros. OK." in result
        assert "0 registros. PROBLEMA IDENTIFICADO." in result
