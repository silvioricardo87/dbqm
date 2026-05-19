from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from dbqm.core.paths import CONFIG_DIR, CONNECTIONS_FILE


@dataclass
class Connection:
    name: str
    db_type: str  # "oracle", "sqlserver", "postgresql", "mysql"
    user: str
    password: str  # encrypted
    # Oracle
    mode: Optional[str] = None  # "tns" or "direct"
    tns_path: Optional[str] = None
    tns_name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    service_name: Optional[str] = None
    # SQL Server
    database: Optional[str] = None
    windows_auth: bool = False
    # Free-form notes about this connection (purpose, schema, contacts, etc.)
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> Connection:
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def display_target(self) -> str:
        if self.db_type == "oracle":
            if self.mode == "tns":
                return self.tns_name or ""
            return f"{self.host}:{self.port}/{self.service_name}"
        if self.db_type in ("sqlserver", "postgresql", "mysql"):
            target = self.host or ""
            if self.port:
                target += f":{self.port}"
            if self.database:
                target += f"/{self.database}"
            return target
        return self.host or ""


def load_connections() -> list[Connection]:
    if not CONNECTIONS_FILE.exists():
        return []
    data = json.loads(CONNECTIONS_FILE.read_text(encoding="utf-8"))
    return [Connection.from_dict(c) for c in data.get("connections", [])]


def save_connections(connections: list[Connection]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"connections": [c.to_dict() for c in connections]}
    CONNECTIONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_connection(name: str) -> Optional[Connection]:
    for c in load_connections():
        if c.name == name:
            return c
    return None


def delete_connection(name: str) -> bool:
    conns = load_connections()
    new_conns = [c for c in conns if c.name != name]
    if len(new_conns) == len(conns):
        return False
    save_connections(new_conns)
    return True
