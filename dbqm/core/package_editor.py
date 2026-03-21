"""Oracle package editor — core logic for creating, editing, and compiling packages."""
from __future__ import annotations


def check_package_exists(db, pkg_name: str) -> bool:
    """Check if a package exists in the database."""
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM ALL_OBJECTS WHERE OBJECT_NAME = :name "
            "AND OBJECT_TYPE = 'PACKAGE' "
            "AND OWNER = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA')",
            {"name": pkg_name.upper()},
        )
        row = cursor.fetchone()
        return row[0] > 0 if row else False
    finally:
        cursor.close()


def fetch_package_source(db, pkg_name: str) -> tuple[str, str]:
    """Fetch spec and body source from ALL_SOURCE. Returns (spec_sql, body_sql)."""
    spec = _get_source(db, pkg_name, "PACKAGE")
    body = _get_source(db, pkg_name, "PACKAGE BODY")
    return (spec, body)


def _get_source(db, pkg_name: str, obj_type: str) -> str:
    """Fetch source lines for a given object type and reassemble."""
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT TEXT FROM ALL_SOURCE WHERE NAME = :name AND TYPE = :type "
            "AND OWNER = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') ORDER BY LINE",
            {"name": pkg_name.upper(), "type": obj_type},
        )
        lines = [row[0] for row in cursor.fetchall()]
        if not lines:
            return ""
        # Prepend CREATE OR REPLACE
        source = "".join(lines)
        return f"CREATE OR REPLACE {source}"
    finally:
        cursor.close()


def compile_package(db, sql: str) -> tuple[bool, str]:
    """Execute CREATE OR REPLACE PACKAGE/BODY. Returns (success, error_msg)."""
    cursor = db.cursor()
    try:
        cursor.execute(sql)
        return (True, "")
    except Exception as e:
        return (False, str(e))
    finally:
        cursor.close()


def fetch_compilation_errors(db, pkg_name: str, obj_type: str) -> list[dict]:
    """Fetch compilation errors from ALL_ERRORS.

    Returns list of {"line": int, "col": int, "message": str}.
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT LINE, POSITION, TEXT FROM ALL_ERRORS "
            "WHERE NAME = :name AND TYPE = :type "
            "AND OWNER = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') "
            "ORDER BY SEQUENCE",
            {"name": pkg_name.upper(), "type": obj_type},
        )
        return [
            {"line": row[0], "col": row[1], "message": str(row[2]).strip()}
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()


def generate_blank_template(pkg_name: str) -> tuple[str, str]:
    """Generate blank spec and body templates."""
    name = pkg_name.upper()
    spec = (
        f"CREATE OR REPLACE PACKAGE {name} AS\n"
        f"\n"
        f"  -- Declare procedures and functions here\n"
        f"\n"
        f"END {name};"
    )
    body = (
        f"CREATE OR REPLACE PACKAGE BODY {name} AS\n"
        f"\n"
        f"  -- Implement procedures and functions here\n"
        f"\n"
        f"END {name};"
    )
    return (spec, body)


def generate_wizard_template(pkg_name: str, routines: list[dict]) -> tuple[str, str]:
    """Generate spec and body from routine definitions.

    routines: list of {
        "name": str,
        "type": "PROCEDURE"|"FUNCTION",
        "params": str,
        "return_type": str|None,
    }
    """
    name = pkg_name.upper()
    spec_parts = [f"CREATE OR REPLACE PACKAGE {name} AS\n"]
    body_parts = [f"CREATE OR REPLACE PACKAGE BODY {name} AS\n"]

    for r in routines:
        sig = f"  {r['type']} {r['name']}"
        if r.get("params"):
            sig += f"({r['params']})"
        if r["type"] == "FUNCTION" and r.get("return_type"):
            sig += f" RETURN {r['return_type']}"

        spec_parts.append(f"{sig};\n")

        if r["type"] == "FUNCTION":
            body_parts.append(
                f"{sig} IS\n  BEGIN\n    RETURN NULL; -- TODO\n  END {r['name']};\n"
            )
        else:
            body_parts.append(
                f"{sig} IS\n  BEGIN\n    NULL; -- TODO\n  END {r['name']};\n"
            )

    spec_parts.append(f"\nEND {name};")
    body_parts.append(f"\nEND {name};")

    return ("\n".join(spec_parts), "\n".join(body_parts))
