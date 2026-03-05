"""Application settings with JSON persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from dbqm.core.constants import CONFIG_DIR

SETTINGS_FILE = CONFIG_DIR / "settings.json"


@dataclass
class Settings:
    audit_log_enabled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        return cls(
            audit_log_enabled=data.get("audit_log_enabled", False),
        )


def load_settings() -> Settings:
    if SETTINGS_FILE.exists():
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return Settings.from_dict(data)
    return Settings()


def save_settings(settings: Settings) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(settings.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
