"""Tests for execution history."""
from dbqm.core.history import (
    HistoryEntry, load_history, save_history, add_history_entry,
    clear_history, record_query_execution, record_group_execution,
    MAX_HISTORY,
)


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
