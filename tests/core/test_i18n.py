"""The catalogue's behaviour: lookup, fallback, and who decides the language."""
from __future__ import annotations

import pytest

from dbqm.i18n import (
    IDIOMA_PADRAO,
    UnknownKey,
    available_languages,
    get_language,
    resolve_language,
    set_language,
    t,
)


@pytest.fixture(autouse=True)
def _restaurar_idioma():
    """Module state, so every test puts it back. A test that leaked a
    language would change what the next one reads."""
    anterior = get_language()
    yield
    set_language(anterior)


class TestLookup:
    def test_it_renders_the_source_language_by_default(self):
        set_language("en")
        assert t("connection.name_required") == "Name is required."

    def test_it_renders_a_translation(self):
        set_language("pt")
        assert t("connection.name_required") == "Nome obrigatorio."

    def test_placeholders_are_filled_by_name(self):
        set_language("en")
        assert t("read_only.refused", nome="prod") == (
            "Connection 'prod' is read-only. Use --force-write to send it anyway."
        )

    def test_the_same_key_in_two_languages_keeps_the_value(self):
        """The sentence changes; what was interpolated into it does not."""
        set_language("en")
        ingles = t("read_only.refused", nome="prod")
        set_language("pt")
        portugues = t("read_only.refused", nome="prod")
        assert ingles != portugues
        assert "'prod'" in ingles and "'prod'" in portugues

    def test_a_key_nobody_defines_raises(self):
        """Not an empty string and not the key itself: a string the user was
        meant to read and did not is a bug worth stopping for."""
        with pytest.raises(UnknownKey):
            t("nao.existe")


class TestFallback:
    def test_an_untranslated_key_falls_back_to_english(self, monkeypatch):
        from dbqm.i18n import CATALOGOS

        monkeypatch.setitem(CATALOGOS, "xx", {})
        set_language("xx")
        assert t("connection.name_required") == "Name is required."

    def test_a_language_nobody_has_falls_back_to_the_default(self):
        assert set_language("klingon") == IDIOMA_PADRAO
        assert get_language() == IDIOMA_PADRAO

    def test_none_falls_back_to_the_default(self):
        assert set_language(None) == IDIOMA_PADRAO


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
        assert resolve_language("") == IDIOMA_PADRAO

    def test_an_unusable_environment_value_does_not_stop_the_program(self, monkeypatch):
        monkeypatch.setenv("DBQM_LANG", "nao-existe")
        assert resolve_language("pt") == IDIOMA_PADRAO


def test_the_languages_it_offers_are_the_ones_it_has():
    from dbqm.i18n import CATALOGOS

    assert available_languages() == sorted(CATALOGOS)
    assert IDIOMA_PADRAO in available_languages()
