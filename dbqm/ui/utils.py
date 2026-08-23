"""UI utility functions."""
import re
import unicodedata

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Select


class NavSelect(Select):
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


def prefixo_comum_de_pastas(pastas: list[str]) -> str:
    """Maior prefixo de segmentos (separados por "/") compartilhado por
    TODAS as pastas dadas, incluindo a barra final — "" se houver menos de
    duas pastas ou se nenhum segmento inicial for comum a todas.

    Usado para decidir se o rotulo de uma pasta num Select pode elidir o
    prefixo (ex.: "Mapfre Sustentacao/Faturamento" -> "Faturamento"): o
    calculo e feito a cada chamada, contra as pastas reais, nao contra um
    literal fixado no codigo. Isso importa porque a redundancia so existe
    enquanto UMA familia de pastas domina a lista inteira — no dia em que
    uma segunda familia (outro prefixo) aparecer ao lado da primeira, o
    prefixo comum a TODAS encolhe (tipicamente pra "") sozinho, e a lista
    volta a mostrar o caminho inteiro sem precisar de uma mudanca de
    codigo. Fixar o literal "Mapfre Sustentacao/" faria o oposto: ganharia
    largura hoje e esconderia informacao no dia em que deixasse de ser
    verdade.
    """
    if len(pastas) < 2:
        return ""
    segmentos = [p.split("/") for p in pastas]
    comuns: list[str] = []
    for grupo in zip(*segmentos):
        if len(set(grupo)) == 1:
            comuns.append(grupo[0])
        else:
            break
    return "/".join(comuns) + "/" if comuns else ""
