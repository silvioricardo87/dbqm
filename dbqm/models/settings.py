"""Application settings with JSON persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

from dbqm.core.paths import CONFIG_DIR, SETTINGS_FILE


@dataclass
class Settings:
    audit_log_enabled: bool = False
    theme: str = "plano-escuro"
    # The language every user-facing string is rendered in. English is the
    # source language; `DBQM_LANG` overrides this for one run without
    # writing to the file. See `dbqm/i18n/__init__.py`.
    language: str = "en"
    # Export configuration
    default_export_dir: str = ""  # empty = use current working directory
    export_dir_prompted: bool = False  # has the user been asked about the dir?
    create_export_subdirs: bool = True  # create category subdirs for groups/DDL/SQL (queries are always flat)
    # Oracle Instant Client directory. Empty = auto-detect (see core.db_manager).
    # Takes precedence over ORACLE_HOME so a 32-bit client installed by another
    # tool (e.g. PL/SQL Developer) cannot hijack the 64-bit client dbqm needs.
    oracle_client_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        """Read whatever fields this class declares, defaults and all.

        Was a hand-written argument per field, which meant a field added to
        the class was written to the file by `to_dict` and silently dropped
        on the way back -- `language` landed that way and the setting simply
        did not take. `Connection.from_dict` has always derived the list;
        this one does too now. Unknown keys are ignored, so a settings file
        written by a newer dbqm still loads on an older one.
        """
        campos = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in campos})


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
