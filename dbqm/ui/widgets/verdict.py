"""Verdict and operation-status markers.

These are two different axes and they do not share a palette: DIFERE is not a
warning and AUSENTE is not an error. Each marker carries a glyph besides the
color, so that the state does not depend on the reader telling shades apart.

Closed on purpose, in the same spirit as `dialog.py`: whoever needs a state
that is not here needs a new variant in this module, never markup assembled by
hand in another file — that is why `mark_verdict` and `mark_operation` reject
any input outside their own vocabulary. The whole axis (`$ds-verdict-*`/
`$ds-op-failure` outside of here) is watched by
`tests/ui/test_widgets.py::test_no_hand_rolled_verdict_markup_outside_the_component`.
"""
from __future__ import annotations

from dbqm.ui.utils import escape_markup

VERDICTS: dict[str, tuple[str, str]] = {
    # status -> (glyph, token)
    "match": ("=", "$ds-verdict-match"),
    "match-normalized": ("~", "$ds-verdict-match"),
    "diff": ("!", "$ds-verdict-diff"),
    "absent": ("-", "$ds-verdict-absent"),
}

OPERATIONS: dict[str, tuple[str, str]] = {
    # state -> (glyph, token); an empty token ("") means "no color, weight only"
    "ok": ("", ""),
    "failure": ("x", "$ds-op-failure"),
    "running": ("*", "$ds-identity"),
}


def mark_verdict(status: str, *, label: str | None = None) -> str:
    """Markup for the comparison verdict, with glyph and color.

    `match` (OK) uses the same `ds-text-muted` token on purpose: an equal
    result carries no alarm at all, only the glyph confirms the state.

    `label`, if passed, swaps only the LABEL — glyph and token still come
    from `VERDICTS`, closed. It exists for the caller that already has its
    own word for the state (`"Iguais:"`, `"DIVERGENTE"`, ...) and needs to
    paint it without duplicating the component's default label next to it.
    It does not expose the token itself — only the component knows which
    token goes with which status, so the color never comes loose from the
    state it represents. `label` is always escaped before entering the
    markup: the parameter exists for a label, never to inject new markup,
    and no caller today passes anything beyond a fixed literal — but
    nothing stops a future caller from passing text coming from data, and a
    `[/]`/token in there would close the tag too early.
    """
    if status not in VERDICTS:
        raise ValueError(f"status desconhecido: {status!r}; use {sorted(VERDICTS)}")
    glyph, token = VERDICTS[status]
    text = escape_markup(label) if label is not None else {
        "match": "OK",
        "match-normalized": "OK*",
        "diff": "DIFERE",
        "absent": "AUSENTE",
    }[status]
    return f"[{token}]{glyph} {text}[/]"


def mark_operation(state: str, *, label: str | None = None) -> str:
    """Markup for the status of an operation (query/group execution).

    `ok` comes out with no alarm ink — success is the absence of alarm, only
    `failure` gets an error color — but it keeps the WEIGHT (`[bold]`): no
    color is not no legibility. The same rule the manual call sites in
    `adhoc.py`, `exec_routine.py` and `package_editor.py` already apply with
    `[bold]` pinned next to the success text. `running` gets the identity
    color, to tell "in progress" apart from "result".

    `label`, if passed, swaps only the LABEL (same reason and same escaping
    as `mark_verdict`).
    """
    if state not in OPERATIONS:
        raise ValueError(f"estado desconhecido: {state!r}; use {sorted(OPERATIONS)}")
    glyph, token = OPERATIONS[state]
    text = escape_markup(label) if label is not None else {
        "ok": "OK", "failure": "FALHA", "running": "executando",
    }[state]
    body = f"{(glyph + ' ') if glyph else ''}{text}"
    if not token:
        return f"[bold]{body}[/]"
    return f"[{token}]{body}[/]"
