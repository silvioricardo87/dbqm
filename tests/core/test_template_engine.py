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


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def group_result():
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


@pytest.fixture
def multi_row_result():
    """GroupResult with a query that returns multiple rows."""
    qr = QueryResult(
        query_name="REGISTROS",
        connection_name="conn1",
        columns=["ID", "NOME", "STATUS"],
        rows=[
            [1, "Alice", "ativo"],
            [2, "Bob", "inativo"],
            [3, "Carol", None],
        ],
        row_count=3,
        elapsed=0.2,
    )
    return GroupResult(
        group_name="multi",
        query_results={"REGISTROS": qr},
        comparisons=[],
        all_match=True,
    )


# ------------------------------------------------------------------
# TestExtractPlaceholders
# ------------------------------------------------------------------

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

    def test_empty_string(self):
        assert extract_placeholders("") == []

    def test_adjacent_placeholders(self):
        assert extract_placeholders("{{a}}{{b}}") == ["a", "b"]

    def test_placeholder_with_underscores(self):
        assert extract_placeholders("{{etapa_1_fonte}}") == ["etapa_1_fonte"]

    def test_non_word_chars_not_captured(self):
        """Placeholders with spaces or special chars are not matched."""
        assert extract_placeholders("{{not valid}}") == []
        assert extract_placeholders("{{a-b}}") == []


# ------------------------------------------------------------------
# TestResolveAutoFields
# ------------------------------------------------------------------

class TestResolveAutoFields:
    def test_param_source(self, group_result):
        fields = {"titulo": "param:CORRETOR"}
        params = {"CORRETOR": "108866"}
        resolved = resolve_auto_fields(group_result, params, fields)
        assert resolved["titulo"] == "108866"

    def test_param_missing_returns_empty(self, group_result):
        fields = {"x": "param:NONEXISTENT"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["x"] == ""

    def test_query_count(self, group_result):
        fields = {"count": "query:ASD_CORRETOR:_count"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["count"] == "1"

    def test_query_count_label(self, group_result):
        fields = {"label": "query:ASD_CORRETOR:_count_label"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["label"] == "1 registro"

    def test_query_count_label_plural(self, group_result):
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

    def test_literal_with_colons(self, group_result):
        """Literal text after first colon is preserved, even if it contains colons."""
        fields = {"x": "literal:hora:10:30"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert resolved["x"] == "hora:10:30"

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

    def test_invalid_source_type_skipped(self, group_result):
        fields = {"x": "unknown_type:value"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert "x" not in resolved

    def test_source_without_colon_skipped(self, group_result):
        fields = {"x": "nocolon"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert "x" not in resolved

    def test_query_source_without_field_skipped(self, group_result):
        """query:NAME without a field part is skipped."""
        fields = {"x": "query:ASD_CORRETOR"}
        resolved = resolve_auto_fields(group_result, {}, fields)
        assert "x" not in resolved

    def test_none_column_value(self, multi_row_result):
        """None values in columns are rendered as empty string."""
        fields = {"s": "query:REGISTROS:STATUS:2"}
        resolved = resolve_auto_fields(multi_row_result, {}, fields)
        assert resolved["s"] == ""

    def test_multi_row_specific_indices(self, multi_row_result):
        fields = {
            "first": "query:REGISTROS:NOME:0",
            "second": "query:REGISTROS:NOME:1",
            "third": "query:REGISTROS:NOME:2",
        }
        resolved = resolve_auto_fields(multi_row_result, {}, fields)
        assert resolved["first"] == "Alice"
        assert resolved["second"] == "Bob"
        assert resolved["third"] == "Carol"

    def test_multi_row_count(self, multi_row_result):
        fields = {"n": "query:REGISTROS:_count"}
        resolved = resolve_auto_fields(multi_row_result, {}, fields)
        assert resolved["n"] == "3"

    def test_multi_row_count_label(self, multi_row_result):
        fields = {"l": "query:REGISTROS:_count_label"}
        resolved = resolve_auto_fields(multi_row_result, {}, fields)
        assert resolved["l"] == "3 registros"

    def test_mixed_sources(self, group_result):
        """Multiple source types resolve together."""
        fields = {
            "titulo": "literal:INVESTIGACAO",
            "corretor": "param:CORRETOR",
            "susep": "query:ASD_CORRETOR:SUSEP",
            "count_vw": "query:VW_ESTRUTURA:_count",
            "manual_field": "",
        }
        params = {"CORRETOR": "108866"}
        resolved = resolve_auto_fields(group_result, params, fields)
        assert resolved["titulo"] == "INVESTIGACAO"
        assert resolved["corretor"] == "108866"
        assert resolved["susep"] == "00000202098947"
        assert resolved["count_vw"] == "0"
        assert "manual_field" not in resolved

    def test_empty_fields_dict(self, group_result):
        resolved = resolve_auto_fields(group_result, {}, {})
        assert resolved == {}


# ------------------------------------------------------------------
# TestGetInputFields
# ------------------------------------------------------------------

class TestGetInputFields:
    def test_basic(self):
        placeholders = ["a", "b", "c"]
        resolved = {"a": "val_a"}
        assert get_input_fields(placeholders, resolved) == ["b", "c"]

    def test_all_resolved(self):
        assert get_input_fields(["a"], {"a": "x"}) == []

    def test_none_resolved(self):
        assert get_input_fields(["a", "b"], {}) == ["a", "b"]

    def test_empty_placeholders(self):
        assert get_input_fields([], {"a": "x"}) == []

    def test_preserves_order(self):
        assert get_input_fields(["z", "a", "m"], {}) == ["z", "a", "m"]


# ------------------------------------------------------------------
# TestRenderTemplate
# ------------------------------------------------------------------

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

    def test_no_placeholders(self):
        result = render_template("plain text", {})
        assert result == "plain text"

    def test_empty_content(self):
        result = render_template("", {"x": "1"})
        assert result == ""

    def test_repeated_placeholder(self):
        result = render_template("{{x}} and {{x}}", {"x": "val"})
        assert result == "val and val"

    def test_special_chars_in_value(self):
        result = render_template("{{x}}", {"x": "a < b > c & d"})
        assert result == "a < b > c & d"

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


# ------------------------------------------------------------------
# End-to-end integration tests
# ------------------------------------------------------------------

class TestEndToEnd:
    """Full pipeline: extract -> resolve -> get_input -> render."""

    def test_all_auto_fields(self, group_result):
        content = "Corretor {{susep}} tem {{count}} registro(s). Status: {{status}}."
        fields = {
            "susep": "query:ASD_CORRETOR:SUSEP",
            "count": "query:ASD_CORRETOR:_count",
            "status": "query:ASD_CORRETOR:_status",
        }

        placeholders = extract_placeholders(content)
        assert placeholders == ["susep", "count", "status"]

        resolved = resolve_auto_fields(group_result, {}, fields)
        input_fields = get_input_fields(placeholders, resolved)
        assert input_fields == []

        result = render_template(content, resolved)
        assert result == "Corretor 00000202098947 tem 1 registro(s). Status: OK."

    def test_mixed_auto_and_input(self, group_result):
        content = "{{titulo}}\n{{fonte}}: {{count}} registros"
        fields = {
            "fonte": "query:VW_ESTRUTURA:_name",
            "count": "query:VW_ESTRUTURA:_count",
        }

        placeholders = extract_placeholders(content)
        resolved = resolve_auto_fields(group_result, {}, fields)
        input_fields = get_input_fields(placeholders, resolved)
        assert input_fields == ["titulo"]

        # Simulate user filling the input
        all_values = {**resolved, "titulo": "Minha Investigacao"}
        result = render_template(content, all_values)
        assert result == "Minha Investigacao\nVW_ESTRUTURA: 0 registros"

    def test_params_in_template(self, group_result):
        content = "Corretor {{cod}} (SUSEP {{susep}})"
        fields = {
            "cod": "param:CORRETOR",
            "susep": "query:ASD_CORRETOR:SUSEP",
        }
        params = {"CORRETOR": "108866"}

        placeholders = extract_placeholders(content)
        resolved = resolve_auto_fields(group_result, params, fields)
        result = render_template(content, resolved)
        assert result == "Corretor 108866 (SUSEP 00000202098947)"

    def test_multi_row_template(self, multi_row_result):
        content = (
            "REGISTROS ({{total}}):\n"
            "1. {{nome1}} - {{status1}}\n"
            "2. {{nome2}} - {{status2}}\n"
        )
        fields = {
            "total": "query:REGISTROS:_count",
            "nome1": "query:REGISTROS:NOME:0",
            "status1": "query:REGISTROS:STATUS:0",
            "nome2": "query:REGISTROS:NOME:1",
            "status2": "query:REGISTROS:STATUS:1",
        }

        resolved = resolve_auto_fields(multi_row_result, {}, fields)
        result = render_template(content, resolved)
        assert "REGISTROS (3):" in result
        assert "1. Alice - ativo" in result
        assert "2. Bob - inativo" in result

    def test_full_investigation_template(self, group_result):
        """Simulates the real-world investigation template from the user example."""
        content = (
            "INVESTIGACAO - {{titulo}}\n\n"
            "ANALISE: {{analise}}\n\n"
            "ENTIDADES: CD_INTERNO_CORRETOR {{cod}}, SUSEP {{susep}}\n\n"
            "ETAPAS:\n"
            "- ({{etapa1_nome}}): Corretor existe com SUSEP {{susep}}, TP_DOCUMENTO {{tp_doc}}. {{etapa1_verdict}}.\n"
            "- ({{etapa2_nome}}): {{etapa2_count_label}}. {{etapa2_verdict}}.\n"
        )
        fields = {
            "cod": "param:CORRETOR",
            "susep": "query:ASD_CORRETOR:SUSEP",
            "tp_doc": "query:ASD_CORRETOR:TP_DOCUMENTO",
            "etapa1_nome": "query:ASD_CORRETOR:_name",
            "etapa1_verdict": "literal:OK",
            "etapa2_nome": "query:VW_ESTRUTURA:_name",
            "etapa2_count_label": "query:VW_ESTRUTURA:_count_label",
            "etapa2_verdict": "literal:PROBLEMA IDENTIFICADO",
            # these are manual input fields (not in fields dict)
        }
        params = {"CORRETOR": "108866"}

        placeholders = extract_placeholders(content)
        resolved = resolve_auto_fields(group_result, params, fields)

        input_fields = get_input_fields(placeholders, resolved)
        assert "titulo" in input_fields
        assert "analise" in input_fields

        all_values = {
            **resolved,
            "titulo": "CONSULTA APOLICE",
            "analise": "Corretora AMO nao consegue cotar seguro automovel",
        }
        result = render_template(content, all_values)

        assert "INVESTIGACAO - CONSULTA APOLICE" in result
        assert "CD_INTERNO_CORRETOR 108866" in result
        assert "SUSEP 00000202098947" in result
        assert "TP_DOCUMENTO CGC" in result
        assert "(ASD_CORRETOR):" in result
        assert "OK." in result
        assert "(VW_ESTRUTURA):" in result
        assert "0 registros" in result
        assert "PROBLEMA IDENTIFICADO." in result
