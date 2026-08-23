"""Design system test 4: component inventory.

Fails when a second component with the same function shows up, and when the
chrome that Dialog delivers goes back to being hand-written.

The verdict already has a guard of its own in
`tests/ui/test_widgets.py::test_no_hand_rolled_verdict_markup_outside_the_component`
— not duplicated here.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "dbqm"

# ---------------------------------------------------------------------------
# "Nenhum X" hand-written instead of EmptyState
# ---------------------------------------------------------------------------
#
# A line-by-line grep for "Nenhum"/"Nenhuma" produces false positives: the
# word legitimately shows up in prose (docstrings, notification texts, the
# button label "Nenhum (remover)"). What matters is the word inside a
# Static(...)/add_row(...)/update(...) call — and those calls may span
# several lines, so the scan has to be multi-line (balanced parentheses over
# the whole text of the file, not line by line). A naive scan already let 4
# cases hidden that way slip through.
_CHAMADA = re.compile(r"\b(?:Static|add_row|update)\s*\(")
_PALAVRA_VAZIO = re.compile(r"Nenhum[a-z]*", re.I | re.S)

# Exemptions: "Nenhum X" inside a watched call that is NOT a list empty
# state — these are status readouts of a single field, with no possible
# "create the first one". Exempted with the reason, so nobody "fixes" them back.
ISENCOES_ESTADO_VAZIO = {
    # history.py: "Nenhum registro selecionado" is the nothing-selected
    # placeholder of the detail panel — it shows up even with the table
    # full of rows, when none is highlighted. There is no "create the first
    # one" for "highlight a row"; EmptyState does not apply.
    "dbqm/ui/screens/history.py",
    # settings.py: "Client em uso: nenhum encontrado" is a configuration
    # status readout (which Instant Client is active), one field among
    # several on the Settings screen — not an empty list with an action to
    # create the first item.
    "dbqm/ui/screens/settings.py",
}


def _watched_calls(text: str):
    """Yields `(position, call_text)` for each Static(/add_row(/update(
    in the file, with balanced parentheses — multi-line by construction,
    because the balancing walks the whole text without stopping at a line
    break."""
    for m in _CHAMADA.finditer(text):
        inicio_parens = m.end() - 1
        profundidade = 0
        fim = None
        for i in range(inicio_parens, len(text)):
            if text[i] == "(":
                profundidade += 1
            elif text[i] == ")":
                profundidade -= 1
                if profundidade == 0:
                    fim = i
                    break
        if fim is not None:
            yield m.start(), text[m.start() : fim + 1]


def test_empty_state_is_not_hand_written():
    """A loose "Nenhum X" in Static/add_row/update is the antipattern that
    EmptyState solves."""
    fora = []
    for arquivo in sorted((ROOT / "ui").rglob("*.py")):
        if arquivo.name == "empty_state.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        rel = arquivo.relative_to(ROOT.parent).as_posix()
        for pos, chamada in _watched_calls(texto):
            if not _PALAVRA_VAZIO.search(chamada):
                continue
            if rel in ISENCOES_ESTADO_VAZIO:
                continue
            linha = texto.count("\n", 0, pos) + 1
            fora.append(f"{rel}:{linha}")
    assert not fora, f"estado vazio escrito a mao em: {fora}"


# ---------------------------------------------------------------------------
# Dialog frame (`border: thick`) hand-written outside Dialog
# ---------------------------------------------------------------------------
#
# `dialog.py` is the only excluded file: there, "border: thick" shows up both
# in the real DEFAULT_CSS (which is the legitimate owner of that frame now)
# and in the docstring that explains why the component exists. Excluding the
# whole file covers both occurrences at once, without having to tell CSS
# from prose.


def test_dialog_frame_exists_in_a_single_place():
    fora = []
    for arquivo in sorted(ROOT.rglob("*.py")):
        if arquivo.name == "dialog.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "border: thick" in texto:
            fora.append(arquivo.relative_to(ROOT.parent).as_posix())
    assert not fora, f"moldura de dialog escrita a mao em: {fora}"


# ---------------------------------------------------------------------------
# Skeleton block (`$ds-surface-raised` as background) hand-written
# ---------------------------------------------------------------------------
#
# `Skeleton` was the only one of the four shared components with no guard
# whatsoever — the three screens that use it (`browser`, `group_exec`,
# `query_exec`) import it today, but nothing stopped a fourth one from
# repeating the grid of blocks by hand.
#
# The watched mark is the block's BACKGROUND: `$ds-surface-raised` is a token
# that in `dbqm/ui/` has a single use — painting the skeleton's ghost cell.
# Same bet as the `Dialog` frame guard, which watches `border: thick`:
# whoever repeats a component repeats it by copying its CSS.
#
# KNOWN LIMITS (what this guard does NOT see):
# - A hand-made skeleton that picks ANOTHER background token (e.g. `$ds-panel`)
#   or that draws the blocks with a glyph (`Static("░░░░")`) instead of a
#   background goes straight through. The guard closes the copy-paste path,
#   not the reinvention one.
# - It does not look at the HTML (`core/html_report.py` uses the form
#   `var(--ds-surface-raised)`, which is another language and another
#   consumer).


def test_skeleton_block_exists_in_a_single_place():
    fora = []
    for arquivo in sorted(ROOT.rglob("*.py")):
        if arquivo.name == "skeleton.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "$ds-surface-raised" in texto:
            fora.append(arquivo.relative_to(ROOT.parent).as_posix())
    assert not fora, f"bloco de esqueleto escrito a mao em: {fora}"
