"""Template rules shared by the TUI and the CLI.

Validation and construction used to live inline inside
`ui/screens/template_manage.py`, where only the TUI could reach them --
`core/` must never import `ui/`. They live here now, and both front ends
call them.

The messages `validate` returns are read by a user, so they are Portuguese
without accents, like every other label in the program. They are *returned*
rather than raised: the TUI shows the first with
`notify(severity="warning")` -- asking someone to fill a field in is not a
failure -- and the CLI prints them and picks an exit code. Neither choice is
this module's business, which is why they are returned rather than raised.

`Template` is flatter than `Query` and `Group`: `name`, `description`,
`content`, `created_at`, none of them a container. Nothing here needs
`deepcopy` -- `Query.column_maps` needed it because it is a dict of dicts
that `apply_column_maps` mutates at runtime, and `Group` needed it in three
of its seven fields for the same reason. A flat string has no inner mapping
for a shallow copy to alias, so there is nothing to guard.
"""
from __future__ import annotations

from typing import Any

from dbqm.models.template import Template, load_templates, save_templates


def _text(values: dict[str, Any], key: str) -> str:
    return str(values.get(key) or "").strip()


def validate(values: dict[str, Any]) -> list[str]:
    """Every problem with `values`, as user-facing messages. Empty means valid.

    Wording matches `template_manage.py`'s `TemplateEditModal._save` byte for
    byte, in the same order (name before content): that modal is what users
    read today, so this module was made to agree with it, not the other way
    round.
    """
    errors: list[str] = []

    if not _text(values, "name"):
        errors.append("Informe o nome do template.")

    if not _text(values, "content"):
        errors.append("O conteudo do template nao pode estar vazio.")

    return errors


def build(values: dict[str, Any], existing: Template | None = None) -> Template:
    """A `Template` from raw form/CLI values. Assumes `validate` passed.

    Never mutates `existing`; starts from it when given and overlays only
    the keys `values` actually sets. That is the whole point of this
    function: a CLI `update --description` must not erase `content`, and a
    TUI edit (which never touches `name`) must not erase it either.
    `created_at` is carried over, never regenerated.

    `content` is the one field this module treats differently from `name`
    and `description`: it is carried through verbatim, never `.strip()`-ed.
    Leading/trailing whitespace inside a report template's body is
    meaningful formatting (a blank line between sections), not incidental
    input noise the way it is for a name or a one-line description --
    `validate` still treats an all-whitespace value as empty, via `_text`,
    for the emptiness check alone.
    """

    def _carry(key: str, default: str = "") -> str:
        if key in values:
            return _text(values, key)
        return getattr(existing, key) if existing is not None else default

    name = _carry("name")
    description = _carry("description")

    if "content" in values:
        raw = values["content"]
        content = str(raw) if raw is not None else ""
    elif existing is not None:
        content = existing.content
    else:
        content = ""

    template = Template(name=name, description=description, content=content)
    if existing is not None:
        template.created_at = existing.created_at
    return template


def upsert(values: dict[str, Any]) -> tuple[Template, bool]:
    """Save `values`, creating or replacing by name. Returns (template, created).

    Kept for symmetry with `connection_builder`, where the TUI's Salvar
    button really does mean "save this, new or not". Nothing calls it here --
    the screen builds directly, and the CLI must not: there,
    `add` on an existing name and `update` on a missing one have to be
    errors, so the command checks first and calls `build` itself.
    """
    templates = load_templates()
    name = _text(values, "name")
    index = next((i for i, t in enumerate(templates) if t.name == name), None)
    existing = templates[index] if index is not None else None
    template = build(values, existing)
    if index is None:
        templates.append(template)
    else:
        templates[index] = template
    save_templates(templates)
    return template, index is None
