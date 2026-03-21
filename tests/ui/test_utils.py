"""Tests for UI utilities."""
from dbqm.ui.utils import sanitize_id, escape_markup


def test_sanitize_id_ascii():
    assert sanitize_id("hello-world") == "hello-world"


def test_sanitize_id_accents():
    assert sanitize_id("investigacao-apolice") == "investigacao-apolice"


def test_sanitize_id_accents_unicode():
    result = sanitize_id("investigacao-apolice")
    assert result == "investigacao-apolice"


def test_sanitize_id_spaces():
    assert sanitize_id("my folder name") == "my-folder-name"


def test_sanitize_id_special_chars():
    assert sanitize_id("test@#$%^&*()") == "test"


def test_sanitize_id_starts_with_number():
    assert sanitize_id("123abc").startswith("id-")


def test_sanitize_id_empty():
    result = sanitize_id("")
    assert result  # should not be empty


def test_sanitize_id_unicode_only():
    result = sanitize_id("\u65e5\u672c\u8a9e")
    assert result  # should not be empty, fallback to "item" or "id-"


def test_sanitize_id_cedilla():
    assert "c" in sanitize_id("a\u00e7\u00e3o")


def test_sanitize_id_tilde():
    assert sanitize_id("n\u00e3o") == "nao"


def test_sanitize_id_accented_folder():
    """Accented folder names should produce valid IDs."""
    result = sanitize_id("Investiga\u00e7\u00e3o")
    assert result  # not empty
    assert all(c.isalnum() or c in "-_" for c in result)
    # Should not start with a digit
    assert not result[0].isdigit()


def test_sanitize_id_slash_and_space():
    """Slashes and spaces should be converted to hyphens."""
    result = sanitize_id("folder/sub folder")
    assert " " not in result
    assert "/" not in result


def test_escape_markup_brackets():
    assert escape_markup("test[bold]") == "test\\[bold\\]"


def test_escape_markup_clean():
    assert escape_markup("hello") == "hello"


def test_escape_markup_nested():
    assert escape_markup("[red]error[/]") == "\\[red\\]error\\[/\\]"
