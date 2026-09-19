"""Design system test 2: token parity between themes.

Without it, a theme ends up with the wrong inherited colour and nobody
notices until someone complains. It is the rule from the guide: no colour
may have a single definition in one theme only.
"""
import re
from pathlib import Path

from dbqm.design.tokens import (
    SURFACES,
    THEMES,
    LIGHT_TOKENS,
    DARK_TOKENS,
    VALID_OVER,
)


def test_themes_declare_exactly_the_same_keys():
    assert set(DARK_TOKENS) == set(LIGHT_TOKENS)


def test_every_registered_theme_has_the_same_keys():
    expected = set(DARK_TOKENS)
    for name, tokens in THEMES.items():
        assert set(tokens) == expected, f"tema {name} diverge"


def test_every_token_has_an_explicit_hex_value():
    """`auto 60%` is not computable from the file; hex is."""
    for name, tokens in THEMES.items():
        for key, value in tokens.items():
            assert value.startswith("#") and len(value) == 7, f"{name}.{key}={value}"


def test_every_declared_surface_exists_as_a_token():
    for theme, tokens in THEMES.items():
        for s in SURFACES:
            assert s in tokens, f'theme {theme} does not define the surface {s}'


def test_every_text_token_declares_which_backgrounds_it_is_valid_over():
    for token in VALID_OVER:
        assert token in DARK_TOKENS, f'{token}, declared in VALID_OVER, does not exist'
        assert VALID_OVER[token], f'{token} declares no valid background'


# --------------------------------------------------------------------------
# Test 6 (of the design system): every `$x` variable used in DEFAULT_CSS
# exists.
#
# Without it, a reference to a variable that nobody defines any more breaks
# nothing visibly: Textual simply falls back to its own built-in computed
# value (e.g. `$border`), and the screen renders a colour completely
# different from the intended one with no error at all. That is exactly what
# happened in Task 2: `theme.py` stopped writing the custom "border" key into
# the variables dict, and the 5 remaining references to `$border` in
# action_bar.py/panel.py/templates_sidebar.py started resolving to Textual's
# built-in `border` (derived from the palette, not from any token) instead of
# the `borda` token that was the intention.
#
# The guard matches any assignment (module-level or class-level) of a
# triple-quoted string to an identifier, not just a literal `DEFAULT_CSS`.
# Before, only `DEFAULT_CSS = """..."""` was scanned;
# `dbqm/ui/theme.py::INERT_STATES_CSS` escaped by having another name, and a
# token rename inside it would leave `$ds-text-disabled`/`$ds-text-muted`
# silently resolving to a Textual builtin — the same `$border` failure this
# guard exists to catch.

UI_ROOT = Path(__file__).resolve().parents[2] / "dbqm" / "ui"

_DEFAULT_CSS_BLOCK = re.compile(
    r'[A-Za-z_][A-Za-z0-9_]*\s*=\s*"""(.*?)"""', re.DOTALL
)
_CSS_VARIABLE = re.compile(r'\$([a-zA-Z][a-zA-Z0-9_-]*)')

# Named Theme fields that `dbqm/ui/theme.py::_build_theme` fills in from a
# token (accent=identity, background=background, ...), plus `text-muted`, a
# variable computed by Textual itself from the foreground which never had —
# and does not need — a dedicated token. Any other name (border,
# panel-active, text-bright, text-dim, ...) is a leftover from the old theme
# and must not show up in new CSS.
DOCUMENTED_BUILTINS = frozenset({
    "primary", "secondary", "accent", "warning", "error", "success",
    "foreground", "background", "surface", "panel", "text-muted",
})


def _css_variables_used() -> set[str]:
    found_ones: set[str] = set()
    for file in sorted(UI_ROOT.rglob("*.py")):
        text = file.read_text(encoding="utf-8")
        for bloco in _DEFAULT_CSS_BLOCK.findall(text):
            for m in _CSS_VARIABLE.finditer(bloco):
                found_ones.add(m.group(1))
    return found_ones


def test_every_css_variable_is_a_token_or_a_documented_builtin():
    allowed = set(DARK_TOKENS) | DOCUMENTED_BUILTINS
    used = _css_variables_used()
    unknown = used - allowed
    assert not unknown, (
        f'DEFAULT_CSS references variable(s) that are neither a token nor a documented builtin: {sorted(unknown)}'
    )
