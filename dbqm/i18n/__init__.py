"""User-facing text, in the language the user picked.

Every string a person reads — a TUI label, a CLI message, an error a script
parses the token of — comes from here. Nothing else in `dbqm/` may hold one:
`tests/design/test_i18n_policy.py` reads the source and fails on a literal
that looks like screen text, the same way the design guards fail on a literal
colour.

**English is the source language.** A key's English text is the definition of
what that string means; a translation that drifts from it is a bug in the
translation. Portuguese is a translation like any other, and keeps the
project's long-standing rule of carrying no accents.

The catalogue is a Python module, not a `.po` file compiled into a `.mo`:
there is no build step to forget, it travels inside the wheel by being
ordinary code, `mypy` reads it, and a missing key is a test failure rather
than a silent fallback at runtime.

    from dbqm.i18n import t

    t("connection.not_found", name="prod")
    # en: "Connection 'prod' not found."
    # pt: "Conexao 'prod' nao encontrada."

Placeholders are `str.format` fields, named rather than positional, because a
translation is free to reorder them and a positional `{}` cannot be reordered
without changing meaning.
"""
from __future__ import annotations

import os
from typing import Any, Final

from dbqm.i18n import en, pt

#: Every language the catalogue carries, by the code a user writes.
CATALOGUES: Final[dict[str, dict[str, str]]] = {
    "en": en.TEXTS,
    "pt": pt.TEXTS,
}

DEFAULT_LANGUAGE: Final = "en"

#: Set by `set_language`. Module state on purpose: the alternative is
#: threading a locale through every function that renders anything, and this
#: process renders for exactly one user.
_language: str = DEFAULT_LANGUAGE


class UnknownKey(KeyError):
    """A key no catalogue defines. Raised, never papered over: a string the
    user was supposed to read and did not is not a smaller bug than a crash."""


def available_languages() -> list[str]:
    return sorted(CATALOGUES)


def get_language() -> str:
    return _language


def set_language(language: str | None) -> str:
    """Switch language, returning the one now in effect.

    An unknown or empty code falls back to the default rather than raising:
    this is called with whatever is in a settings file or an environment
    variable, and a typo there should not stop the program from starting.
    """
    global _language
    _language = language if language in CATALOGUES else DEFAULT_LANGUAGE
    return _language


def resolve_language(configured: str = "") -> str:
    """The language to use, in precedence order: `DBQM_LANG`, then the
    stored setting, then the default.

    The environment wins so a script can force a language for one run —
    which is what the test suite does, and what a CI job parsing messages
    should do — without writing to the user's settings.
    """
    return set_language(os.environ.get("DBQM_LANG") or configured or DEFAULT_LANGUAGE)


def t(key: str, /, **fields: Any) -> str:
    """The text for `chave`, in the current language, with `campos` filled in.

    Falls back to English for a key the current language has not translated
    yet — an untranslated string is worth showing in English, where an empty
    one or a raw key is not. A key no catalogue has at all raises.
    """
    text = CATALOGUES[_language].get(key) or en.TEXTS.get(key)
    if text is None:
        raise UnknownKey(key)
    return text.format(**fields) if fields else text
