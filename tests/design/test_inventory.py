"""Design system test 4: component inventory.

Fails when a second component with the same function shows up, and when the
chrome that Dialog delivers goes back to being hand-written.

The verdict already has a guard of its own in
`tests/ui/test_widgets.py::test_no_hand_rolled_verdict_markup_outside_the_component`
— not duplicated here.
"""
import re
from pathlib import Path

from dbqm.i18n import en

ROOT = Path(__file__).resolve().parents[2] / "dbqm"

# ---------------------------------------------------------------------------
# "No X" hand-written instead of EmptyState
# ---------------------------------------------------------------------------
#
# What matters is an empty-list sentence inside a Static(...)/add_row(...)/
# update(...) call — and those calls may span several lines, so the scan has
# to be multi-line (balanced parentheses over the whole text of the file, not
# line by line). A naive scan already let 4 cases hidden that way slip
# through.
#
# Since the catalogue, the call carries a KEY and the sentence lives in
# `dbqm/i18n/en.py`. Reading the call text alone found nothing and the test
# passed for having nothing to look at, which is worse than failing. The key
# is resolved here and it is the resolved TEXT that is examined.
_CALL = re.compile(r"\b(?:Static|add_row|update)\s*\(")
_KEY = re.compile(r"""t\(\s*["']([\w.]+)["']""")
#: The sentence itself, from the first word: "No object found."
_EMPTY_TEXT = re.compile(r"^\s*(?:No|None|Nothing|Nenhum[a-z]*)\b", re.I)
#: The same sentence written straight into the call, where it starts
#: after a quote and possibly after markup: `Static("[dim]No object ...")`.
_EMPTY_LITERAL = re.compile(r"""['"](?:\[[^]]*])?\s*(?:No|Nothing|Nenhum[a-z]*)\b""", re.I)


def _says_nothing_is_here(call: str) -> bool:
    """Whether the call paints a "there is nothing here" sentence.

    Both spellings are accepted: the key's text for a call that went
    through the catalogue, and a bare literal for one that never did.
    """
    if _EMPTY_LITERAL.search(call):
        return True
    return any(_EMPTY_TEXT.search(en.TEXTS.get(key, ""))
               for key in _KEY.findall(call))

# Exemptions: "Nenhum X" inside a watched call that is NOT a list empty
# state — these are status readouts of a single field, with no possible
# "create the first one". Exempted with the reason, so nobody "fixes" them back.
EMPTY_STATE_EXEMPT = {
    # history.py: "Nenhum registro selecionado" is the nothing-selected
    # placeholder of the detail panel — it shows up even with the table
    # full of rows, when none is highlighted. There is no "create the first
    # one" for "highlight a row"; EmptyState does not apply.
    "dbqm/ui/screens/history.py",
    # settings.py: "Client in use: none found" is a configuration status
    # readout (which Instant Client is active), one field among several on
    # the Settings screen — not an empty list with an action to create the
    # first item.
    "dbqm/ui/screens/settings.py",
    # exec_routine.py: "No input parameters" describes the SIGNATURE of the
    # routine the user just picked. There is no first parameter to create;
    # the routine takes none, and the Run button is mounted right below it.
    "dbqm/ui/screens/exec_routine.py",
    # oracle_clients.py: the "no packages catalogued for this platform"
    # row states a fact about the platform, not an empty list of the
    # user's own things. Nothing the user can do here creates a package.
    "dbqm/ui/screens/oracle_clients.py",
}


def _watched_calls(text: str):
    """Yields `(position, call_text)` for each Static(/add_row(/update(
    in the file, with balanced parentheses — multi-line by construction,
    because the balancing walks the whole text without stopping at a line
    break."""
    for m in _CALL.finditer(text):
        parens_start = m.end() - 1
        depth = 0
        end = None
        for i in range(parens_start, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is not None:
            yield m.start(), text[m.start() : end + 1]


def test_empty_state_is_not_hand_written():
    """A loose "No X" in Static/add_row/update is the antipattern that
    EmptyState solves."""
    outside = []
    for file in sorted((ROOT / "ui").rglob("*.py")):
        if file.name == "empty_state.py":
            continue
        text = file.read_text(encoding="utf-8")
        rel = file.relative_to(ROOT.parent).as_posix()
        for pos, call in _watched_calls(text):
            if not _says_nothing_is_here(call):
                continue
            if rel in EMPTY_STATE_EXEMPT:
                continue
            line = text.count("\n", 0, pos) + 1
            outside.append(f"{rel}:{line}")
    assert not outside, f"an empty state written by hand in: {outside}"


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
    outside = []
    for file in sorted(ROOT.rglob("*.py")):
        if file.name == "dialog.py":
            continue
        text = file.read_text(encoding="utf-8")
        if "border: thick" in text:
            outside.append(file.relative_to(ROOT.parent).as_posix())
    assert not outside, f"the dialog frame written by hand in: {outside}"


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
    outside = []
    for file in sorted(ROOT.rglob("*.py")):
        if file.name == "skeleton.py":
            continue
        text = file.read_text(encoding="utf-8")
        if "$ds-surface-raised" in text:
            outside.append(file.relative_to(ROOT.parent).as_posix())
    assert not outside, f"bloco de esqueleto escrito a mao em: {outside}"
