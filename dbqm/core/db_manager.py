"""Database connection manager for Oracle, SQL Server, PostgreSQL, and MySQL."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dbqm.core.crypto import decrypt
from dbqm.models.connection import Connection

_thick_mode_initialized = False


def _parse_tns_entry(tns_path: str, tns_name: str) -> dict | None:
    """Parse tnsnames.ora to extract host/port/service for a given TNS name."""
    path = Path(tns_path)
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(
        rf"^\s*{re.escape(tns_name)}\s*=\s*",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        return None
    start = match.end()
    depth = 0
    end = start
    for i, ch in enumerate(content[start:], start):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    block = content[match.start():end]
    host_m = re.search(r"HOST\s*=\s*([^\s)]+)", block, re.IGNORECASE)
    port_m = re.search(r"PORT\s*=\s*(\d+)", block, re.IGNORECASE)
    service_m = re.search(r"SERVICE_NAME\s*=\s*([^\s)]+)", block, re.IGNORECASE)
    sid_m = re.search(r"SID\s*=\s*([^\s)]+)", block, re.IGNORECASE)
    if not host_m:
        return None
    return {
        "host": host_m.group(1),
        "port": int(port_m.group(1)) if port_m else 1521,
        "service_name": service_m.group(1) if service_m else None,
        "sid": sid_m.group(1) if sid_m else None,
    }


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CLIENTS_DIR = PROJECT_ROOT / "clients"


def _find_oracle_client_dir() -> str | None:
    """Auto-detect Oracle Instant Client directory matching Python architecture."""
    import struct
    arch = "x64" if struct.calcsize("P") * 8 == 64 else "x86"
    # 1. Check project's clients/ directory first — prefer matching architecture
    if CLIENTS_DIR.exists():
        candidates = sorted(
            [e for e in CLIENTS_DIR.iterdir() if e.is_dir() and "instantclient" in e.name.lower()],
            key=lambda e: (arch in e.name.lower(), e.name),
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
    # 2. Check ORACLE_HOME env var
    oracle_home = os.environ.get("ORACLE_HOME")
    if oracle_home and Path(oracle_home).exists():
        return oracle_home
    # 3. Search common locations
    search_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")),
        Path("C:/oracle"),
        Path("C:/app/oracle"),
    ]
    for base in search_paths:
        if not base.exists():
            continue
        for entry in base.iterdir():
            if entry.is_dir() and "instantclient" in entry.name.lower():
                return str(entry)
    return None


_thick_mode_error: str | None = None


def _init_thick_mode(config_dir: str | None = None) -> bool:
    """Initialize Oracle thick mode. Returns True if successful."""
    global _thick_mode_initialized, _thick_mode_error
    if _thick_mode_initialized:
        return True
    import oracledb
    try:
        kwargs = {}
        if config_dir:
            kwargs["config_dir"] = config_dir
        lib_dir = _find_oracle_client_dir()
        if lib_dir:
            kwargs["lib_dir"] = lib_dir
        oracledb.init_oracle_client(**kwargs)
        _thick_mode_initialized = True
        _thick_mode_error = None
        return True
    except Exception as e:
        _thick_mode_error = str(e)
        return False


def _needs_thick_mode(error: Exception) -> bool:
    """Check if the error indicates thick mode is required."""
    msg = str(error)
    return "DPY-3015" in msg or "password verifier type" in msg


def get_oracle_connection(conn: Connection) -> Any:
    """Establish Oracle connection. Initializes thick mode eagerly to avoid DPY-3015."""
    import oracledb

    password = decrypt(conn.password)
    config_dir = str(Path(conn.tns_path).parent) if conn.tns_path else None

    if conn.mode == "tns" and conn.tns_name:
        dsn = conn.tns_name
        # Try to parse TNS file to build a direct DSN
        if conn.tns_path:
            tns_info = _parse_tns_entry(conn.tns_path, conn.tns_name)
            if tns_info:
                svc = tns_info.get("service_name") or tns_info.get("sid", "")
                dsn = f"{tns_info['host']}:{tns_info['port']}/{svc}"
    else:
        host = conn.host or "localhost"
        port = conn.port or 1521
        svc = conn.service_name or ""
        dsn = f"{host}:{port}/{svc}"

    # Always try to initialize thick mode eagerly (avoids DPY-3015)
    if not _thick_mode_initialized:
        _init_thick_mode(config_dir)

    try:
        return oracledb.connect(user=conn.user, password=password, dsn=dsn)
    except Exception as err:
        if not _needs_thick_mode(err):
            raise
        # DPY-3015 in thin mode and thick mode was not available
        thick_detail = f"\nErro ao inicializar thick mode: {_thick_mode_error}" if _thick_mode_error else ""
        raise RuntimeError(
            "Thin mode nao suportado por este servidor (DPY-3015). "
            "Instale o Oracle Instant Client e defina ORACLE_HOME para usar thick mode.\n"
            f"Download: https://www.oracle.com/database/technologies/instant-client/downloads.html{thick_detail}"
        ) from err


def get_sqlserver_connection(conn: Connection) -> Any:
    """Establish SQL Server connection."""
    import pymssql

    password = decrypt(conn.password)
    return pymssql.connect(
        server=conn.host or "localhost",
        port=str(conn.port or 1433),
        user=conn.user,
        password=password,
        database=conn.database or "",
    )


def get_postgresql_connection(conn: Connection) -> Any:
    """Establish PostgreSQL connection."""
    import psycopg

    password = decrypt(conn.password)
    return psycopg.connect(
        host=conn.host or "localhost",
        port=conn.port or 5432,
        dbname=conn.database or "",
        user=conn.user,
        password=password,
    )


def get_mysql_connection(conn: Connection) -> Any:
    """Establish MySQL connection."""
    import pymysql

    password = decrypt(conn.password)
    return pymysql.connect(
        host=conn.host or "localhost",
        port=conn.port or 3306,
        database=conn.database or "",
        user=conn.user,
        password=password,
    )


def get_connection(conn: Connection) -> Any:
    """Get a database connection based on connection type."""
    if conn.db_type == "oracle":
        return get_oracle_connection(conn)
    elif conn.db_type == "sqlserver":
        return get_sqlserver_connection(conn)
    elif conn.db_type == "postgresql":
        return get_postgresql_connection(conn)
    elif conn.db_type == "mysql":
        return get_mysql_connection(conn)
    else:
        raise ValueError(f"Tipo de banco desconhecido: {conn.db_type}")


def test_connection(conn: Connection) -> tuple[bool, str]:
    """Test a connection and return (success, message) with version and timing."""
    import time as _time
    db = None
    try:
        start = _time.time()
        db = get_connection(conn)
        cursor = db.cursor()
        try:
            try:
                if conn.db_type == "oracle":
                    cursor.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
                elif conn.db_type == "sqlserver":
                    cursor.execute("SELECT @@VERSION")
                else:
                    cursor.execute("SELECT version()")
                version_row = cursor.fetchone()
                version = version_row[0][:80] if version_row else "desconhecida"
            except Exception:
                version = "indisponivel"
                if conn.db_type == "oracle":
                    cursor.execute("SELECT 1 FROM DUAL")
                else:
                    cursor.execute("SELECT 1")
                cursor.fetchone()
        finally:
            cursor.close()

        elapsed = _time.time() - start
        return True, (
            f'Conexao "{conn.name}" OK! ({elapsed:.2f}s)\n'
            f"  Versao: {version}"
        )
    except Exception as e:
        err_msg = str(e)
        sanitized = err_msg.split('\n')[0][:200]
        return False, f"Erro ao conectar: {sanitized}"
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
