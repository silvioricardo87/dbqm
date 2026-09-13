"""Every core dataclass that reaches an output must say its own wire shape.

The alternative was a serialiser in the CLI knowing fifteen classes' internals,
where a field added to `core/` goes missing from the JSON with no test noticing.
"""
from __future__ import annotations

import dataclasses
import importlib
import json

import pytest

MODULOS = [
    "dbqm.core.object_browser",
    "dbqm.core.table_browser",
    "dbqm.core.query_engine",
    "dbqm.core.group_engine",
]


def _dataclasses_publicas():
    for nome in MODULOS:
        mod = importlib.import_module(nome)
        for attr in vars(mod).values():
            if (
                dataclasses.is_dataclass(attr)
                and isinstance(attr, type)
                and attr.__module__ == nome
            ):
                yield nome, attr


class TestInventory:
    def test_every_core_dataclass_has_to_dict(self):
        """A guard, in the style of tests/design: the next one is born with it."""
        faltando = [
            f"{mod}.{cls.__name__}"
            for mod, cls in _dataclasses_publicas()
            if not callable(getattr(cls, "to_dict", None))
        ]
        assert not faltando, (
            "these reach a CLI output and cannot serialise themselves: "
            f"{faltando}"
        )

    def test_there_are_fifteen_of_them(self):
        """Pins the count so a new class is a deliberate decision, not a drift."""
        assert len(list(_dataclasses_publicas())) == 15

    def test_no_dataclass_emits_a_password(self):
        """The rule: to_dict never emits a secret. `connection show` redacts
        precisely because serialisation is chosen, not automatic."""
        for _, cls in _dataclasses_publicas():
            campos = {f.name for f in dataclasses.fields(cls)}
            assert "password" not in campos, (
                f"{cls.__name__} has a password field; its to_dict must redact "
                "it and this test must be updated to say so"
            )


class TestShapes:
    def test_table_structure_round_trips_through_json(self):
        from dbqm.core.object_browser import ColumnInfo, IndexInfo, TableStructure

        estrutura = TableStructure(
            table="PEDIDOS",
            columns=[ColumnInfo(
                name="ID", data_type="NUMBER", data_length=None,
                data_precision=10, data_scale=0, nullable=False, is_pk=True,
            )],
            indexes=[IndexInfo(name="PK_PEDIDOS", columns=["ID"], is_unique=True)],
        )
        d = estrutura.to_dict()
        assert d["table"] == "PEDIDOS"
        assert d["columns"][0]["name"] == "ID"
        assert d["indexes"][0]["is_unique"] is True
        json.dumps(d)  # must not raise

    def test_view_info_carries_its_definition(self):
        from dbqm.core.object_browser import ViewInfo

        v = ViewInfo(name="V_PEDIDOS", owner="APP", sql_definition="SELECT 1 FROM DUAL")
        d = v.to_dict()
        assert d == {
            "name": "V_PEDIDOS",
            "owner": "APP",
            "sql_definition": "SELECT 1 FROM DUAL",
        }
        json.dumps(d)

    def test_routine_info_nests_its_params(self):
        from dbqm.core.object_browser import RoutineInfo, RoutineParam

        r = RoutineInfo(
            name="CALC_TOTAL",
            routine_type="FUNCTION",
            params=[RoutineParam(name="P1", data_type="NUMBER", direction="IN")],
            return_type="NUMBER",
        )
        d = r.to_dict()
        assert d["name"] == "CALC_TOTAL"
        assert d["params"][0] == {
            "name": "P1", "data_type": "NUMBER", "direction": "IN", "default": "",
        }
        json.dumps(d)

    def test_package_info_nests_its_routines(self):
        from dbqm.core.object_browser import PackageInfo, RoutineInfo

        p = PackageInfo(
            name="PKG_PEDIDOS",
            owner="APP",
            routines=[RoutineInfo(name="PROC1", routine_type="PROCEDURE")],
        )
        d = p.to_dict()
        assert d["name"] == "PKG_PEDIDOS"
        assert d["routines"][0]["name"] == "PROC1"
        json.dumps(d)

    def test_browse_result_carries_its_rows(self):
        from dbqm.core.table_browser import BrowseResult

        b = BrowseResult(
            table="PEDIDOS", connection_name="c", columns=["id"],
            rows=[[1]], row_count=1, total_count=1, elapsed=0.1,
            limit=100, offset=0,
        )
        d = b.to_dict()
        assert d["table"] == "PEDIDOS"
        assert d["rows"] == [[1]]
        assert d["fk_columns"] == []
        json.dumps(d, default=str)

    def test_query_result_carries_its_rows(self):
        from dbqm.core.query_engine import QueryResult

        r = QueryResult(query_name="q", connection_name="c", columns=["a"],
                        rows=[[1]], row_count=1, elapsed=0.1)
        d = r.to_dict()
        assert d["columns"] == ["a"]
        assert d["rows"] == [[1]]
        json.dumps(d, default=str)

    def test_adhoc_result_carries_its_output_lines(self):
        from dbqm.core.query_engine import AdhocResult

        a = AdhocResult(
            sql_type="SELECT", connection_name="c", db_type="oracle",
            columns=["a"], rows=[[1]], row_count=1,
            output_lines=["linha 1"],
        )
        d = a.to_dict()
        assert d["sql_type"] == "SELECT"
        assert d["output_lines"] == ["linha 1"]
        json.dumps(d, default=str)

    def test_group_result_nests_query_results_and_comparisons(self):
        from dbqm.core.group_engine import ComparisonResult, ComparisonRow, GroupResult
        from dbqm.core.query_engine import QueryResult

        qr = QueryResult(query_name="q1", connection_name="c", columns=["id"],
                          rows=[[1]], row_count=1, elapsed=0.1)
        comp = ComparisonResult(
            column="id",
            rows=[ComparisonRow(key_value=1, values={"q1": 1}, status="OK")],
            total_keys=1, equal_count=1, diff_count=0, absent_count=0,
            normalized_count=0,
        )
        g = GroupResult(
            group_name="g1", query_results={"q1": qr}, comparisons=[comp],
            all_match=True, summary_lines=["ok"],
        )
        d = g.to_dict()
        assert d["group_name"] == "g1"
        assert d["query_results"]["q1"]["columns"] == ["id"]
        assert d["comparisons"][0]["rows"][0]["status"] == "OK"
        json.dumps(d, default=str)
