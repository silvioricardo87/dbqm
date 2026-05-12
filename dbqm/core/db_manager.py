"""Database connection manager for Oracle, SQL Server, PostgreSQL, and MySQL."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dbqm.core.crypto import decrypt
from dbqm.models.connection import Connection

_thick_mode_initialized = False


def _missing_driver_message(db_label: str, package: str) -> str:
    """Format a hint when a database driver wheel is unavailable on this platform.

    Triggered notably on Windows ARM64, where psycopg-binary and pymssql have
    no published wheels.
    """
    import platform
    import sys
    plat = f"{sys.platform}/{platform.machine()}"
    return (
        f"Driver para {db_label} ({package}) nao esta instalado neste ambiente "
        f"({plat}). Instale manualmente com `pip install {package}` se houver "
        f"wheel disponivel para sua plataforma; em Windows ARM, este driver "
        f"nao tem wheel publicada e foi omitido por padrao."
    )


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


from dbqm.core.paths import CLIENTS_DIR


def _find_oracle_client_dir() -> str | None:
    """Auto-detect Oracle Instant Client directory matching Python architecture."""
    import struct
    arch = "x64" if struct.calcsize("P") * 8 == 64 else "x86"

    def _best_instantclient(base_dir: Path) -> str | None:
        """Find best matching instantclient subdirectory in base_dir."""
        if not base_dir.exists():
            return None
        candidates = sorted(
            [e for e in base_dir.iterdir() if e.is_dir() and "instantclient" in e.name.lower()],
            key=lambda e: (arch in e.name.lower(), e.name),
            reverse=True,
        )
        return str(candidates[0]) if candidates else None

    # 1. Check DBQM_HOME clients/ directory
    result = _best_instantclient(CLIENTS_DIR)
    if result:
        return result
    # 2. Check package-local clients/ directory (next to dbqm/ package)
    pkg_clients = Path(__file__).resolve().parent.parent.parent / "clients"
    result = _best_instantclient(pkg_clients)
    if result:
        return result
    # 3. Check ORACLE_HOME env var — validate architecture via oci.dll
    oracle_home = os.environ.get("ORACLE_HOME")
    if oracle_home:
        oh_path = Path(oracle_home)
        if oh_path.exists():
            oci_dll = oh_path / "oci.dll"
            if oci_dll.exists():
                try:
                    with open(oci_dll, "rb") as f:
                        f.seek(0x3C)
                        pe_offset = int.from_bytes(f.read(4), "little")
                        f.seek(pe_offset + 4)
                        machine = int.from_bytes(f.read(2), "little")
                        # 0x8664 = AMD64, 0x14c = i386
                        dll_is_64 = machine == 0x8664
                        python_is_64 = struct.calcsize("P") * 8 == 64
                        if dll_is_64 == python_is_64:
                            return oracle_home
                except Exception:
                    pass
            else:
                return oracle_home
    # 4. Search common locations
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


def _ensure_utf8_nls_lang() -> None:
    """Force NLS_LANG to UTF-8 so the Oracle client returns messages in UTF-8.

    Without this, on Windows the thick client typically returns server messages
    in WE8MSWIN1252/WE8ISO8859P1, which Python then mis-decodes as UTF-8 and
    renders accents as `�` (e.g. `s�mbolo` instead of `símbolo`).
    """
    current = os.environ.get("NLS_LANG", "")
    # Preserve user-set NLS_LANG that already targets a UTF-8 charset.
    if "UTF8" in current.upper() or "AL32UTF8" in current.upper():
        return
    # Preserve language/territory if present (`LANG_TERRITORY.CHARSET` form),
    # only swap the charset.
    if "." in current:
        prefix = current.rsplit(".", 1)[0]
        os.environ["NLS_LANG"] = f"{prefix}.AL32UTF8"
    else:
        os.environ["NLS_LANG"] = ".AL32UTF8"


def _init_thick_mode(config_dir: str | None = None) -> bool:
    """Initialize Oracle thick mode. Returns True if successful."""
    global _thick_mode_initialized, _thick_mode_error
    if _thick_mode_initialized:
        return True
    _ensure_utf8_nls_lang()
    try:
        import oracledb
    except ImportError as e:
        _thick_mode_error = str(e)
        return False
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


# Eagerly initialize thick mode at import time — must happen before any connection
_init_thick_mode()


def get_oracle_connection(conn: Connection) -> Any:
    """Establish Oracle connection. Initializes thick mode eagerly to avoid DPY-3015."""
    try:
        import oracledb
    except ImportError as e:
        raise RuntimeError(_missing_driver_message("Oracle", "oracledb")) from e

    password = decrypt(conn.password)
    config_dir = str(Path(conn.tns_path).parent) if conn.tns_path else None

    if conn.mode == "tns" and conn.tns_name:
        dsn = conn.tns_name
        # Try to parse TNS file to build a proper DSN
        if conn.tns_path:
            tns_info = _parse_tns_entry(conn.tns_path, conn.tns_name)
            if tns_info:
                if tns_info.get("service_name"):
                    dsn = oracledb.makedsn(
                        tns_info["host"], tns_info["port"],
                        service_name=tns_info["service_name"],
                    )
                elif tns_info.get("sid"):
                    dsn = oracledb.makedsn(
                        tns_info["host"], tns_info["port"],
                        sid=tns_info["sid"],
                    )
    else:
        host = conn.host or "localhost"
        port = conn.port or 1521
        svc = conn.service_name or ""
        dsn = oracledb.makedsn(host, port, service_name=svc)

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
    try:
        import pymssql
    except ImportError as e:
        raise RuntimeError(_missing_driver_message("SQL Server", "pymssql")) from e

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
    try:
        import psycopg
    except ImportError as e:
        raise RuntimeError(_missing_driver_message("PostgreSQL", "psycopg[binary]")) from e

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
    try:
        import pymysql
    except ImportError as e:
        raise RuntimeError(_missing_driver_message("MySQL", "PyMySQL")) from e

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


def fetch_table_columns(conn: Connection, table: str) -> list[str]:
    """Fetch column names from a table. Returns empty list on error."""
    db = None
    try:
        db = get_connection(conn)
        cursor = db.cursor()
        try:
            # Handle schema.table notation
            parts = table.replace('"', '').replace('`', '').replace('[', '').replace(']', '').split('.')
            table_name = parts[-1]
            schema = parts[0] if len(parts) > 1 else None

            if conn.db_type == "oracle":
                if schema:
                    cursor.execute(
                        "SELECT column_name FROM all_tab_columns "
                        "WHERE table_name = :tbl AND owner = :own ORDER BY column_id",
                        {"tbl": table_name.upper(), "own": schema.upper()},
                    )
                else:
                    cursor.execute(
                        "SELECT column_name FROM user_tab_columns "
                        "WHERE table_name = :tbl ORDER BY column_id",
                        {"tbl": table_name.upper()},
                    )
            elif conn.db_type == "postgresql":
                schema_val = schema or "public"
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = %(tbl)s AND table_schema = %(sch)s "
                    "ORDER BY ordinal_position",
                    {"tbl": table_name, "sch": schema_val},
                )
            elif conn.db_type == "mysql":
                if schema:
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = %(tbl)s AND table_schema = %(sch)s "
                        "ORDER BY ordinal_position",
                        {"tbl": table_name, "sch": schema},
                    )
                else:
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = %(tbl)s AND table_schema = DATABASE() "
                        "ORDER BY ordinal_position",
                        {"tbl": table_name},
                    )
            else:
                # sqlserver / generic
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = %(tbl)s ORDER BY ordinal_position",
                    {"tbl": table_name},
                )
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
    except Exception:
        return []
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


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
