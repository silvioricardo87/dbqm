from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
QUERIES_FILE = CONFIG_DIR / "queries.json"


@dataclass
class QueryParam:
    name: str
    description: str = ""
    default: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> QueryParam:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            default=data.get("default", ""),
        )


@dataclass
class Query:
    name: str
    connection: str
    sql: str
    table: str = ""
    description: str = ""
    params: list[QueryParam] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    column_maps: dict = field(default_factory=dict)  # {"col": {"raw": "label", ...}}
    order_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    is_favorite: bool = False
    last_executed: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["params"] = [p.to_dict() for p in self.params]
        return d

    def apply_column_maps(self, rows: list[list], columns: list[str]) -> list[list]:
        """Apply column value mappings to result rows in-place and return them."""
        if not self.column_maps:
            return rows
        col_indices = {}
        for col_name, mapping in self.column_maps.items():
            for i, c in enumerate(columns):
                if c == col_name:
                    col_indices[i] = mapping
                    break
        for row in rows:
            for idx, mapping in col_indices.items():
                val = str(row[idx]) if row[idx] is not None else ""
                if val in mapping:
                    row[idx] = mapping[val]
        return rows

    @classmethod
    def from_dict(cls, data: dict) -> Query:
        params = [QueryParam.from_dict(p) for p in data.get("params", [])]
        return cls(
            name=data["name"],
            connection=data["connection"],
            sql=data["sql"],
            table=data.get("table", ""),
            description=data.get("description", ""),
            params=params,
            columns=data.get("columns", []),
            column_maps=data.get("column_maps", {}),
            order_by=data.get("order_by", ""),
            created_at=data.get("created_at", datetime.now().isoformat(timespec="seconds")),
            is_favorite=data.get("is_favorite", False),
            last_executed=data.get("last_executed", ""),
        )


def load_queries() -> list[Query]:
    if not QUERIES_FILE.exists():
        return []
    data = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
    return [Query.from_dict(q) for q in data.get("queries", [])]


def save_queries(queries: list[Query]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"queries": [q.to_dict() for q in queries]}
    QUERIES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_query(name: str) -> Optional[Query]:
    for q in load_queries():
        if q.name == name:
            return q
    return None


def delete_query(name: str) -> bool:
    queries = load_queries()
    new_queries = [q for q in queries if q.name != name]
    if len(new_queries) == len(queries):
        return False
    save_queries(new_queries)
    return True
