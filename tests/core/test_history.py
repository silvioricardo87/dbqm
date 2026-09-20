"""Tests for execution history."""
import threading

import pytest

from dbqm.core.history import (
    HistoryEntry, load_history, save_history, add_history_entry,
    clear_history, record_query_execution, record_group_execution,
    kind_label, MAX_HISTORY, _history_file,
)
from dbqm.i18n import available_languages, get_language, set_language


@pytest.fixture
def in_each_language():
    """Run the body once per language, restoring the one in force."""
    previous = get_language()
    yield available_languages()
    set_language(previous)


class TestKindLabel:
    def test_the_word_changes_with_the_language(self, in_each_language):
        """The three surfaces that show this field now share one spelling.

        Before, the TUI table said "grupo", the detail panel beside it
        printed the stored "group", and so did `dbqm history -f table` --
        one field, two languages, in the same screen.
        """
        seen = set()
        for language in in_each_language:
            set_language(language)
            seen.add((kind_label("group"), kind_label("query")))
        assert len(seen) == len(in_each_language), (
            f"a language reuses another's words for this field: {seen}")

    def test_the_stored_value_is_not_the_shown_one(self, in_each_language):
        """`-f json` and the file on disk keep English, whatever is on screen.

        A caller parsing `entry_type` must not have to know which language
        the machine that wrote the file was running in.
        """
        for language in in_each_language:
            set_language(language)
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

    def test_save_is_atomic_no_tmp_left_behind(self, tmp_config_dir):
        """`save_history` writes to a sibling `.tmp` then replaces it -- no
        temp file survives, and what is left parses."""
        save_history([HistoryEntry(id="1", timestamp="t", entry_type="query",
                                   name="q", connection="c")])
        f = _history_file()
        assert f.with_suffix(".tmp").exists() is False
        assert load_history()[0].id == "1"

    def test_concurrent_add_entry_loses_nothing(self, tmp_config_dir):
        """The MCP server runs tools in worker threads: twenty concurrent
        `add_history_entry` calls must not interleave into a lost update."""
        threads = [
            threading.Thread(target=add_history_entry, args=(
                HistoryEntry(id=str(i), timestamp="t", entry_type="query",
                            name=f"q{i}", connection="c"),
            ))
            for i in range(20)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        loaded = load_history()
        assert len(loaded) == 20
        assert {e.id for e in loaded} == {str(i) for i in range(20)}
