"""Export and import DBQM configurations (connections, queries, groups)."""
from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

from dbqm.core.crypto import (
    decrypt,
    encrypt,
    encrypt_with_password,
    decrypt_with_password,
    generate_salt,
)
from dbqm.models.connection import Connection, load_connections, save_connections
from dbqm.models.query import Query, load_queries, save_queries
from dbqm.models.group import Group, load_groups, save_groups
from dbqm.core.constants import EXPORTS_DIR
BUNDLE_VERSION = 1


def export_configs(
    password: str,
    include_connections: bool = True,
    include_queries: bool = True,
    include_groups: bool = True,
) -> str:
    """Export selected configs to a .dbqm bundle file. Returns the file path."""
    salt = generate_salt()
    bundle: dict = {
        "version": BUNDLE_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "salt": base64.b64encode(salt).decode(),
    }

    if include_connections:
        conns = load_connections()
        conn_dicts = []
        for c in conns:
            d = c.to_dict()
            plain_pw = decrypt(c.password)
            d["password"] = encrypt_with_password(plain_pw, password, salt)
            conn_dicts.append(d)
        bundle["connections"] = conn_dicts

    if include_queries:
        bundle["queries"] = [q.to_dict() for q in load_queries()]

    if include_groups:
        bundle["groups"] = [g.to_dict() for g in load_groups()]

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = EXPORTS_DIR / f"dbqm_config_{ts}.dbqm"
    filepath.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(filepath)


def import_configs(filepath: str, password: str) -> dict:
    """Import configs from a .dbqm bundle file. Returns summary dict.

    Duplicates (by name) are silently skipped.
    """
    data = json.loads(Path(filepath).read_text(encoding="utf-8"))
    salt = base64.b64decode(data["salt"])

    summary = {"connections": 0, "queries": 0, "groups": 0, "skipped": 0}

    # Connections
    if "connections" in data:
        existing = load_connections()
        existing_names = {c.name for c in existing}
        for cd in data["connections"]:
            if cd["name"] in existing_names:
                summary["skipped"] += 1
                continue
            plain_pw = decrypt_with_password(cd["password"], password, salt)
            cd["password"] = encrypt(plain_pw)
            existing.append(Connection.from_dict(cd))
            summary["connections"] += 1
        save_connections(existing)

    # Queries
    if "queries" in data:
        existing = load_queries()
        existing_names = {q.name for q in existing}
        for qd in data["queries"]:
            if qd["name"] in existing_names:
                summary["skipped"] += 1
                continue
            existing.append(Query.from_dict(qd))
            summary["queries"] += 1
        save_queries(existing)

    # Groups
    if "groups" in data:
        existing = load_groups()
        existing_names = {g.name for g in existing}
        for gd in data["groups"]:
            if gd["name"] in existing_names:
                summary["skipped"] += 1
                continue
            existing.append(Group.from_dict(gd))
            summary["groups"] += 1
        save_groups(existing)

    return summary
