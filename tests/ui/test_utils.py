"""Tests for UI utilities."""
from dbqm.ui.utils import sanitize_id, escape_markup, common_folder_prefix


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


# ---------------------------------------------------------------------------
# common_folder_prefix
# ---------------------------------------------------------------------------
#
# It existed with no test at all: every folder used in the UI suite was
# prefix-free ("Grupo A", "FolderA", "Pasta0") and none contained "/", so the
# elision branch never ran — replacing the function body with `return ""`
# kept 326 tests green. These cases, plus the screen test that reads the
# painted LABEL, are what kills that mutant.


def test_common_folder_prefix_single_family():
    """The case that motivated the function: one family dominates the whole
    list."""
    assert common_folder_prefix([
        "Mapfre Sustentacao/Faturamento",
        "Mapfre Sustentacao/Apolice",
    ]) == "Mapfre Sustentacao/"


def test_common_folder_prefix_several_segments():
    """The prefix grows segment by segment, it does not stop at the first."""
    assert common_folder_prefix(["A/B/C", "A/B/D"]) == "A/B/"


def test_common_folder_prefix_nothing_in_common():
    """Two families side by side: the common prefix shrinks on its own to ""
    and the list goes back to showing the whole path — the reason the prefix
    is computed on every load instead of being hardcoded as a literal."""
    assert common_folder_prefix(["Mapfre/Faturamento", "Interno/Backlog"]) == ""


def test_common_folder_prefix_compares_segments_not_characters():
    """"Fatura" is a prefix of "Faturamento" in characters, but not in
    segments — eliding here would cut off the start of a folder name."""
    assert common_folder_prefix(["Faturamento", "Fatura"]) == ""


def test_common_folder_prefix_fewer_than_two():
    """With zero or one folder there is no redundancy to remove: the list's
    only label has to show up in full."""
    assert common_folder_prefix([]) == ""
    assert common_folder_prefix(["Mapfre Sustentacao/Faturamento"]) == ""


def test_common_folder_prefix_folder_that_prefixes_its_sibling():
    """Sibling case: one folder IS the common prefix of the other.

    The returned prefix ("A/B/") does not apply to "A/B" itself — the caller
    has to check `startswith` before cutting, and that is what stops "A/B"'s
    label from turning into an empty string. The function returns the
    correct prefix; the caller's `startswith`
    (query_exec.py/group_run.py) is load-bearing, not defensive."""
    assert common_folder_prefix(["A/B", "A/B/C"]) == "A/B/"


def test_common_folder_prefix_repeated_list_would_return_everything():
    """Behaviour pinned down, not endorsed: with the SAME folder repeated the
    common prefix is the whole of it, and cutting that would erase the label.

    There is no guard against this inside the function on purpose — the two
    callers pass `sorted(Counter(...))`, that is, dictionary keys, which are
    unique by construction. With unique entries, the only way for the prefix
    to cover a whole folder is the sibling case above, where the caller's
    `startswith` already saves the label. This test exists so that, if a
    third caller one day passes a list with repetitions, the consequence is
    written down here instead of showing up as a list of blank labels."""
    assert common_folder_prefix(["A/B", "A/B"]) == "A/B/"
