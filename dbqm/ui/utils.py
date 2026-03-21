"""UI utility functions."""
import re
import unicodedata


def sanitize_id(text: str) -> str:
    """Convert arbitrary text to a valid Textual widget ID.

    Textual IDs only allow letters, numbers, underscores, and hyphens,
    and must not begin with a number.
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    result = re.sub(r"[^a-zA-Z0-9_-]", "-", ascii_only.lower())
    result = re.sub(r"-+", "-", result).strip("-")
    if not result or result[0].isdigit():
        result = "id-" + result
    return result or "item"


def escape_markup(text: str) -> str:
    """Escape Rich markup characters in user text."""
    return text.replace("[", "\\[").replace("]", "\\]")
