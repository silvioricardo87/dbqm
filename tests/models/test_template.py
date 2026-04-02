"""Tests for template model."""
from dbqm.models.template import Template, load_templates, save_templates, find_template, delete_template


class TestTemplate:
    def test_round_trip(self):
        t = Template(name="tpl1", description="desc", content="Hello {{name}}")
        t2 = Template.from_dict(t.to_dict())
        assert t2.name == "tpl1"
        assert t2.description == "desc"
        assert t2.content == "Hello {{name}}"

    def test_defaults(self):
        t = Template.from_dict({"name": "t", "description": ""})
        assert t.content == ""
        assert t.created_at  # Should have a timestamp


class TestTemplatePersistence:
    def test_save_load_find_delete(self, tmp_config_dir):
        save_templates([Template(name="tpl1", description="d", content="{{x}}")])
        assert len(load_templates()) == 1
        assert find_template("tpl1") is not None
        assert find_template("nonexistent") is None
        assert delete_template("tpl1") is True
        assert load_templates() == []

    def test_delete_nonexistent(self, tmp_config_dir):
        save_templates([Template(name="tpl1", description="", content="")])
        assert delete_template("nope") is False
        assert len(load_templates()) == 1

    def test_multiple_templates(self, tmp_config_dir):
        templates = [
            Template(name="a", description="first", content="{{x}}"),
            Template(name="b", description="second", content="{{y}}"),
        ]
        save_templates(templates)
        loaded = load_templates()
        assert len(loaded) == 2
        assert {t.name for t in loaded} == {"a", "b"}
