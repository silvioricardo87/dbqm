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


class TestGroupPersistence:
    def test_save_load_find_delete(self, tmp_config_dir):
        save_groups([Group(name="g1", description="d", queries=["q1"], join_key="k")])
        assert len(load_groups()) == 1
        assert find_group("g1") is not None
        assert delete_group("g1") is True
        assert load_groups() == []
