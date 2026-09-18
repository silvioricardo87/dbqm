"""Group rules shared by the TUI and the CLI.

Validation and the merge-preserving construction used to live inside
`ui/screens/group_manage.py`, where only the TUI could reach them --
`core/` must never import `ui/`. They live here now, and both front ends
call them.

The messages `validate` returns are read by a user, so they are Portuguese
without accents, like every other label in the program. They are *returned*
rather than raised: the TUI shows them with `notify(severity="warning")`
(matching what `group_manage.py` did before this moved) and the CLI prints
them and picks an exit code, and that choice is not this module's business.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from dbqm.i18n import t
from dbqm.models.group import Group, load_groups, save_groups
from dbqm.models.query import find_query


def _text(values: dict[str, Any], key: str) -> str:
    return str(values.get(key) or "").strip()


def validate(values: dict[str, Any]) -> list[str]:
    """Every problem with `values`, as user-facing messages. Empty means valid.

    Wording matches `group_manage.py`'s `GroupCreateModal._save` byte for
    byte: that screen is what users read today, so this module was made to
    agree with it, not the other way round. The per-query existence check is
    new here -- the TUI's `SelectionList` only ever offers queries that
    exist, so it never needed one, but a CLI `--query` is free text.
    """
    errors: list[str] = []

    if not _text(values, "name"):
        errors.append(t("group.name_required"))

    queries = values.get("queries") or []
    if len(queries) < 2:
        errors.append(t("group.two_queries_required"))
    else:
        # Only when the count is right: "needs two queries" and "this one does
        # not exist" are one mistake reported twice otherwise, and `-f json`
        # joins them with "; ". `query_builder` chains the same way.
        for qname in queries:
            if qname and find_query(qname) is None:
                errors.append(t("group.query_not_found", nome=qname))
        # Distinct, not merely two: `run_comparison` keys its index by query
        # name, so the same name twice collapses to one side and the
        # comparison can only ever report agreement -- with itself. `multi`
        # refuses the same shape for a repeated `-c`.
        repetidas = sorted({q for q in queries if queries.count(q) > 1})
        if repetidas:
            errors.append(t("group.query_repeated", nome=repetidas[0]))

    if not _text(values, "join_key"):
        errors.append(t("group.join_key_required"))

    return errors


def build(values: dict[str, Any], existing: Group | None = None) -> Group:
    """A `Group` from raw form/CLI values. Assumes `validate` passed.

    Never mutates `existing`; starts from it when given and overlays only
    the keys `values` actually sets. That is the whole point of this
    function: a CLI `update --description` must not erase `column_mapping`,
    `normalize`, `template`, `template_fields`, `validation_rule`, `folder`,
    `adhoc_sql` or `connections` -- anything the TUI authored that this call
    never mentions. `created_at` is carried over, never regenerated.
    """

    def _carry(key: str, default: str = "") -> str:
        if key in values:
            return _text(values, key)
        return getattr(existing, key) if existing is not None else default

    def _carry_list(key: str) -> list[str]:
        # `queries`, `compare_columns` and `connections` are flat lists of
        # names -- the strings themselves are immutable, so a plain copy of
        # the list (not the strings) is all aliasing needs.
        if key in values:
            return list(values[key]) if values[key] else []
        if existing is not None:
            return list(getattr(existing, key))
        return []

    def _carry_dict(key: str) -> dict[str, Any]:
        # `shared_params`, `column_mapping` and `normalize` are dicts of
        # dicts (a param's {description, default}; a column's per-query or
        # per-value mapping) -- a shallow `dict(...)` would still alias the
        # inner mappings between `existing` and the built `Group`, so this
        # needs `deepcopy`, the same fix Task 1 made for `Query.column_maps`.
        if key in values:
            return deepcopy(values[key]) if values[key] else {}
        if existing is not None:
            return deepcopy(getattr(existing, key))
        return {}

    name = _carry("name")
    description = _carry("description")
    join_key = _carry("join_key")
    folder = _carry("folder")
    template = _carry("template")
    validation_rule = _carry("validation_rule", "all_equal")
    adhoc_sql = _carry("adhoc_sql")

    queries = _carry_list("queries")
    compare_columns = _carry_list("compare_columns")
    connections = _carry_list("connections")

    shared_params = _carry_dict("shared_params")
    column_mapping = _carry_dict("column_mapping")
    normalize = _carry_dict("normalize")

    # `template_fields` maps a placeholder name to a source *expression*
    # (a flat string, like `column_maps`' outer level) -- nothing nested, so
    # a shallow copy is correct and nothing here needs `deepcopy`.
    if "template_fields" in values:
        template_fields = dict(values["template_fields"]) if values["template_fields"] else {}
    elif existing is not None:
        template_fields = dict(existing.template_fields)
    else:
        template_fields = {}

    group = Group(
        name=name,
        description=description,
        queries=queries,
        join_key=join_key,
        compare_columns=compare_columns,
        shared_params=shared_params,
        column_mapping=column_mapping,
        normalize=normalize,
        validation_rule=validation_rule,
        folder=folder,
        template=template,
        template_fields=template_fields,
        adhoc_sql=adhoc_sql,
        connections=connections,
    )
    if existing is not None:
        group.created_at = existing.created_at
    return group


def upsert(values: dict[str, Any]) -> tuple[Group, bool]:
    """Save `values`, creating or replacing by name. Returns (group, created).

    This is what the TUI's Salvar means. The CLI does NOT use it: there,
    `add` on an existing name and `update` on a missing one have to be
    errors, so the command checks first and calls `build` itself.
    """
    groups = load_groups()
    name = _text(values, "name")
    index = next((i for i, g in enumerate(groups) if g.name == name), None)
    existing = groups[index] if index is not None else None
    group = build(values, existing)
    if index is None:
        groups.append(group)
    else:
        groups[index] = group
    save_groups(groups)
    return group, index is None
