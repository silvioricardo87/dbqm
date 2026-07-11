"""Tests for group model."""
from dbqm.models.group import Group, load_groups, save_groups, find_group, delete_group


class TestGroup:
    def test_round_trip(self):
        g = Group(name="g1", description="test", queries=["q1", "q2"], join_key="id",
                  compare_columns=["status"], normalize={"status": {"paga": "pago"}})
        g2 = Group.from_dict(g.to_dict())
        assert g2.name == "g1"
        assert g2.queries == ["q1", "q2"]
        assert g2.normalize == {"status": {"paga": "pago"}}

    def test_defaults(self):
        g = Group.from_dict({"name": "g", "description": "", "queries": [], "join_key": "id"})
        assert g.validation_rule == "all_equal"
        assert g.folder == ""
        assert g.template == ""
        assert g.template_fields == {}

    def test_template_round_trip(self):
        g = Group(
            name="g_tpl", description="with template", queries=["q1", "q2"],
            join_key="id", template="investigacao",
            template_fields={
                "titulo": "param:CORRETOR",
                "count": "query:q1:_count",
                "analise": "",
            },
        )
        d = g.to_dict()
        assert d["template"] == "investigacao"
        assert d["template_fields"]["titulo"] == "param:CORRETOR"
        assert d["template_fields"]["analise"] == ""

        g2 = Group.from_dict(d)
        assert g2.template == "investigacao"
        assert g2.template_fields == {
            "titulo": "param:CORRETOR",
            "count": "query:q1:_count",
            "analise": "",
        }

    def test_template_defaults_from_old_data(self):
        """Groups saved before template feature should load with empty defaults."""
        data = {"name": "old", "description": "", "queries": ["q1", "q2"], "join_key": "id"}
        g = Group.from_dict(data)
        assert g.template == ""
        assert g.template_fields == {}

    def test_adhoc_round_trip(self):
        """Ad-hoc (Multi-Exec) groups round-trip adhoc_sql + connections."""
        g = Group(
            name="multi", description="", queries=[], join_key="ID",
            adhoc_sql="SELECT ID, STATUS FROM t",
            connections=["conn_a", "conn_b", "conn_c"],
        )
        d = g.to_dict()
        assert d["adhoc_sql"] == "SELECT ID, STATUS FROM t"
        assert d["connections"] == ["conn_a", "conn_b", "conn_c"]

        g2 = Group.from_dict(d)
        assert g2.adhoc_sql == "SELECT ID, STATUS FROM t"
        assert g2.connections == ["conn_a", "conn_b", "conn_c"]

    def test_adhoc_defaults_from_old_data(self):
        """Groups saved before the ad-hoc feature load with empty defaults."""
        data = {"name": "old", "description": "", "queries": ["q1", "q2"], "join_key": "id"}
        g = Group.from_dict(data)
        assert g.adhoc_sql == ""
        assert g.connections == []


class TestGroupPersistence:
    def test_save_load_find_delete(self, tmp_config_dir):
        save_groups([Group(name="g1", description="d", queries=["q1"], join_key="k")])
        assert len(load_groups()) == 1
        assert find_group("g1") is not None
        assert delete_group("g1") is True
        assert load_groups() == []

    def test_save_load_with_template(self, tmp_config_dir):
        g = Group(
            name="g_tpl", description="d", queries=["q1", "q2"], join_key="id",
            template="meu_template",
            template_fields={"campo1": "param:X", "campo2": "query:q1:COL"},
        )
        save_groups([g])
        loaded = load_groups()
        assert len(loaded) == 1
        assert loaded[0].template == "meu_template"
        assert loaded[0].template_fields == {"campo1": "param:X", "campo2": "query:q1:COL"}
