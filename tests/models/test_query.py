"""Tests for query model."""
from dbqm.models.query import (
    Query, QueryParam, load_queries, save_queries, find_query, delete_query,
    filter_queries,
)


class TestQueryParam:
    def test_round_trip(self):
        p = QueryParam(name="id", description="The ID", default="123")
        p2 = QueryParam.from_dict(p.to_dict())
        assert p2.name == "id"
        assert p2.description == "The ID"
        assert p2.default == "123"


class TestQuery:
    def test_to_dict_from_dict(self):
        q = Query(name="q1", connection="c1", sql="SELECT 1", table="t", params=[QueryParam("id")])
        d = q.to_dict()
        q2 = Query.from_dict(d)
        assert q2.name == "q1"
        assert q2.sql == "SELECT 1"
        assert len(q2.params) == 1
        assert q2.params[0].name == "id"

    def test_apply_column_maps_no_maps(self):
        q = Query(name="q", connection="c", sql="SELECT 1")
        rows = [[1, "a"], [2, "b"]]
        result = q.apply_column_maps(rows, ["id", "name"])
        assert result == [[1, "a"], [2, "b"]]

    def test_apply_column_maps(self):
        q = Query(name="q", connection="c", sql="SELECT 1",
                  column_maps={"status": {"1": "active", "0": "inactive"}})
        rows = [[1, "1"], [2, "0"], [3, "2"]]
        result = q.apply_column_maps(rows, ["id", "status"])
        assert result[0][1] == "active"
        assert result[1][1] == "inactive"
        assert result[2][1] == "2"  # unmapped stays


class TestFilterQueries:
    """filter_queries: text matches name OR description; connection matches
    exactly; all filters AND together and each is optional."""

    def _sample(self):
        return [
            Query(name="Clientes ativos", connection="prod", sql="S",
                  description="lista de clientes ativos"),
            Query(name="Pedidos do dia", connection="prod", sql="S",
                  description="pedidos faturados hoje"),
            Query(name="Estoque", connection="homolog", sql="S",
                  description="saldo de estoque por deposito"),
        ]

    def test_no_filters_returns_all(self):
        qs = self._sample()
        assert filter_queries(qs) == qs

    def test_text_matches_name(self):
        result = filter_queries(self._sample(), text="estoque")
        assert [q.name for q in result] == ["Estoque"]

    def test_text_matches_description(self):
        result = filter_queries(self._sample(), text="faturados")
        assert [q.name for q in result] == ["Pedidos do dia"]

    def test_text_case_insensitive(self):
        result = filter_queries(self._sample(), text="CLIENTES")
        assert [q.name for q in result] == ["Clientes ativos"]

    def test_connection_only(self):
        result = filter_queries(self._sample(), connection="homolog")
        assert [q.name for q in result] == ["Estoque"]

    def test_text_and_connection_combined(self):
        result = filter_queries(self._sample(), text="ativos", connection="prod")
        assert [q.name for q in result] == ["Clientes ativos"]

    def test_text_and_connection_no_match(self):
        # "estoque" only exists on homolog, so prod yields nothing.
        result = filter_queries(self._sample(), text="estoque", connection="prod")
        assert result == []

    def test_blank_connection_ignored(self):
        result = filter_queries(self._sample(), connection="")
        assert len(result) == 3

    def test_whitespace_text_ignored(self):
        result = filter_queries(self._sample(), text="   ")
        assert len(result) == 3

    def test_preserves_input_order(self):
        result = filter_queries(self._sample(), connection="prod")
        assert [q.name for q in result] == ["Clientes ativos", "Pedidos do dia"]


class TestQueryPersistence:
    def test_save_and_load(self, tmp_config_dir):
        queries = [Query(name="q1", connection="c1", sql="SELECT 1")]
        save_queries(queries)
        loaded = load_queries()
        assert len(loaded) == 1
        assert loaded[0].name == "q1"

    def test_find_and_delete(self, tmp_config_dir):
        save_queries([Query(name="q1", connection="c", sql="S")])
        assert find_query("q1") is not None
        assert find_query("nope") is None
        assert delete_query("q1") is True
        assert delete_query("q1") is False
