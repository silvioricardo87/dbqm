"""What the operations layer and the CLI consume from `core/` and `models/`.

One module names every symbol the command layer reaches for, instead of thirty
imports spread across the top of a file. Two things follow from that.

It states the coupling. Anything `ops/` or the CLI needs from `core/` or
`models/` is listed here, so the direction of dependency is readable in one
place.

And it gives the tests a single patch path — but **only if callers use
qualified access**: `deps.find_connection(...)`, never
`from dbqm.ops.deps import find_connection`.

That is not a style preference, it is the whole mechanism. A bare-name import
copies the function object into the importing module's namespace at import
time. Patching `dbqm.ops.deps.find_connection` then rebinds the attribute on
*this* module and the caller never sees it: it resolves the copy it already
holds, runs the real function, and the test passes while testing nothing.
Attribute access through the module resolves at call time, which is what the
patch replaces.

Measured when this was got wrong: 30 of 134 tests failed, every one of them
reaching a real lookup or a real connection attempt.
"""
from __future__ import annotations

from dbqm.core.audit import log_execution
from dbqm.core.config_portability import export_configs, import_configs
from dbqm.core.db_manager import error_text, open_connection, test_connection
from dbqm.core.ddl_extractor import extract_ddl, save_extraction
from dbqm.core.exporter import (
    export_group_csv,
    export_group_flat_csv,
    export_group_flat_json,
    export_group_flat_txt,
    export_group_json,
    export_group_txt,
    export_query_csv,
    export_query_json,
    export_query_txt,
)
from dbqm.core.group_engine import (
    NoComparableColumns,
    build_adhoc_group_result,
    build_group_result,
    derive_comparison_columns,
    execute_across,
)
from dbqm.core.html_report import export_group_html, export_query_html
from dbqm.core.history import (
    clear_history,
    load_history,
    record_group_execution,
    record_query_execution,
)
from dbqm.core.object_browser import (
    ObjectNotFound,
    UnsupportedEngine,
    execute_routine,
    get_standalone_routine_info,
    get_table_structure,
    get_view_definition,
    list_objects,
    list_package_routines,
)
from dbqm.core.oracle_client_installer import (
    available_clients,
    detect_host_platform,
    host_platform_label,
    install_client,
    list_installed_clients,
    remove_client,
)
from dbqm.core.query_engine import (
    MAX_ROWS,
    QueryResult,
    classify_sql,
    detect_params,
    execute_adhoc,
    execute_explain,
    execute_query,
)
from dbqm.core.read_only import ReadOnlyViolation, check_read_only
from dbqm.core.table_browser import browse_table
from dbqm.models.connection import find_connection, load_connections
from dbqm.models.group import find_group, load_groups
from dbqm.models.query import find_query, load_queries
from dbqm.models.settings import load_settings, save_settings
from dbqm.models.template import find_template, load_templates

__all__ = [
    "MAX_ROWS",
    "NoComparableColumns",
    "ObjectNotFound",
    "QueryResult",
    "ReadOnlyViolation",
    "UnsupportedEngine",
    "available_clients",
    "browse_table",
    "build_adhoc_group_result",
    "build_group_result",
    "check_read_only",
    "classify_sql",
    "detect_params",
    "clear_history",
    "derive_comparison_columns",
    "detect_host_platform",
    "error_text",
    "execute_across",
    "execute_adhoc",
    "execute_explain",
    "execute_query",
    "execute_routine",
    "export_configs",
    "export_group_csv",
    "export_group_flat_csv",
    "export_group_flat_json",
    "export_group_flat_txt",
    "export_group_html",
    "export_group_json",
    "export_group_txt",
    "export_query_csv",
    "export_query_html",
    "export_query_json",
    "export_query_txt",
    "extract_ddl",
    "find_connection",
    "find_group",
    "find_query",
    "find_template",
    "get_standalone_routine_info",
    "get_table_structure",
    "get_view_definition",
    "host_platform_label",
    "import_configs",
    "install_client",
    "list_installed_clients",
    "list_objects",
    "list_package_routines",
    "load_connections",
    "load_groups",
    "load_history",
    "load_queries",
    "load_settings",
    "load_templates",
    "log_execution",
    "open_connection",
    "record_group_execution",
    "record_query_execution",
    "remove_client",
    "save_extraction",
    "save_settings",
    "test_connection",
]
