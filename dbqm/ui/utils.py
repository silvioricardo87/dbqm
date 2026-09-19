"""UI utility functions."""
import re
import unicodedata

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Select


class NavSelect(Select[str | None]):
    """Select widget that opens only with Enter/Space, not arrows.

    This allows arrow keys to navigate between widgets in form screens
    instead of opening the dropdown.
    """

    BINDINGS = [
        Binding("enter,space", "show_overlay", "Show menu", show=False),
    ]


class NavVerticalScroll(VerticalScroll):
    """VerticalScroll that doesn't consume arrow keys.

    Allows arrow keys to navigate between child widgets instead of scrolling.
    Scrolling is still possible via PageUp/PageDown and mouse wheel.
    """

    can_focus = False

    BINDINGS = [
        # Keep page navigation but remove arrow key scrolling
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
        Binding("home", "scroll_home", "Home", show=False),
        Binding("end", "scroll_end", "End", show=False),
    ]


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


def common_folder_prefix(folders: list[str]) -> str:
    """The longest run of leading "/"-separated segments shared by ALL the
    folders given, trailing slash included — "" when there are fewer than two
    folders, or when no leading segment is common to all of them.

    Used to decide whether a folder's label in a Select may elide the prefix
    (e.g. "Mapfre Sustentacao/Faturamento" -> "Faturamento"). It is computed
    on every call, against the real folders, never against a literal pinned in
    the code. That matters because the redundancy only exists while ONE family
    of folders dominates the whole list — the day a second family (another
    prefix) appears beside the first, the prefix common to ALL of them shrinks
    (typically to "") on its own, and the list goes back to showing the full
    path with no code change. Pinning the literal "Mapfre Sustentacao/" would
    do the opposite: buy width today and hide information the day it stopped
    being true.
    """
    if len(folders) < 2:
        return ""
    segments = [p.split("/") for p in folders]
    common: list[str] = []
    for group in zip(*segments, strict=False):
        if len(set(group)) == 1:
            common.append(group[0])
        else:
            break
    return "/".join(common) + "/" if common else ""
