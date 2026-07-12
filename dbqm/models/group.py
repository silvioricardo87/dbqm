from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from dbqm.core.paths import CONFIG_DIR, GROUPS_FILE


@dataclass
class Group:
    name: str
    description: str
    queries: list[str]
    join_key: str
    compare_columns: list[str] = field(default_factory=list)
    shared_params: dict = field(default_factory=dict)
    column_mapping: dict = field(default_factory=dict)
    normalize: dict = field(default_factory=dict)
    validation_rule: str = "all_equal"
    folder: str = ""
    template: str = ""  # template name (empty = no template)
    template_fields: dict = field(default_factory=dict)  # {field_name: source_expression}
    # Ad-hoc (Multi-Exec) groups: run one SQL across a set of connections.
    adhoc_sql: str = ""  # non-empty marks this as an ad-hoc group
    connections: list[str] = field(default_factory=list)  # connection names
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Group:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            queries=data.get("queries", []),
            join_key=data.get("join_key", ""),
            compare_columns=data.get("compare_columns", []),
            shared_params=data.get("shared_params", {}),
            column_mapping=data.get("column_mapping", {}),
            normalize=data.get("normalize", {}),
            validation_rule=data.get("validation_rule", "all_equal"),
            folder=data.get("folder", ""),
            template=data.get("template", ""),
            template_fields=data.get("template_fields", {}),
            adhoc_sql=data.get("adhoc_sql", ""),
            connections=data.get("connections", []),
            created_at=data.get("created_at", datetime.now().isoformat(timespec="seconds")),
        )


def load_groups() -> list[Group]:
    if not GROUPS_FILE.exists():
        return []
    data = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    return [Group.from_dict(g) for g in data.get("groups", [])]


def save_groups(groups: list[Group]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"groups": [g.to_dict() for g in groups]}
    GROUPS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_group(name: str) -> Optional[Group]:
    for g in load_groups():
        if g.name == name:
            return g
    return None


def delete_group(name: str) -> bool:
    groups = load_groups()
    new_groups = [g for g in groups if g.name != name]
    if len(new_groups) == len(groups):
        return False
    save_groups(new_groups)
    return True
