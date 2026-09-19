"""Every core dataclass that reaches an output must say its own wire shape.

The alternative was a serialiser in the CLI knowing every class's internals,
where a field added to `core/` goes missing from the JSON with no test noticing.

The inventory walks every module under `dbqm.core`, not a hand-picked list —
a hardcoded module list is invisible to a dataclass born in a module nobody
remembered to add, which is exactly the drift this guard exists to catch.
"""
from __future__ import annotations

import dataclasses
import importlib
import json
import pkgutil

import dbqm.core

# Dataclasses that live in `dbqm.core` but never reach a CLI json envelope —
# excluded by name, with a reason, rather than by narrowing the module walk
# back down to a list someone has to remember to update.
EXCLUDED = {
    # Oracle Instant Client catalog/installation metadata: consumed only by
    # the Textual UI (dbqm/ui/screens/oracle_clients.py), never serialised
    # to a CLI json envelope.
    "dbqm.core.oracle_client_installer.ClientPackage",
    "dbqm.core.oracle_client_installer.InstalledClient",
}


def _core_modules():
    for modinfo in pkgutil.iter_modules(dbqm.core.__path__, prefix="dbqm.core."):
        if not modinfo.ispkg:
            yield modinfo.name


def _public_dataclasses():
    for name in _core_modules():
        mod = importlib.import_module(name)
        for attr in vars(mod).values():
            if (
                dataclasses.is_dataclass(attr)
                and isinstance(attr, type)
                and attr.__module__ == name
                and f"{name}.{attr.__name__}" not in EXCLUDED
            ):
                yield name, attr


class TestInventory:
    def test_every_core_dataclass_has_to_dict(self):
        """A guard, in the style of tests/design: the next one is born with it."""
        missing_ones = [
            f"{mod}.{cls.__name__}"
            for mod, cls in _public_dataclasses()
            if not callable(getattr(cls, "to_dict", None))
        ]
        assert not missing_ones, (
            "these reach a CLI output and cannot serialise themselves: "
            f"{missing_ones}"
        )

    def test_there_are_nineteen_of_them(self):
        """Pins the count so a new class (or a new exclusion) is a
        deliberate decision, not a drift. 15 from object_browser/
        table_browser/query_engine/group_engine, 3 from ddl_extractor
        (ExtractedObject, ExtractionResult, RoutineExtractionResult), 1 from
        history (HistoryEntry) — 2 more (ClientPackage, InstalledClient) are
        named in EXCLUDED, not counted here."""
        assert len(list(_public_dataclasses())) == 19

    def test_no_dataclass_emits_a_password(self):
        """The rule: to_dict never emits a secret. `connection show` redacts
        precisely because serialisation is chosen, not automatic."""
        for _, cls in _public_dataclasses():
            fields = {f.name for f in dataclasses.fields(cls)}
            assert "password" not in fields, (
                f"{cls.__name__} has a password field; its to_dict must redact "
                "it and this test must be updated to say so"
            )


class TestShapes:
    def test_table_structure_round_trips_through_json(self):
        from dbqm.core.object_browser import ColumnInfo, IndexInfo, TableStructure

        structure = TableStructure(
            table="ORDERS",
            columns=[ColumnInfo(
                name="ID", data_type="NUMBER", data_length=None,
                data_precision=10, data_scale=0, nullable=False, is_pk=True,
            )],
            indexes=[IndexInfo(name="PK_PEDIDOS", columns=["ID"], is_unique=True)],
        )
        d = structure.to_dict()
        assert d["table"] == "ORDERS"
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
            table="ORDERS", connection_name="c", columns=["id"],
            rows=[[1]], row_count=1, total_count=1, elapsed=0.1,
            limit=100, offset=0,
        )
        d = b.to_dict()
        assert d["table"] == "ORDERS"
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

    def test_adhoc_result_carries_its_sql_and_output_lines(self):
        from dbqm.core.query_engine import AdhocResult

        a = AdhocResult(
            sql_type="SELECT", connection_name="c", sql="SELECT 1", db_type="oracle",
            columns=["a"], rows=[[1]], row_count=1,
            output_lines=["linha 1"],
        )
        d = a.to_dict()
        assert d["sql_type"] == "SELECT"
        assert d["sql"] == "SELECT 1"
        assert d["output_lines"] == ["linha 1"]
        json.dumps(d, default=str)

    def test_group_result_nests_query_results_and_comparisons(self):
        """`summary_lines` is Portuguese display prose derived from the same
        counts `comparisons[*].*_count` already carries — it must not appear
        in the wire shape (rule 2: data, not presentation)."""
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
        assert "summary_lines" not in d
        json.dumps(d, default=str)

    def test_extraction_result_nests_its_objects(self):
        from dbqm.core.ddl_extractor import ExtractedObject, ExtractionResult

        r = ExtractionResult(
            object_name="PKG_PEDIDOS", object_type="PACKAGE", owner="APP",
            connection_name="c",
            objects=[ExtractedObject(name="PKG_PEDIDOS", obj_type="PACKAGE", ddl="CREATE ...")],
        )
        d = r.to_dict()
        assert d["object_name"] == "PKG_PEDIDOS"
        assert d["objects"][0] == {
            "name": "PKG_PEDIDOS", "obj_type": "PACKAGE", "ddl": "CREATE ...",
        }
        json.dumps(d)
