"""A database's shape: objects, one object's structure, a table's rows, DDL.

Every function opens the handle it needs and closes it before returning.
Failures keep the distinction `cli/errors.py` exists for: the database not
answering is `connection_failed`; the database answering and rejecting what
was asked is `sql_error`, or `usage` when `core/` says the engine has no
such capability at all.
"""
from __future__ import annotations

from typing import Any, Callable, TypeVar

from dbqm.core.ddl_extractor import ExtractionResult
from dbqm.core.table_browser import BrowseResult
from dbqm.i18n import t
from dbqm.models.connection import Connection
from dbqm.ops import deps
from dbqm.ops.errors import OperationError

T = TypeVar("T")


def with_open_connection(conn: Connection, action: Callable[[Any], T]) -> T:
    """Open a handle, run `action(db)` on it, and map each failure to its token.

    The two failures are kept apart deliberately. `open_connection` failing
    means the database did not answer -> `connection_failed` (3). `action`
    failing means the database answered and rejected what we asked -> a
    statement error (4), or `usage` (2) when `core/` says the capability does
    not exist on this engine at all. Collapsing both into `connection_failed`
    is what `run` and `sql` do, and it is the distinction `errors.py` exists
    to preserve: a caller retrying a connection failure would retry forever
    against a query the engine will never accept.
    """
    try:
        with deps.open_connection(conn) as db:
            # These two handlers exhaust everything `action` can raise, so
            # the outer handler below can only ever see a failure from
            # opening the connection itself. That is what keeps the two
            # apart.
            try:
                return action(db)
            except deps.UnsupportedEngine as e:
                raise OperationError("usage", str(e)) from e
            except deps.ObjectNotFound as e:
                raise OperationError("not_found", str(e)) from e
            except ValueError as e:
                raise OperationError("usage", str(e)) from e
            except Exception as e:
                raise OperationError("sql_error", str(e)) from e
    except OperationError:
        # Without this arm, the outer `except Exception` below would catch
        # an `OperationError` raised inside -- a `sql_error` from `action`,
        # say -- and relabel it `connection_failed`. Re-raising here keeps
        # the inner mapping intact; only a failure to open the connection
        # itself should reach the outer handler.
        raise
    except Exception as e:
        raise OperationError("connection_failed", str(e)) from e


def list_objects(conn: Connection, obj_type: str) -> list[str]:
    kind = obj_type.upper()
    return with_open_connection(conn, lambda db: deps.list_objects(db, conn.db_type, kind))


def describe(conn: Connection, name: str) -> dict[str, Any]:
    """Show one object's shape: columns, keys and indexes.

    Dispatches on what the object turns out to be rather than asking the user
    to say table or view. No row count in either format: a COUNT(*) is a full
    scan, which is why `psql \\d` does not show one either. `-f table` and
    `-f json` carry the same content -- one shape for the command, not two.
    """
    def action(db: Any) -> tuple[Any, Any]:
        structure = deps.get_table_structure(db, conn.db_type, name)
        view = deps.get_view_definition(db, conn.db_type, name)
        return structure, view

    structure, view = with_open_connection(conn, action)
    definition = view.sql_definition or ""
    # `owner`, not the definition, is what says the object is a view. A view
    # whose source the connected user may not read comes back with its owner
    # set and an empty definition -- measured on SQL Server, where a missing
    # VIEW DEFINITION grant makes both information_schema.views and
    # sys.sql_modules return NULL rather than an error. Labelling on the
    # definition alone reports such a view as a table.
    is_view = bool(view.owner or definition)
    if not structure.columns and not is_view:
        raise OperationError("not_found",
                             t("describe.not_table_nor_view", name=name, connection=conn.name))
    data: dict[str, Any] = structure.to_dict()
    data["connection_name"] = conn.name
    data["object_type"] = "VIEW" if is_view else "TABLE"
    if definition:
        data["sql_definition"] = definition
    return data


def rows(conn: Connection, table: str, *, limit: int, offset: int) -> BrowseResult:
    """Browse a table's rows, paged.

    No `--where`: `dbqm sql` already takes a predicate, and a filter
    expression here would be injection surface bought for nothing.
    """
    if limit < 1:
        raise OperationError("usage", t("rows.limit_positive"))
    if offset < 0:
        raise OperationError("usage", t("rows.offset_not_negative"))

    def action(db: Any) -> BrowseResult:
        try:
            return deps.browse_table(
                db, conn.db_type, table, conn.name,
                limit=limit, offset=offset,
            )
        except ValueError:
            # `_validate_identifier` refused the name. Bad input, not a
            # missing table -- do not go asking whether it exists.
            raise
        except Exception as original:
            # Ask only now: on success this costs nothing, and the catalogue
            # answers authoritatively instead of us matching four dialects of
            # "table does not exist". Views are not tables, so a valid view
            # name would wrongly 404 without also checking "VIEW".
            try:
                tables = {t.upper() for t in deps.list_objects(db, conn.db_type, "TABLE")}
                views = {v.upper() for v in deps.list_objects(db, conn.db_type, "VIEW")}
            except Exception:
                # The diagnosis itself failed. Raise the ORIGINAL by name, not
                # a bare `raise`, which inside a nested handler re-raises the
                # inner one -- the user must learn what their own query did
                # wrong, not what the existence check did wrong.
                raise original from None
            if table.upper() not in tables | views:
                raise deps.ObjectNotFound(
                    t("rows.table_not_found", name=table, connection=conn.name)
                ) from original
            raise

    return with_open_connection(conn, action)


def extract_ddl(conn: Connection, obj: str, *, on_progress: Any = None) -> ExtractionResult:
    """`extract_ddl` opens its own handle and records every statement failure
    into `result.errors`, so anything that escapes it is a failure to open --
    the same call-site reasoning `query_engine` uses for `error_kind`.
    Without this the exception reached `main.py` and became exit 1, "a bug
    in dbqm", for a database that was merely unreachable.
    """
    try:
        result = deps.extract_ddl(conn, obj, on_progress=on_progress)
    except Exception as e:
        raise OperationError("connection_failed", str(e)) from e
    if result.errors and not result.objects:
        code = "not_found" if result.not_found else "sql_error"
        raise OperationError(code, "; ".join(result.errors))
    return result
