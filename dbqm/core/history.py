"""Execution history persistence."""
from __future__ import annotations

import json
import os
import threading
import time
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


def _read() -> list[HistoryEntry]:
    """The unlocked read. Only for a caller that already holds `_LOCK` --
    `load_history` below is the locked entry point everyone else uses."""
    f = _history_file()
    if not f.exists():
        return []
    if f.stat().st_size > MAX_HISTORY_FILE_SIZE:
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return [HistoryEntry.from_dict(d) for d in data]


def load_history() -> list[HistoryEntry]:
    """Locked like every other access to the file: a concurrent
    `add_history_entry` writing the temp file's replacement must not be
    read mid-swap."""
    with _LOCK:
        return _read()


#: `save_history`'s replace, on Windows, can meet a `PermissionError` while
#: another handle has the destination open -- a `load_history` in another
#: thread mid-read, the TUI, a concurrent CLI invocation. Both are bounded
#: below by how many times to retry and how long to wait between tries.
_REPLACE_ATTEMPTS = 5
_REPLACE_RETRY_SECONDS = 0.02


def save_history(entries: list[HistoryEntry]) -> None:
    """Atomic: write to a sibling temp file, then replace -- a concurrent
    reader never sees a half-written file.

    The temp file's name carries this process's pid so two processes
    racing to save never share one write handle. The final `replace` is
    retried a bounded number of times on `PermissionError` alone -- the
    Windows case above -- and re-raised if it still fails after that."""
    f = _history_file()
    tmp = f.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps([e.to_dict() for e in entries], indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    for attempt in range(1, _REPLACE_ATTEMPTS + 1):
        try:
            tmp.replace(f)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS:
                raise
            time.sleep(_REPLACE_RETRY_SECONDS)


def add_history_entry(entry: HistoryEntry) -> None:
    """Locked across load, insert and save so two concurrent callers cannot
    each load the same list and overwrite the other's entry.

    Calls `_read()`, not `load_history()`: the lock is not reentrant, and
    `load_history()` would deadlock against the lock this function already
    holds."""
    with _LOCK:
        entries = _read()
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
