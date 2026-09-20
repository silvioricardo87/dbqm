"""Execution history persistence."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from dbqm.core.paths import HISTORY_DIR
from dbqm.i18n import t

MAX_HISTORY = 100

#: Guards every read-modify-write against the file. The CLI never raced
#: this -- one process per invocation -- but the MCP server runs tools in
#: worker threads, so two `run`/`run_group` calls can interleave.
_LOCK = threading.Lock()


def kind_label(entry_type: str) -> str:
    """The word a reader sees for an entry's type.

    Three surfaces render this field -- the history table in the TUI, the
    detail panel beside it, and `dbqm history -f table` -- and until now
    each spelled it for itself: one said "grupo", the other two printed
    the stored value. The value on disk and in `-f json` stays English,
    because that is what a caller parses; only the word on screen moves.
    """
    return t("history.type_group") if entry_type == "group" else t("history.type_query")


@dataclass
class HistoryEntry:
    id: str
    timestamp: str
    entry_type: str  # "query" or "group"
    name: str
    connection: str
    params: dict = field(default_factory=dict)
    row_count: int = 0
    elapsed: float = 0.0
    success: bool = True
    error: str = ""
    all_match: bool | None = None
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> HistoryEntry:
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            entry_type=data.get("entry_type", "query"),
            name=data.get("name", ""),
            connection=data.get("connection", ""),
            params=data.get("params", {}),
            row_count=data.get("row_count", 0),
            elapsed=data.get("elapsed", 0.0),
            success=data.get("success", True),
            error=data.get("error", ""),
            all_match=data.get("all_match"),
            summary=data.get("summary", ""),
        )


def _history_file() -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR / "history.json"


MAX_HISTORY_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def load_history() -> list[HistoryEntry]:
    f = _history_file()
    if not f.exists():
        return []
    if f.stat().st_size > MAX_HISTORY_FILE_SIZE:
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return [HistoryEntry.from_dict(d) for d in data]


def save_history(entries: list[HistoryEntry]) -> None:
    """Atomic: write to a sibling temp file, then replace -- a concurrent
    reader never sees a half-written file."""
    f = _history_file()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(
        json.dumps([e.to_dict() for e in entries], indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    tmp.replace(f)


def add_history_entry(entry: HistoryEntry) -> None:
    """Locked across load, insert and save so two concurrent callers cannot
    each load the same list and overwrite the other's entry."""
    with _LOCK:
        entries = load_history()
        entries.insert(0, entry)
        if len(entries) > MAX_HISTORY:
            entries = entries[:MAX_HISTORY]
        save_history(entries)


def clear_history() -> None:
    """Locked for the same reason `add_history_entry` is."""
    with _LOCK:
        save_history([])


def _generate_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")[:18]


def record_query_execution(
    query_name: str,
    connection_name: str,
    params: dict,
    row_count: int,
    elapsed: float,
    success: bool,
    error: str = "",
) -> None:
    entry = HistoryEntry(
        id=_generate_id(),
        timestamp=datetime.now().isoformat(timespec="seconds"),
        entry_type="query",
        name=query_name,
        connection=connection_name,
        params=params,
        row_count=row_count,
        elapsed=elapsed,
        success=success,
        error=error,
    )
    add_history_entry(entry)


def record_group_execution(
    group_name: str,
    params: dict,
    all_match: bool,
    summary: str,
    elapsed: float,
) -> None:
    entry = HistoryEntry(
        id=_generate_id(),
        timestamp=datetime.now().isoformat(timespec="seconds"),
        entry_type="group",
        name=group_name,
        connection="",
        params=params,
        all_match=all_match,
        summary=summary,
        elapsed=elapsed,
        success=True,
    )
    add_history_entry(entry)
