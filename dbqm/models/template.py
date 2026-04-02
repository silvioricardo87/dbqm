"""Template model for grouped query report formatting."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from dbqm.core.paths import TEMPLATES_DIR, TEMPLATES_FILE


@dataclass
class Template:
    name: str
    description: str
    content: str  # Template text with {{field}} placeholders
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Template:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            content=data.get("content", ""),
            created_at=data.get("created_at", datetime.now().isoformat(timespec="seconds")),
        )


def load_templates() -> list[Template]:
    if not TEMPLATES_FILE.exists():
        return []
    data = json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
    return [Template.from_dict(t) for t in data.get("templates", [])]


def save_templates(templates: list[Template]) -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    data = {"templates": [t.to_dict() for t in templates]}
    TEMPLATES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_template(name: str) -> Optional[Template]:
    for t in load_templates():
        if t.name == name:
            return t
    return None


def delete_template(name: str) -> bool:
    templates = load_templates()
    new_templates = [t for t in templates if t.name != name]
    if len(new_templates) == len(templates):
        return False
    save_templates(new_templates)
    return True
