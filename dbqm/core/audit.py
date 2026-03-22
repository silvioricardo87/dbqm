"""Append-only audit log for query executions."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from dbqm.core.paths import CONFIG_DIR, AUDIT_FILE
from dbqm.models.settings import load_settings


def _is_enabled() -> bool:
    return load_settings().audit_log_enabled


def log_execution(
    action: str,
    name: str,
    connection: str = "",
    params: dict | None = None,
    row_count: int = 0,
    success: bool = True,
    error: str = "",
) -> None:
    """Append an audit entry if audit logging is enabled."""
    if not _is_enabled():
        return

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "name": name,
        "connection": connection,
        "params": params or {},
        "row_count": row_count,
        "success": success,
    }
    if error:
        entry["error"] = error[:200]

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    is_new = not AUDIT_FILE.exists()
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    if is_new:
        try:
            AUDIT_FILE.chmod(0o600)
        except OSError:
            pass
