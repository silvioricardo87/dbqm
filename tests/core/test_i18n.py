"""The catalogue's behaviour: lookup, fallback, and who decides the language."""
from __future__ import annotations

import pytest

from dbqm.i18n import (
    DEFAULT_LANGUAGE,
    UnknownKey,
    available_languages,
    get_language,
    resolve_language,
    set_language,
    t,
)


@pytest.fixture(autouse=True)
def _restore_the_language():
    """Module state, so every test puts it back. A test that leaked a
    language would change what the next one reads."""
    previous = get_language()
    yield
    set_language(previous)


class TestLookup:
    def test_it_renders_the_source_language_by_default(self):
        set_language("en")
        assert t("connection.name_required") == "Name is required."

    def test_it_renders_a_translation(self):
        set_language("pt")
        assert t("connection.name_required") == "Nome obrigatorio."

    def test_placeholders_are_filled_by_name(self):
        set_language("en")
        assert t("read_only.refused", name="prod") == (
            "Connection 'prod' is read-only. Use --force-write to send it anyway."
        )

    def test_the_same_key_in_two_languages_keeps_the_value(self):
        """The sentence changes; what was interpolated into it does not."""
        set_language("en")
        english = t("read_only.refused", name="prod")
        set_language("pt")
        portuguese = t("read_only.refused", name="prod")
        assert english != portuguese
        assert "'prod'" in english and "'prod'" in portuguese

    def test_a_key_nobody_defines_raises(self):
        """Not an empty string and not the key itself: a string the user was
        meant to read and did not is a bug worth stopping for."""
        with pytest.raises(UnknownKey):
            t("does.not.exist")


class TestFallback:
    def test_an_untranslated_key_falls_back_to_english(self, monkeypatch):
        from dbqm.i18n import CATALOGUES

        monkeypatch.setitem(CATALOGUES, "xx", {})
        set_language("xx")
        assert t("connection.name_required") == "Name is required."

    def test_a_language_nobody_has_falls_back_to_the_default(self):
        assert set_language("klingon") == DEFAULT_LANGUAGE
        assert get_language() == DEFAULT_LANGUAGE

    def test_none_falls_back_to_the_default(self):
        assert set_language(None) == DEFAULT_LANGUAGE


class TestWhoDecides:
    def test_the_environment_wins_over_the_setting(self, monkeypatch):
        """A script forcing a language for one run must not have to write to
        the user's settings file to do it."""
        monkeypatch.setenv("DBQM_LANG", "pt")
        assert resolve_language("en") == "pt"

    def test_the_setting_is_used_when_the_environment_is_silent(self, monkeypatch):
        monkeypatch.delenv("DBQM_LANG", raising=False)
        assert resolve_language("pt") == "pt"

    def test_nothing_configured_means_the_default(self, monkeypatch):
        monkeypatch.delenv("DBQM_LANG", raising=False)
        assert resolve_language("") == DEFAULT_LANGUAGE

    def test_an_unusable_environment_value_does_not_stop_the_program(self, monkeypatch):
        monkeypatch.setenv("DBQM_LANG", "does-not-exist")
        assert resolve_language("pt") == DEFAULT_LANGUAGE


def test_the_languages_it_offers_are_the_ones_it_has():
    from dbqm.i18n import CATALOGUES

    assert available_languages() == sorted(CATALOGUES)
    assert DEFAULT_LANGUAGE in available_languages()
