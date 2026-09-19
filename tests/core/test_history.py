"""Tests for execution history."""
import pytest

from dbqm.core.history import (
    HistoryEntry, load_history, save_history, add_history_entry,
    clear_history, record_query_execution, record_group_execution,
    kind_label, MAX_HISTORY,
)
from dbqm.i18n import available_languages, get_language, set_language


@pytest.fixture
def em_cada_idioma():
    """Run the body once per language, restoring the one in force."""
    anterior = get_language()
    yield available_languages()
    set_language(anterior)


class TestKindLabel:
    def test_the_word_changes_with_the_language(self, em_cada_idioma):
        """The three surfaces that show this field now share one spelling.

        Before, the TUI table said "grupo", the detail panel beside it
        printed the stored "group", and so did `dbqm history -f table` --
        one field, two languages, in the same screen.
        """
        vistos = set()
        for idioma in em_cada_idioma:
            set_language(idioma)
            vistos.add((kind_label("group"), kind_label("query")))
        assert len(vistos) == len(em_cada_idioma), (
            f"a language reuses another's words for this field: {vistos}")

    def test_the_stored_value_is_not_the_shown_one(self, em_cada_idioma):
        """`-f json` and the file on disk keep English, whatever is on screen.

        A caller parsing `entry_type` must not have to know which language
        the machine that wrote the file was running in.
        """
        for idioma in em_cada_idioma:
            set_language(idioma)
            e = HistoryEntry(id="1", timestamp="t", entry_type="group",
                             name="g", connection="c")
            assert e.to_dict()["entry_type"] == "group"

    def test_anything_that_is_not_a_group_reads_as_a_query(self):
        """The field has two values on disk; an older file may have neither."""
        set_language("en")
        assert kind_label("") == kind_label("query")


class TestHistoryEntry:
    def test_round_trip(self):
        e = HistoryEntry(id="1", timestamp="2026-01-01T00:00:00", entry_type="query",
                         name="q1", connection="c1", params={"x": "1"}, row_count=10, elapsed=0.5)
        e2 = HistoryEntry.from_dict(e.to_dict())
        assert e2.id == "1"
        assert e2.name == "q1"
        assert e2.params == {"x": "1"}

    def test_from_dict_defaults(self):
        e = HistoryEntry.from_dict({"id": "1", "timestamp": "t", "name": "n", "connection": "c"})
        assert e.entry_type == "query"
        assert e.success is True
        assert e.all_match is None


class TestHistoryPersistence:
    def test_save_and_load(self, tmp_config_dir):
        entries = [HistoryEntry(id="1", timestamp="t", entry_type="query", name="q", connection="c")]
        save_history(entries)
        loaded = load_history()
        assert len(loaded) == 1
        assert loaded[0].id == "1"

    def test_load_empty(self, tmp_config_dir):
        assert load_history() == []

    def test_add_entry_prepends(self, tmp_config_dir):
        add_history_entry(HistoryEntry(id="1", timestamp="t1", entry_type="query", name="q1", connection="c"))
        add_history_entry(HistoryEntry(id="2", timestamp="t2", entry_type="query", name="q2", connection="c"))
        loaded = load_history()
        assert loaded[0].id == "2"
        assert loaded[1].id == "1"

    def test_max_history_limit(self, tmp_config_dir):
        for i in range(MAX_HISTORY + 10):
            add_history_entry(HistoryEntry(id=str(i), timestamp="t", entry_type="query", name=f"q{i}", connection="c"))
        loaded = load_history()
        assert len(loaded) == MAX_HISTORY

    def test_clear_history(self, tmp_config_dir):
        add_history_entry(HistoryEntry(id="1", timestamp="t", entry_type="query", name="q", connection="c"))
        clear_history()
        assert load_history() == []

    def test_record_query(self, tmp_config_dir):
        record_query_execution("q1", "c1", {"x": "1"}, 10, 0.5, True)
        loaded = load_history()
        assert len(loaded) == 1
        assert loaded[0].entry_type == "query"
        assert loaded[0].name == "q1"

    def test_record_group(self, tmp_config_dir):
        record_group_execution("g1", {}, True, "summary", 1.0)
        loaded = load_history()
        assert loaded[0].entry_type == "group"
        assert loaded[0].all_match is True
