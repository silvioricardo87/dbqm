"""Application settings with JSON persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict

from dbqm.core.paths import CONFIG_DIR, SETTINGS_FILE


@dataclass
class Settings:
    audit_log_enabled: bool = False
    theme: str = "github-dark"
    # Export configuration
    default_export_dir: str = ""  # empty = use current working directory
    export_dir_prompted: bool = False  # has the user been asked about the dir?
    create_export_subdirs: bool = True  # create category subdirs for groups/DDL/SQL (queries are always flat)
    # Oracle Instant Client directory. Empty = auto-detect (see core.db_manager).
    # Takes precedence over ORACLE_HOME so a 32-bit client installed by another
    # tool (e.g. PL/SQL Developer) cannot hijack the 64-bit client dbqm needs.
    oracle_client_dir: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        return cls(
            audit_log_enabled=data.get("audit_log_enabled", False),
            theme=data.get("theme", "github-dark"),
            default_export_dir=data.get("default_export_dir", ""),
            export_dir_prompted=data.get("export_dir_prompted", False),
            create_export_subdirs=data.get("create_export_subdirs", True),
            oracle_client_dir=data.get("oracle_client_dir", ""),
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
