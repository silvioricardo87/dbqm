"""Commands for curating saved queries, groups and templates: add, update,
rm, show, list.

Mirrors `dbqm.cli.commands.connection` -- the subparser shape, `_fail_or_print`,
the outcome printer, and `_*_rm`'s confirmation (refuse under a non-terminal
stdin rather than hang, and prompt on stderr so `-f json`'s stdout stays
JSON-only) are the same decisions, copied on purpose. `cmd_query`, `cmd_group`
and `cmd_template` all live here, over `query_builder`, `group_builder` and
`template_builder` respectively -- same shape, same two-dictionary rule
(validate the merged effective state, `build` the sparse flags actually
given), none uses `upsert` (that is what the TUI's Salvar button means; the
CLI's `add` on an existing name and `update` on a missing one are both
errors a script wants to hear about). Ad-hoc (Multi-Exec) groups are out of
scope for `cmd_group`: no flag here sets `adhoc_sql`/`connections`, but
`group_builder.build` still preserves them on an `update` of a group that
already has them.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from rich.markup import escape
from rich.table import Table

from dbqm.i18n import t
from dbqm.cli import deps
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.render import console

# Set by `build_parser` (in `dbqm.cli`) so `cmd_query`/`cmd_group`/
# `cmd_template` can print their own group's help (add/update/rm/show/list)
# on a bare `dbqm query` / `dbqm group` / `dbqm template`, the same way
# `connection._connection_parser` does for `dbqm connection`.
_query_parser: argparse.ArgumentParser | None = None
_group_parser: argparse.ArgumentParser | None = None
_template_parser: argparse.ArgumentParser | None = None


_QUERY_OUTCOME_KEY = {
    "created": "query.created",
    "updated": "query.updated",
    "removed": "query.removed",
}

# `outcome` (past participle, used in the Rich sentence) to the verb the
# envelope's `command` field uses instead (`query.add`, not `query.created`).
_QUERY_OUTCOME_VERB = {
    "created": "add",
    "updated": "update",
    "removed": "rm",
}


def _print_query_outcome(output_format: str, name: str, outcome: str) -> None:
    if output_format == "json":
        verbo = _QUERY_OUTCOME_VERB[outcome]
        ok(f"query.{verbo}", {"name": name, outcome: True})
        return
    console.print(escape(t(_QUERY_OUTCOME_KEY[outcome], name=name)))


def _fail_or_print(
    args: argparse.Namespace,
    command: str,
    code: str,
    message: str,
    *,
    extra: str | None = None,
) -> NoReturn:
    """Mirrors `connection._fail_or_print`: same branch point for `-f json`
    versus `table`, same exit code either way -- only what gets printed, and
    where, differs.
    """
    if args.format == "json":
        fail(command, code, message)
    console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
    if extra:
        console.print(extra)
    sys.exit(int(exit_for(code)))


def _exit_with_errors(args: argparse.Namespace, command: str, errors: list[str]) -> NoReturn:
    if args.format == "json":
        fail(command, "validation", "; ".join(errors))
    for error in errors:
        console.print(f"[ds.op.failure]{escape(error)}[/ds.op.failure]")
    sys.exit(int(exit_for("validation")))


def _resolve_sql(args: argparse.Namespace, command: str) -> str | None:
    """The SQL text for `add`/`update`, or `None` if neither flag was given.

    `None` here (not `""`) is what lets `_query_values` drop the key entirely
    when the command line never mentions the query's SQL -- an `update
    --description` must not re-derive `table`/`columns`/`order_by` from
    whatever SQL happens to already be stored. `--sql-file` is read as UTF-8
    text; an unreadable path is `usage`, not a stack trace -- the file is
    something a script handed dbqm, not something dbqm already has.
    """
    sql_file = getattr(args, "sql_file", None)
    if sql_file:
        try:
            return Path(sql_file).read_text(encoding="utf-8")
        except OSError as exc:
            _fail_or_print(args, command, "usage",
                            t("file.unreadable", name=sql_file, error=exc))
    return getattr(args, "sql", None)


def _query_values(args: argparse.Namespace, sql: str | None) -> dict[str, object]:
    """Only the flags actually given. A flag left out must not overwrite.

    Mirrors `connection._connection_values`: `None` means "not mentioned on
    this command line" and is dropped here so `query_builder.build` sees an
    absent key -- which is what lets `query update --description` leave
    `sql`-derived fields, `column_maps`, `folder` and `is_favorite` exactly
    as they were.
    """
    values = {
        "name": args.name,
        "connection": args.connection,
        "description": args.description,
        "folder": args.folder,
        "is_favorite": args.is_favorite,
        "sql": sql,
    }
    return {key: value for key, value in values.items() if value is not None}


def _query_add(args: argparse.Namespace) -> None:
    from dbqm.core.query_builder import build, validate
    from dbqm.models.query import save_queries

    if deps.find_query(args.name) is not None:
        _exit_with_errors(args, "query.add", [t("query.already_exists", name=args.name)])

    sql = _resolve_sql(args, "query.add")
    values = _query_values(args, sql)

    errors = validate(values)
    if errors:
        _exit_with_errors(args, "query.add", errors)

    query = build(values)

    queries = deps.load_queries()
    queries.append(query)
    save_queries(queries)
    _print_query_outcome(args.format, query.name, "created")


def _query_update(args: argparse.Namespace) -> None:
    from dbqm.core.query_builder import build, validate
    from dbqm.models.query import save_queries

    existing = deps.find_query(args.name)
    if existing is None:
        _fail_or_print(args, "query.update", "not_found",
                        t("query.not_found_named", name=args.name))

    sql = _resolve_sql(args, "query.update")
    values = _query_values(args, sql)

    # Validate the EFFECTIVE state an update would leave behind, not the
    # sparse `values` alone: a `query update NOME --description "..."` must
    # not fail validation just because --sql/--connection were not repeated
    # on this command line.
    merged = existing.to_dict()
    merged.update(values)
    errors = validate(merged)
    if errors:
        _exit_with_errors(args, "query.update", errors)

    # `build` gets the SPARSE `values`, never `merged`: `merged` always
    # carries a "sql" key (copied from `existing`), and if that reached
    # `build` it would re-derive `table`/`columns`/`order_by` from it even
    # when the user never passed --sql/--sql-file -- silently discarding a
    # manual edit to `table` the way `query_builder.build`'s docstring warns
    # against.
    query = build(values, existing)

    queries = deps.load_queries()
    index = next(i for i, q in enumerate(queries) if q.name == query.name)
    queries[index] = query
    save_queries(queries)
    _print_query_outcome(args.format, query.name, "updated")


def _query_show(args: argparse.Namespace) -> None:
    query = deps.find_query(args.name)
    if query is None:
        _fail_or_print(args, "query.show", "not_found",
                        t("query.not_found_named", name=args.name))

    data = query.to_dict()

    if args.format == "json":
        ok("query.show", data)
        return

    table = Table(title=escape(t("query.show_title", name=query.name)))
    table.add_column(t("common.field"))
    table.add_column(t("common.value"))
    for key, value in data.items():
        table.add_row(key, escape(str(value)))
    console.print(table)


def _query_rm(args: argparse.Namespace) -> None:
    from dbqm.models.query import delete_query

    if deps.find_query(args.name) is None:
        _fail_or_print(args, "query.rm", "not_found",
                        t("query.not_found_named", name=args.name))

    if not args.yes:
        # Refuse rather than prompt when there is no terminal: a script that
        # hangs on an unanswerable question is worse than one that fails.
        if not sys.stdin.isatty():
            _fail_or_print(args, "query.rm", "usage",
                            t("common.remove_needs_yes"))
        # The prompt goes to stderr: `input(prompt)` writes it to stdout,
        # which would put prose on the stream the envelope owns.
        print(t("query.confirm_remove", name=args.name), end="",
              file=sys.stderr, flush=True)
        resposta = input().strip().lower()
        if resposta not in t("common.yes_answers").split(","):
            if args.format == "json":
                ok("query.rm", {"name": args.name, "removed": False})
            else:
                console.print(t("common.cancelled"))
            return

    delete_query(args.name)
    _print_query_outcome(args.format, args.name, "removed")


def _query_list(args: argparse.Namespace) -> None:
    """Like `dbqm list queries`, plus an optional `--connection` filter that
    `list queries` has no room for (its `resource` is shared with
    connections/groups)."""
    items = deps.load_queries()
    connection = getattr(args, "connection", None)
    if connection:
        items = [q for q in items if q.connection == connection]

    if args.format == "json":
        data = [{"name": q.name, "connection": q.connection, "folder": q.folder,
                  "description": q.description,
                  "params": [p.name for p in q.params]} for q in items]
        ok("query.list", data)
        return

    if not items:
        console.print(f'[ds.text.muted]{t("query.none_configured")}[/ds.text.muted]')
        return

    table = Table(title=t("query.list_title"))
    table.add_column(t("common.name"))
    table.add_column(t("common.description"))
    table.add_column(t("common.connection"))
    table.add_column(t("common.folder"))
    table.add_column(t("common.params"))
    table.add_column(t("common.favorite_short"))
    for q in items:
        params = ", ".join(p.name for p in q.params) or "-"
        fav = "*" if q.is_favorite else ""
        desc = q.description[:50] + "..." if len(q.description) > 50 else q.description
        table.add_row(escape(q.name), escape(desc or "-"), f"[ds.identity]{escape(q.connection)}[/]",
                      escape(q.folder or "-"), escape(params), fav)
    console.print(table)


_QUERY_SUBCOMMANDS = {
    "add": _query_add,
    "update": _query_update,
    "rm": _query_rm,
    "show": _query_show,
    "list": _query_list,
}


def cmd_query(args: argparse.Namespace) -> None:
    """Manage saved queries."""
    subcommand = getattr(args, "subcommand", None)
    handler = _QUERY_SUBCOMMANDS.get(subcommand) if isinstance(subcommand, str) else None
    if handler is None:
        # A bare `dbqm query` prints the group's own help (add/update/rm/
        # show/list, with their flags) rather than a one-line reminder.
        if _query_parser is not None:
            _query_parser.print_help()
        else:
            console.print(
                f'[ds.op.failure]{t("query.usage")}[/ds.op.failure]'
            )
        sys.exit(int(exit_for("validation")))
    handler(args)


# ---------------------------------------------------------------------------
# dbqm group add|update|show|rm|list
# ---------------------------------------------------------------------------

_GROUP_OUTCOME_KEY = {
    "created": "group.created",
    "updated": "group.updated",
    "removed": "group.removed",
}

# `outcome` (past participle, used in the Rich sentence) to the verb the
# envelope's `command` field uses instead (`group.add`, not `group.created`).
_GROUP_OUTCOME_VERB = {
    "created": "add",
    "updated": "update",
    "removed": "rm",
}


def _print_group_outcome(output_format: str, name: str, outcome: str) -> None:
    if output_format == "json":
        verbo = _GROUP_OUTCOME_VERB[outcome]
        ok(f"group.{verbo}", {"name": name, outcome: True})
        return
    console.print(escape(t(_GROUP_OUTCOME_KEY[outcome], name=name)))


def _group_values(args: argparse.Namespace) -> dict[str, object]:
    """Only the flags actually given. Mirrors `_query_values`.

    `None` means "not mentioned on this command line" and is dropped here so
    `group_builder.build` sees an absent key -- which is what lets `group
    update --description` leave `queries`, `compare_columns`, `join_key`,
    `column_mapping`, `normalize`, `template`, `template_fields`,
    `validation_rule`, `adhoc_sql` and `connections` exactly as they were.
    `--query`/`--compare-column` are `action="append"`, so an absent flag is
    `None` (not `[]`) and is dropped the same way a scalar flag is.
    """
    values = {
        "name": args.name,
        "description": args.description,
        "folder": args.folder,
        "join_key": args.join_key,
        "queries": args.query,
        "compare_columns": args.compare_column,
    }
    return {key: value for key, value in values.items() if value is not None}


def _group_add(args: argparse.Namespace) -> None:
    from dbqm.core.group_builder import build, validate
    from dbqm.models.group import save_groups

    if deps.find_group(args.name) is not None:
        _exit_with_errors(args, "group.add", [t("group.already_exists", name=args.name)])

    values = _group_values(args)

    errors = validate(values)
    if errors:
        _exit_with_errors(args, "group.add", errors)

    group = build(values)

    groups = deps.load_groups()
    groups.append(group)
    save_groups(groups)
    _print_group_outcome(args.format, group.name, "created")


def _group_update(args: argparse.Namespace) -> None:
    from dbqm.core.group_builder import build, validate
    from dbqm.models.group import save_groups

    existing = deps.find_group(args.name)
    if existing is None:
        _fail_or_print(args, "group.update", "not_found",
                        t("group.not_found_named", name=args.name))

    values = _group_values(args)

    # Validate the EFFECTIVE state an update would leave behind, not the
    # sparse `values` alone: a `group update NOME --description "..."` must
    # not fail validation just because --query/--join-key were not repeated
    # on this command line.
    merged = existing.to_dict()
    merged.update(values)
    errors = validate(merged)
    if errors:
        _exit_with_errors(args, "group.update", errors)

    # `build` gets the SPARSE `values`, never `merged`: `merged` always
    # carries every field (copied from `existing`), and if that reached
    # `build` it would overwrite `column_mapping`/`normalize`/`template`/
    # `template_fields`/`validation_rule`/`adhoc_sql`/`connections` with
    # whatever `existing` already had for every update, which happens to
    # look harmless (it round-trips) until one of those fields was hand-
    # edited to something `values` could never reproduce -- the exact trap
    # `_query_update` guards against for `table`.
    group = build(values, existing)

    groups = deps.load_groups()
    index = next(i for i, g in enumerate(groups) if g.name == group.name)
    groups[index] = group
    save_groups(groups)
    _print_group_outcome(args.format, group.name, "updated")


def _group_show(args: argparse.Namespace) -> None:
    group = deps.find_group(args.name)
    if group is None:
        _fail_or_print(args, "group.show", "not_found",
                        t("group.not_found_named", name=args.name))

    data = group.to_dict()

    if args.format == "json":
        ok("group.show", data)
        return

    table = Table(title=escape(t("group.show_title", name=group.name)))
    table.add_column(t("common.field"))
    table.add_column(t("common.value"))
    for key, value in data.items():
        table.add_row(key, escape(str(value)))
    console.print(table)


def _group_rm(args: argparse.Namespace) -> None:
    from dbqm.models.group import delete_group

    if deps.find_group(args.name) is None:
        _fail_or_print(args, "group.rm", "not_found",
                        t("group.not_found_named", name=args.name))

    if not args.yes:
        # Refuse rather than prompt when there is no terminal: a script that
        # hangs on an unanswerable question is worse than one that fails.
        if not sys.stdin.isatty():
            _fail_or_print(args, "group.rm", "usage",
                            t("common.remove_needs_yes"))
        # The prompt goes to stderr: `input(prompt)` writes it to stdout,
        # which would put prose on the stream the envelope owns.
        print(t("group.confirm_remove", name=args.name), end="",
              file=sys.stderr, flush=True)
        resposta = input().strip().lower()
        if resposta not in t("common.yes_answers").split(","):
            if args.format == "json":
                ok("group.rm", {"name": args.name, "removed": False})
            else:
                console.print(t("common.cancelled"))
            return

    delete_group(args.name)
    _print_group_outcome(args.format, args.name, "removed")


def _group_list(args: argparse.Namespace) -> None:
    items = deps.load_groups()

    if args.format == "json":
        data = [{"name": g.name, "description": g.description, "folder": g.folder,
                  "queries": g.queries, "join_key": g.join_key} for g in items]
        ok("group.list", data)
        return

    if not items:
        console.print(f'[ds.text.muted]{t("group.none_configured")}[/ds.text.muted]')
        return

    table = Table(title=t("group.list_title"))
    table.add_column(t("common.name"))
    table.add_column(t("common.description"))
    table.add_column(t("query.list_title"))
    table.add_column(t("common.key"))
    table.add_column(t("common.folder"))
    for g in items:
        desc = g.description[:50] + "..." if len(g.description) > 50 else g.description
        table.add_row(escape(g.name), escape(desc or "-"), escape(", ".join(g.queries)),
                      escape(g.join_key), escape(g.folder or "-"))
    console.print(table)


_GROUP_SUBCOMMANDS = {
    "add": _group_add,
    "update": _group_update,
    "rm": _group_rm,
    "show": _group_show,
    "list": _group_list,
}


def cmd_group(args: argparse.Namespace) -> None:
    """Manage saved groups."""
    subcommand = getattr(args, "subcommand", None)
    handler = _GROUP_SUBCOMMANDS.get(subcommand) if isinstance(subcommand, str) else None
    if handler is None:
        # A bare `dbqm group` prints the group's own help (add/update/rm/
        # show/list, with their flags) rather than a one-line reminder.
        if _group_parser is not None:
            _group_parser.print_help()
        else:
            console.print(
                f'[ds.op.failure]{t("group.usage")}[/ds.op.failure]'
            )
        sys.exit(int(exit_for("validation")))
    handler(args)


# ---------------------------------------------------------------------------
# dbqm template add|update|show|rm|list
# ---------------------------------------------------------------------------

_TEMPLATE_OUTCOME_KEY = {
    "created": "template.created",
    "updated": "template.updated",
    "removed": "template.removed",
}

# `outcome` (past participle, used in the Rich sentence) to the verb the
# envelope's `command` field uses instead (`template.add`, not
# `template.created`).
_TEMPLATE_OUTCOME_VERB = {
    "created": "add",
    "updated": "update",
    "removed": "rm",
}


def _print_template_outcome(output_format: str, name: str, outcome: str) -> None:
    if output_format == "json":
        verbo = _TEMPLATE_OUTCOME_VERB[outcome]
        ok(f"template.{verbo}", {"name": name, outcome: True})
        return
    console.print(escape(t(_TEMPLATE_OUTCOME_KEY[outcome], name=name)))


def _resolve_content(args: argparse.Namespace, command: str) -> str | None:
    """The content text for `add`/`update`, or `None` if neither flag was
    given. Mirrors `_resolve_sql`: `None` (not `""`) is what lets
    `_template_values` drop the key entirely when the command line never
    mentions the template's content. `--content-file` is read as UTF-8 text,
    verbatim -- `template_builder.build` never strips it either, since
    leading/trailing whitespace in a report template's body is formatting,
    not incidental input noise.

    A path that cannot be read is `usage`, not a stack trace: the caller
    mistyped a filename, which is their mistake to see and fix, not a
    condition dbqm failed to handle.
    """
    content_file = getattr(args, "content_file", None)
    if content_file:
        try:
            return Path(content_file).read_text(encoding="utf-8")
        except OSError as exc:
            _fail_or_print(args, command, "usage",
                            t("file.unreadable", name=content_file, error=exc))
    return getattr(args, "content", None)


def _template_values(args: argparse.Namespace, content: str | None) -> dict[str, str]:
    """Only the flags actually given. Mirrors `_query_values`/`_group_values`.

    `None` means "not mentioned on this command line" and is dropped here so
    `template_builder.build` sees an absent key -- which is what lets
    `template update --description` leave `content` exactly as it was.

    Typed `dict[str, str]`, unlike its two siblings (`dict[str, object]`):
    every `Template` field is a plain string -- no `is_favorite` bool, no
    `queries` list -- so `str` is the precise type here, and it is also
    what lets `merged.update(values)` below type-check against
    `Template.to_dict()`'s own `dict[str, str]` (`dbqm.models.template` is
    strict-clean, unlike `query`/`group`, so `object` would not type-check
    there the way it harmlessly does for the other two).
    """
    values = {
        "name": args.name,
        "description": args.description,
        "content": content,
    }
    return {key: value for key, value in values.items() if value is not None}


def _template_add(args: argparse.Namespace) -> None:
    from dbqm.core.template_builder import build, validate
    from dbqm.models.template import save_templates

    if deps.find_template(args.name) is not None:
        _exit_with_errors(args, "template.add", [t("template.already_exists", name=args.name)])

    content = _resolve_content(args, "template.add")
    values = _template_values(args, content)

    errors = validate(values)
    if errors:
        _exit_with_errors(args, "template.add", errors)

    template = build(values)

    templates = deps.load_templates()
    templates.append(template)
    save_templates(templates)
    _print_template_outcome(args.format, template.name, "created")


def _template_update(args: argparse.Namespace) -> None:
    from dbqm.core.template_builder import build, validate
    from dbqm.models.template import save_templates

    existing = deps.find_template(args.name)
    if existing is None:
        _fail_or_print(args, "template.update", "not_found",
                        t("template.not_found_named", name=args.name))

    content = _resolve_content(args, "template.update")
    values = _template_values(args, content)

    # Validate the EFFECTIVE state an update would leave behind, not the
    # sparse `values` alone: a `template update NOME --description "..."`
    # must not fail validation just because --content/--content-file were
    # not repeated on this command line.
    merged = existing.to_dict()
    merged.update(values)
    errors = validate(merged)
    if errors:
        _exit_with_errors(args, "template.update", errors)

    # `build` gets the SPARSE `values`, never `merged`: `merged` always
    # carries a "content" key (copied from `existing`), and passing that to
    # `build` would be indistinguishable from the user actually repeating
    # --content on this command line -- harmless here since both reproduce
    # the same string, but it is the same trap `_query_update`'s comment
    # warns about for `table`.
    template = build(values, existing)

    templates = deps.load_templates()
    index = next(i for i, t in enumerate(templates) if t.name == template.name)
    templates[index] = template
    save_templates(templates)
    _print_template_outcome(args.format, template.name, "updated")


def _template_show(args: argparse.Namespace) -> None:
    template = deps.find_template(args.name)
    if template is None:
        _fail_or_print(args, "template.show", "not_found",
                        t("template.not_found_named", name=args.name))

    data = template.to_dict()

    if args.format == "json":
        ok("template.show", data)
        return

    table = Table(title=escape(t("template.show_title", name=template.name)))
    table.add_column(t("common.field"))
    table.add_column(t("common.value"))
    for key, value in data.items():
        table.add_row(key, escape(str(value)))
    console.print(table)


def _template_rm(args: argparse.Namespace) -> None:
    from dbqm.models.template import delete_template

    if deps.find_template(args.name) is None:
        _fail_or_print(args, "template.rm", "not_found",
                        t("template.not_found_named", name=args.name))

    if not args.yes:
        # Refuse rather than prompt when there is no terminal: a script that
        # hangs on an unanswerable question is worse than one that fails.
        if not sys.stdin.isatty():
            _fail_or_print(args, "template.rm", "usage",
                            t("common.remove_needs_yes"))
        # The prompt goes to stderr: `input(prompt)` writes it to stdout,
        # which would put prose on the stream the envelope owns.
        print(t("template.confirm_remove", name=args.name), end="",
              file=sys.stderr, flush=True)
        resposta = input().strip().lower()
        if resposta not in t("common.yes_answers").split(","):
            if args.format == "json":
                ok("template.rm", {"name": args.name, "removed": False})
            else:
                console.print(t("common.cancelled"))
            return

    delete_template(args.name)
    _print_template_outcome(args.format, args.name, "removed")


def _template_list(args: argparse.Namespace) -> None:
    items = deps.load_templates()

    if args.format == "json":
        data = [{"name": item.name, "description": item.description} for item in items]
        ok("template.list", data)
        return

    if not items:
        console.print(f'[ds.text.muted]{t("template.none_configured")}[/ds.text.muted]')
        return

    table = Table(title=t("template.list_title"))
    table.add_column(t("common.name"))
    table.add_column(t("common.description"))
    for item in items:
        desc = (item.description[:50] + "..."
                if len(item.description) > 50 else item.description)
        table.add_row(escape(item.name), escape(desc or "-"))
    console.print(table)


_TEMPLATE_SUBCOMMANDS = {
    "add": _template_add,
    "update": _template_update,
    "rm": _template_rm,
    "show": _template_show,
    "list": _template_list,
}


def cmd_template(args: argparse.Namespace) -> None:
    """Manage saved templates."""
    subcommand = getattr(args, "subcommand", None)
    handler = _TEMPLATE_SUBCOMMANDS.get(subcommand) if isinstance(subcommand, str) else None
    if handler is None:
        # A bare `dbqm template` prints the group's own help (add/update/rm/
        # show/list, with their flags) rather than a one-line reminder.
        if _template_parser is not None:
            _template_parser.print_help()
        else:
            console.print(
                f'[ds.op.failure]{t("template.usage")}[/ds.op.failure]'
            )
        sys.exit(int(exit_for("validation")))
    handler(args)
