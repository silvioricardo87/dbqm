"""MySQL DDL extraction via SHOW CREATE statements."""
from __future__ import annotations

from typing import Any

from dbqm.i18n import t
from dbqm.core.ddl_extractor import ExtractionResult, ExtractedObject


def extract_mysql_ddl(db: Any, object_name: str, result: ExtractionResult, on_progress: Any = None) -> None:
    """Extract DDL for a MySQL object (table, view, procedure, function)."""
    cursor = db.cursor()
    name = object_name.strip()

    try:
        # Try table
        try:
            if on_progress:
                on_progress(1, 1, "TABLE", name)
            cursor.execute(f"SHOW CREATE TABLE `{name}`")
            row = cursor.fetchone()
            if row:
                result.object_type = "TABLE"
                result.objects.append(ExtractedObject(name, "TABLE", row[1] + ";"))
                return
        except Exception:
            pass

        # Try view
        try:
            cursor.execute(f"SHOW CREATE VIEW `{name}`")
            row = cursor.fetchone()
            if row:
                result.object_type = "VIEW"
                result.objects.append(ExtractedObject(name, "VIEW", row[1] + ";"))
                return
        except Exception:
            pass

        # Try procedure
        try:
            cursor.execute(f"SHOW CREATE PROCEDURE `{name}`")
            row = cursor.fetchone()
            if row and row[2]:
                result.object_type = "PROCEDURE"
                result.objects.append(ExtractedObject(name, "PROCEDURE", row[2] + ";"))
                return
        except Exception:
            pass

        # Try function
        try:
            cursor.execute(f"SHOW CREATE FUNCTION `{name}`")
            row = cursor.fetchone()
            if row and row[2]:
                result.object_type = "FUNCTION"
                result.objects.append(ExtractedObject(name, "FUNCTION", row[2] + ";"))
                return
        except Exception:
            pass

        result.errors.append(t("ddl.object_not_found", nome=object_name))
        result.not_found = True
    finally:
        cursor.close()
