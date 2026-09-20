"""Guards of the layout grammar (phase 2).

Phase 1 watched **color**; this one watches **structure**. The first
guard: `Panel` (and `Dialog`, its modal equivalent) is the product's only
section frame. A screen that draws its own box creates a third frame
vocabulary — that is exactly how the product got to three.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

# Anchored on the file, not on the cwd: `Path("dbqm/ui")` scans zero files
# when pytest runs from another directory and the test passes in silence.
# Same idiom as `tests/design/_scan.py` and `test_inventory.py`.
UI_ROOT = Path(__file__).resolve().parents[2] / "dbqm" / "ui"
PROJECT_ROOT = UI_ROOT.parents[1]

# The product's two frames. They are the only files where drawing a box is
# the job. Paths relative to the project root, in the same format that
# `_rel()` produces — the first draft of this guard compared a relative
# posix string against an absolute path and never exempted anyone.
FRAMES = {
    "dbqm/ui/widgets/panel.py",
    "dbqm/ui/widgets/dialog.py",
}

# A real CSS declaration ends in `;` or `}`. Requiring the terminator is
# what separates the declaration from PROSE: `connections.py` explains the
# Panel width quoting "`border: round`" in a comment, and a scan without
# the terminator reports three false positives in that file alone.
#
# `outline` comes along because it DRAWS THE SAME BOX: `outline: round
# $accent` paints all four sides in Textual, only inside the widget's area
# instead of outside. A scan that only looked at `border` would leave the
# door open — swapping one word passed the guard with the box intact.
BORDER = re.compile(
    r"\b(?:border|outline)(?P<lado>-top|-bottom|-left|-right)?"
    r"\s*:\s*(?P<value>[^;{}\n]*?)\s*[;}]"
)
OPENS_A_RULE = re.compile(r"^\s*(?P<seletor>[^{}]+?)\s*\{")

# Exemptions by (file, selector), with the reason written down. By
# SELECTOR and not by file on purpose: a new section box in the same file
# is still failed.
EXEMPT = {
    # RECOLORS the affordance the widget already draws by itself — it adds
    # no box at all. Textual's `SelectCurrent` is born with `border: tall`;
    # here only the COLOR changes, to `$ds-identity`, as a sign of
    # "connection chosen". Two things make this exemption different from
    # the ones that were here before and were not true:
    #   - the geometry does not change (the box already existed, it is the
    #     control's own);
    #   - `tall` is not `round`: the section frame vocabulary remains
    #     exclusive to Panel/Dialog.
    # The previous draft exempted `#adhoc-conn-select` claiming that "the
    # border is the field's affordance". It was not: `Panel #panel-body
    # Select { border: none }` has higher specificity and erased that rule
    # — the exemption was protecting dead CSS. And `#adhoc-dbms-toggle`
    # drew `border: round $primary`, byte for byte the same as
    # `Panel:focus-within`: an idle checkbox looking like a focused panel.
    # Both left the CSS; this one remained, and it is real.
    (
        "dbqm/ui/screens/adhoc.py",
        "AdhocScreen #adhoc-conn-select.--conn-selected SelectCurrent",
    ),
}

# Known limits, chosen and not careless (same discipline as phase 1):
#   - a border assembled by interpolation or by CSS coming from another
#     layer is not seen by a textual scan;
#   - four `border-<side>` added up draw a box and pass, because ONE side
#     is a separation rule (`Panel` itself uses `border-bottom` on the
#     title, the `ActionBar` on top and the `TemplatesSidebar` on the
#     side) and telling the two cases apart would require interpreting the
#     whole block;
#   - the scan is LINE BY LINE, so a declaration broken in two (`border:`
#     on one line, `round $accent;` on the next) escapes — it is valid CSS
#     and Textual draws the box. It is not closed because joining lines
#     before scanning would require distinguishing a broken declaration
#     from the end of a block without a CSS parser, and the guard would
#     start depending on one. If a real case shows up, the way out is the
#     parser, not more regex.


def _rel(file: Path) -> str:
    return file.relative_to(PROJECT_ROOT).as_posix()


def raw_borders() -> list[tuple[str, int, str, str]]:
    """Every box drawn outside a frame component.

    Returns `(file, line, selector, declaration)`.
    """
    found: list[tuple[str, int, str, str]] = []
    for file in sorted(UI_ROOT.rglob("*.py")):
        rel = _rel(file)
        if rel in FRAMES:
            continue
        selector = ""
        for number, line in enumerate(
            file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            opens = OPENS_A_RULE.match(line)
            if opens:
                selector = opens.group("seletor")
            for m in BORDER.finditer(line):
                # A single side is a rule, not a box.
                if m.group("lado"):
                    continue
                # `border: none` ERASES a border; it draws none. The original
                # test excluded the whole line whenever it contained the word
                # "none" in any position — `#nonexistent { border: round
                # $accent; }` would escape. Here it is the VALUE that decides.
                if m.group("value").split()[0:1] == ["none"]:
                    continue
                if (rel, selector) in EXEMPT:
                    continue
                found.append((rel, number, selector, m.group(0)))
    return found


def test_the_border_scan_finds_files():
    """A guard that scans zero files passes without watching anything."""
    files = list(UI_ROOT.rglob("*.py"))
    assert len(files) > 20, f"varredura vazia ou rasa: {len(files)} arquivos"
    assert all((PROJECT_ROOT / rel).is_file() for rel in FRAMES)


def test_no_raw_border_outside_a_frame_component():
    """A third frame vocabulary was how the product got to three."""
    outside = raw_borders()
    assert not outside, 'a box drawn outside Panel/Dialog:\n' + '\n'.join((f'  {rel}:{n}  [{sel}]  {decl}' for rel, n, sel, decl in outside))


def test_the_guard_sees_outline_as_a_box():
    """`outline: round $accent` draws four sides — and is not `border`.

    Written because the first draft only scanned `border`: rendered, an
    `outline: round $accent;` paints the sides and the base exactly like
    the frame, and swapping one word made a new box slip past the guard.
    The `outline-<side>` remain a rule, like the `border-<side>`.
    """
    box = BORDER.search("    #qualquer-tela { outline: round $accent; }")
    assert box is not None and box.group("lado") is None
    rule_line = BORDER.search("    #qualquer-tela { outline-bottom: solid $ds-border; }")
    assert rule_line is not None and rule_line.group("lado") == "-bottom"


# ======================================================================
# Guard 2: centered action cluster outside a dialog
# ======================================================================

# LAYOUT alignment only — the four properties that reposition the content
# inside the container. `text-align` is left out on purpose: it centers
# the text INSIDE the widget's own box and does not detach any cluster
# from the subject it operates on, which is the damage that section 7
# describes.
CENTERING = re.compile(
    r"(?<![\w-])(?:content-)?align(?:-horizontal)?\s*:\s*"
    r"(?P<value>[^;{}\n]*?)\s*[;}]"
)
CLASS_LINE = re.compile(r"^class\s+(?P<name>\w+)\s*(?:\((?P<bases>[^)]*)\))?\s*:")

# Exemptions by (file, selector), with the reason written down — same
# format as the border guard. None of them is an action cluster: they are
# contents that OCCUPY the whole area and have no subject beside them to
# anchor to.
CENTERING_EXEMPT = {
    # The empty state IS the area it lives in: there is no list, table or
    # form beside it that it could detach from. Aligning it left would
    # leave the text stuck against a border with the whole area empty on
    # the right.
    #
    # The previous draft promised too much: "the actions INSIDE it are not
    # exempt". What the exemption by SELECTOR guarantees is narrower — a
    # NEW selector (`.empty-acoes { align: center }`) inherits no exemption
    # at all, but a declaration added TO THESE THREE selectors is never
    # examined by the guard again.
    #
    # Measured, because the difference matters: today the call-to-action
    # button is NOT centered. In the real DBQMApp at 100x30, `hist-empty`
    # occupies x=2..96 and the `Run query` button renders at x=4 —
    # stuck against the padding, aligned left. The reason is that the two
    # `Static` of the empty state are `width: 100%`: they fix the width of
    # the group of children, and `align`/`content-align` on the container
    # has nothing to center horizontally. Adding `align: center middle` to
    # this block does not change the button's x either (measured in both
    # orders, with and without the `content-align`). That is, what keeps
    # the CTA anchored left today is the siblings' width, not this guard.
    ("dbqm/ui/widgets/empty_state.py", "EmptyState"),
    ("dbqm/ui/widgets/empty_state.py", "EmptyState .empty-what"),
    ("dbqm/ui/widgets/empty_state.py", "EmptyState .empty-why"),
    # The progress indicator covers the screen while a remote call
    # happens; same reason as the empty state.
    ("dbqm/ui/widgets/progress.py", "ProgressIndicator Static"),
    # `#pe-empty` is the empty/loading state of the packages editor, with
    # `height: 1fr` and no button inside: while it shows, the editor's two
    # panels are `display: none` and IT is the screen — the case that
    # section 7 itself excepts. Aligning it left would create a second
    # empty-state vocabulary, against the `EmptyState` above.
    ("dbqm/ui/screens/package_editor.py", "PackageEditorScreen #pe-empty"),
}

# Known limits, chosen:
#   - the scan is LINE BY LINE: `align:` on one line and `center;` on the
#     next is valid CSS and escapes, as in the border guard above;
#   - only the DECLARATION is seen. A cluster centered by padding, by a
#     `1fr` spacer or by `widget.styles.align` written in Python does not
#     show up here;
#   - a dialog is recognized by the `class` line: name or base containing
#     `Modal`/`Dialog`. This was CHECKED against the real bases in this
#     repository — every subclass of `ModalScreen` is caught, and the only
#     name caught that is not a `ModalScreen` is `Dialog` itself, which is
#     the dialog's frame. A working screen christened with "Modal" in its
#     name would be exempted by mistake;
#   - the guard does not look at whether the block contains a BUTTON. It
#     fails any layout centering outside a dialog, and the legitimate
#     exceptions go into `CENTERING_EXEMPT` with the reason written down.
#     That is on purpose: the previous draft matched by selector NAME
#     (`#botoes`, `.acoes`) and a cluster called `#adhoc-btn-bar` — real,
#     measured — escaped.
#
# Two more limits of the dialog detection, found in the Task 8 review and
# written here because the list above presented itself as complete:
#   - `CLASSE` is anchored on `^class`: an INDENTED class is invisible to
#     the scan, and the CSS inside it inherits the verdict of the class
#     that surrounds it. There is one in the repository today —
#     `TemplateChosen`, nested in `TemplatesSidebar`
#     (dbqm/ui/widgets/templates_sidebar.py) — and it declares no CSS, so
#     the effect is nil. Accepting `^\s*class` would be worse without more
#     work: a `class Mensagem(Message)` nested in a modal would ZERO the
#     file's `dialogo` from there down, and the modal's legitimate
#     centering would start being failed. Closing that requires tracking
#     indentation, not loosening the anchor;
#   - `dialogo` holds until the end of the FILE after the last class.
#     Module-level CSS written below a modal class would come out exempt.
#     None exists today (this product's CSS always lives in `DEFAULT_CSS`
#     inside the class), and the price of not closing it is known.


def centered_clusters(
    apply_exemptions: bool = True,
) -> list[tuple[str, int, str, str]]:
    """Every layout centering outside a dialog.

    Returns `(file, line, selector, declaration)`. With
    `aplicar_isencoes=False` it also returns those of `CENTERING_EXEMPT` —
    which is what the canary uses to measure how much the dialog detection
    exempts.
    """
    found: list[tuple[str, int, str, str]] = []
    for file in sorted(UI_ROOT.rglob("*.py")):
        rel = _rel(file)
        dialog = False
        selector = ""
        for number, line in enumerate(
            file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            class_name = CLASS_LINE.match(line)
            if class_name:
                name = class_name.group("name")
                bases = class_name.group("bases") or ""
                dialog = any(
                    marker in text
                    for text in (name, bases)
                    for marker in ("Modal", "Dialog")
                )
                selector = ""
                continue
            opens = OPENS_A_RULE.match(line)
            if opens:
                selector = opens.group("seletor")
            if dialog:
                continue
            for m in CENTERING.finditer(line):
                if "center" not in m.group("value"):
                    continue
                if apply_exemptions and (rel, selector) in CENTERING_EXEMPT:
                    continue
                found.append((rel, number, selector, m.group(0)))
    return found


def test_no_centered_button_cluster_outside_a_dialog():
    """Centering only makes sense when the cluster IS the screen — a dialog.

    On a working screen, centering disconnects the action from what it
    operates on: the action has to touch the panel that is its subject.
    """
    outside = centered_clusters()
    assert not outside, 'centering on a working screen:\n' + '\n'.join((f'  {rel}:{n}  [{sel}]  {decl}' for rel, n, sel, decl in outside))


def test_the_centering_scan_sees_the_dialogs():
    """A guard that exempts everything (or nothing) watches nothing.

    Anchored on measured numbers: if the dialog detection stops working,
    the dozens of LEGITIMATE centerings of the modals enter the result and
    the test above starts failing the whole product.
    """
    total = 0
    for file in UI_ROOT.rglob("*.py"):
        for line in file.read_text(encoding="utf-8").splitlines():
            for m in CENTERING.finditer(line):
                if "center" in m.group("value"):
                    total += 1
    assert total > 40, f"varredura rasa demais: {total} centralizacoes"
    # Measured at d2367bb: 62 centering declarations in dbqm/ui, 57 of them
    # inside a dialog (legitimate by section 7) and 5 outside — the five of
    # `CENTERING_EXEMPT`. The ceiling of 8 is that 5 with a narrow margin,
    # on purpose: the previous draft of this canary was `< total / 2`,
    # which only fired if the dialog detection broke almost entirely. It
    # tolerated losing 25 modals in silence — and a canary that tolerates
    # losing half is not a canary, it is decoration.
    outside_a_dialog = centered_clusters(apply_exemptions=False)
    assert len(outside_a_dialog) <= 8, (
        'the dialog detection stopped exempting the modals: %d centerings outside a dialog (there were 5)\n%s' % (len(outside_a_dialog), '\n'.join(('  %s:%d  [%s]' % (r, n, s_) for r, n, s_, _d in outside_a_dialog)))
    )
    # The shape of the `class` line the scan needs to read: name and bases
    # with a generic in brackets, as every modal in this repository
    # declares it. If the regex stops matching it, `dialogo` gets stuck on
    # the value of the PREVIOUS class in the file and the exemption becomes
    # luck.
    matched = CLASS_LINE.match("class ConfirmModal(ModalScreen[bool]):")
    assert matched is not None
    assert matched.group("name") == "ConfirmModal"
    assert matched.group("bases") == "ModalScreen[bool]"


# ======================================================================
# Guard 3: `ListView` outside the vocabulary
# ======================================================================

# Came from `tests/ui/test_screens.py`, where it was born along with Task
# 5. It lives here because it is a repo-wide VOCABULARY scan, sister of
# the other four of this phase — and because a grammar guard hidden in the
# middle of 5 thousand lines of screen tests is not found by whoever is
# going to break it.
def listview_mentions() -> list[str]:
    """Every file of `dbqm/ui` that still mentions `ListView`.

    Matches ANY mention, not `ListView(`: the first draft only saw the
    constructor and for that reason passed green over three leftovers that
    build nothing — a CSS selector `Panel #panel-body ListView` matching
    nothing, an `isinstance(w, (..., ListView, ...))` whose branch cannot
    fire, and docstring prose narrating the widget as if it were still in
    use. A leftover like that costs exactly what a vocabulary guard exists
    to prevent: the next reader looks for the ListView the code promises
    and does not find it.
    """
    return [
        _rel(file)
        for file in sorted(UI_ROOT.rglob("*.py"))
        if "ListView" in file.read_text(encoding="utf-8")
    ]


# Known limits, chosen:
#   - the scan is by SUBSTRING in the file's text: a `getattr(
#     textual.widgets, "List" + "View")` assembles the name at runtime and
#     passes. Closing that would require executing the module, not reading
#     it;
#   - it scans only `dbqm/ui`. A `ListView` in a test, in a script or in
#     the CLI is not failed — the vocabulary this phase governs is the
#     interface's;
#   - the mention can be this very sentence. A product file that EXPLAINS
#     why it does not use `ListView` would be failed; the place for that
#     explanation is here, in the guard.


def test_listview_left_the_vocabulary():
    """`ListView` did the same as `OptionList` in two places.

    Two components for one function is what the phase 1 inventory test
    fails; section 5 of the grammar chose `OptionList`.
    """
    sources = list(UI_ROOT.rglob("*.py"))
    assert sources, 'the scan found no source at all in %s' % UI_ROOT
    found = listview_mentions()
    assert not found, 'ListView is still mentioned in: %s' % found


# ======================================================================
# Common infra of the AST guards
# ======================================================================
#
# The three guards below read the TREE, not the text. The trade is
# deliberate: what they watch is not a CSS declaration on a line, but the
# shape of a call (the argument of `Option(...)`, the argument of
# `add_column(...)`, the body of an `on_button_pressed`). Regex over that
# has already failed in this phase — the first version of the centering
# guard captured `#buttons {` in place of the class line and would have
# failed 16 correct clusters without seeing any of the 3 real ones.
#
# What the AST does NOT see, in any of the three:
#   - a value assembled at runtime (`"%s | %s" % ...` stored in a module
#     dict, a label coming from a `.json`, a column coming from the
#     database);
#   - what another layer does with the object afterwards (a correct
#     `Option` that a wrapper flattens when assembling it);
#   - anything outside `dbqm/ui` — CLI and tests are not scanned.


def _modules() -> list[tuple[str, ast.Module]]:
    """(relative path, tree) of each source of `dbqm/ui`."""
    modules = []
    for file in sorted(UI_ROOT.rglob("*.py")):
        text = file.read_text(encoding="utf-8")
        modules.append((_rel(file), ast.parse(text, filename=str(file))))
    return modules


def _called_name(no: ast.Call) -> str:
    """`Option(...)` -> "Option"; `self.x.add_column(...)` -> "add_column"."""
    if isinstance(no.func, ast.Name):
        return no.func.id
    if isinstance(no.func, ast.Attribute):
        return no.func.attr
    return ""


# ======================================================================
# Guard 4: list item flattened into a single string
# ======================================================================

# The product's list item constructors. `Option` and `Selection` are
# Textual's; `NamedOption` is ours (dbqm/ui/widgets/hierarchical_list.py).
ITEM_BUILDERS = {"Option", "NamedOption", "Selection"}

# Exemptions by (file, constructor), with the MEASURED reason written down.
FLATTENED_EXEMPT = {
    # `SelectionList` (the group_exec connections checklist) paints ONLY
    # THE FIRST LINE of the prompt: I assembled a `Selection(
    # hierarchical_item("MGORA7ORA9", "oracle - host:1521/svc"), ...)` in a
    # test app at 60x20 and the disambiguation line was simply not drawn —
    # the item shows up as `▐X▌ MGORA7ORA9` and the target disappears.
    # Applying the hierarchy here would not make the item more legible: it
    # would ERASE the data it shows today. As long as the checklist is a
    # `SelectionList`, the single string is the least bad shape, and the
    # real way out is to swap the widget — a flow decision, outside the
    # scope of this phase (section 11 of the spec).
    ("dbqm/ui/screens/group_exec.py", "Selection"),
}

# Known limits, chosen:
#   - variable resolution is by NAME, across the whole file, without
#     scope: `label = f"..."` in one function and `Selection(label, ...)`
#     in another get mixed, and the last assignment wins. It was enough to
#     catch the only real case (group_exec) and a real scope resolver
#     would be more code than the whole guard. If a false positive shows
#     up, the way out is scope, not loosening the rule;
#   - only ONE level of indirection: `a = f"{x} {y}"; b = a; Option(b)`
#     escapes;
#   - `f"{x}"` with ONE field passes on purpose — it is identity with a
#     prefix (`f"📄  {t.name}"` in the templates sidebar), not glued-on
#     metadata. It is from TWO fields on one line that the `name (tipo -
#     alvo) | descricao` that section 5 forbids is born;
#   - the exemption is by (file, constructor): a SECOND flattened
#     `Selection` in the same file would pass too. In exchange, a
#     flattened `Selection` in ANY other file is failed.


def _interpolated_fields(no: ast.JoinedStr) -> int:
    return sum(1 for part in no.values if isinstance(part, ast.FormattedValue))


def _addition_operands(no: ast.AST) -> list[ast.AST]:
    """Flattens `a + b + c` into the list of operands."""
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        return _addition_operands(no.left) + _addition_operands(no.right)
    return [no]


def _flattening(no: ast.AST) -> str:
    """Describes the flattening, or "" if the node flattens nothing."""
    if isinstance(no, ast.JoinedStr):
        fields = _interpolated_fields(no)
        if fields >= 2:
            return "f-string com %d campos numa linha so" % fields
        return ""
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        parts = _addition_operands(no)
        glue = [
            p.value
            for p in parts
            if isinstance(p, ast.Constant)
            and isinstance(p.value, str)
            and p.value.strip()
        ]
        variables = [p for p in parts if not isinstance(p, ast.Constant)]
        if glue and variables:
            return "concatenacao com separador %r" % glue[0]
    return ""


def flattened_labels() -> list[tuple[str, int, str, str]]:
    """Every list item assembled as a single string.

    Returns `(file, line, constructor, reason)`.
    """
    found: list[tuple[str, int, str, str]] = []
    for rel, module_ in _modules():
        # One indirection: `label = f"..."` and then `Selection(label, ...)`.
        # Without this, moving the f-string into a variable disarms the
        # guard — and that is exactly how the product's only real case is
        # written.
        assignments: dict[str, ast.AST] = {}
        for no in ast.walk(module_):
            if isinstance(no, ast.Assign) and len(no.targets) == 1:
                target = no.targets[0]
                if isinstance(target, ast.Name):
                    assignments[target.id] = no.value
        for no in ast.walk(module_):
            if not isinstance(no, ast.Call) or not no.args:
                continue
            constructor = _called_name(no)
            if constructor not in ITEM_BUILDERS:
                continue
            first = no.args[0]
            if isinstance(first, ast.Name):
                first = assignments.get(first.id, first)
            reason = _flattening(first)
            if not reason:
                continue
            if (rel, constructor) in FLATTENED_EXEMPT:
                continue
            found.append((rel, no.lineno, constructor, reason))
    return found


def test_the_label_scan_sees_the_item_builders():
    """A guard that finds no constructor watches no list at all."""
    seen = {
        _called_name(no)
        for _rel_, module_ in _modules()
        for no in ast.walk(module_)
        if isinstance(no, ast.Call)
    }
    assert ITEM_BUILDERS <= seen, (
        'a list-item builder vanished from the product: %s' % (ITEM_BUILDERS - seen)
    )
    # The shape the guard needs to recognize, verified here and not merely
    # trusted: two fields in a string are flattening, one field is not.
    two = ast.parse('Option(f"{a} | {b}")').body[0].value.args[0]
    um = ast.parse('Option(f"icone {a}")').body[0].value.args[0]
    assert _flattening(two)
    assert not _flattening(um)


def test_list_label_is_not_a_flattened_string():
    """A list item is never a concatenated string (section 5).

    Identity, disambiguation and context are THREE roles; squeezed into a
    single line, the list breaks the text wherever it fits and the eye
    does not tell a continuation from a new entry. That was the complaint
    that originated this phase. The cure is `hierarchical_item`, not a
    better separator.
    """
    outside = flattened_labels()
    assert not outside, "item de lista achatado numa string:\n" + "\n".join(
        f"  {rel}:{n}  {constructor}(...)  {reason}"
        for rel, n, constructor, reason in outside
    )


# ======================================================================
# Guard 5: result table without a fixed key column
# ======================================================================

# A RESULT table is the one that discovers its own columns in the data:
# `add_column(str(col))` in a loop over what came back from the database.
# It is the one that can have 1 column or 36 (measured: median 9 in the
# maintainer's queries), and that is why it is the one that needs the
# fixed key — dbqm exists to COMPARE, and a row whose key has scrolled out
# of sight compares nothing.
#
# A fixed-schema table (`add_columns("#", "Nome", "Descricao")`) was
# written by someone who knew its width; it does not fall under this rule.
def _is_a_fixed_name(arg: ast.AST) -> bool:
    """A column name written by whoever knew the table's width.

    A string literal is one. So is `t("some.key")`: the name comes from
    the catalogue, which is a constant with a lookup in front of it, not
    from the data. Reading the `t()` call as dynamic made every translated
    header of a fixed-schema table look like a discovered column, and this
    guard demand a fixed key from tables that have no key.
    """
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return True
    return (
        isinstance(arg, ast.Call)
        and isinstance(arg.func, ast.Name)
        and arg.func.id == "t"
        and len(arg.args) == 1
        and isinstance(arg.args[0], ast.Constant)
        and isinstance(arg.args[0].value, str)
    )


def _dynamic_columns(scope: ast.AST) -> list[tuple[int, str, ast.Call]]:
    """`add_column(...)` whose column name comes from the data, in this scope.

    Returns `(line, argument, call)`.
    """
    dynamic: list[tuple[int, str, ast.Call]] = []
    for no in ast.walk(scope):
        if not (isinstance(no, ast.Call) and _called_name(no) in {
            "add_column",
            "add_columns",
        }):
            continue
        for arg in no.args:
            if not _is_a_fixed_name(arg):
                dynamic.append((no.lineno, ast.unparse(arg), no))
                break
    return dynamic


def _fixes_the_key(scope: ast.AST) -> bool:
    for no in ast.walk(scope):
        if isinstance(no, ast.Attribute) and no.attr == "fixed_columns":
            return True
        if isinstance(no, ast.keyword) and no.arg == "fixed_columns":
            return True
    return False


def result_tables_without_fixed_key() -> list[tuple[str, int, str]]:
    """Function that builds a column from data and does not fix the key.

    Returns `(file, line, dynamic_column)`.

    The granularity is the FUNCTION, and not the file — the first draft of
    this guard measured per file and passed in both states: erasing the
    fixing in `_render_flat` in `group_result.py`, the `fixed_columns` of
    `_render_pivoted`, in the same file, kept the guard green. A guard
    that passes with the rule broken is worse than no guard at all, and
    this one was caught by the breakage test of the very task that wrote
    it.
    """
    found: list[tuple[str, int, str]] = []
    for rel, module_ in _modules():
        parents: dict[int, ast.AST] = {}
        nos: dict[int, ast.AST] = {}
        for parent in ast.walk(module_):
            for child in ast.iter_child_nodes(parent):
                parents[id(child)] = parent
                nos[id(child)] = child
        for line, arg, call in _dynamic_columns(module_):
            # Scope = the innermost function that contains the call (or the
            # module, if it is loose). The key can be fixed there or in any
            # function that surrounds it — both readings are legible; what
            # the guard refuses is the fixing living in another branch of
            # the file.
            scopes: list[ast.AST] = []
            current = parents.get(id(call))
            while current is not None:
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scopes.append(current)
                current = parents.get(id(current))
            if not scopes:
                scopes = [module_]
            if not any(_fixes_the_key(e) for e in scopes):
                found.append((rel, line, arg))
    return found


# Known limits, chosen:
#   - the granularity is the FUNCTION that builds the columns (plus the
#     ones that surround it), not the `DataTable` object. A screen that
#     built the columns in one method and fixed the key in ANOTHER sibling
#     method would be failed by mistake — and the right way out is to move
#     the fixing next to the columns, which is where it is legible.
#     Following the object between methods (`query_one("#tabela")` in one,
#     `mount` in another) is aliasing that the AST alone does not resolve;
#   - `fixed_columns` MENTIONED in the function already satisfies it: the
#     guard does not read the value. That the value is right (1 when there
#     is more than one column, 0 when there is only one) is what the
#     rendering tests in `tests/ui/test_widgets.py` assert — by scrolling
#     the real table and reading what stayed painted, not the attribute;
#   - a column whose name comes from a module constant (`add_column(TITULO)`)
#     counts as dynamic and asks for a fixed key. A possible false
#     positive, not observed yet: the way out is to write the literal or
#     to fix the key, and neither of the two makes the screen worse;
#   - a FIXED-SCHEMA table is left out by design (`add_columns("#",
#     "Nome", ...)`). Whoever wrote the literals knew their width; the
#     rule of section 6 exists for the table that discovers the columns in
#     the data and can have 1 or 36.


def test_the_table_scan_finds_the_columns():
    """If nobody builds columns anymore, this guard stopped watching."""
    total = 0
    for _, module_ in _modules():
        for no in ast.walk(module_):
            if isinstance(no, ast.Call) and _called_name(no) in {
                "add_column",
                "add_columns",
            }:
                total += 1
    assert total > 15, 'the scan is too shallow: %d column calls' % total


def test_result_table_fixes_the_key_column():
    """Scrolling without fixing the key destroys the comparison (section 6)."""
    outside = result_tables_without_fixed_key()
    assert not outside, 'a result table without a fixed key:\n' + '\n'.join((f'  {rel}:{n}  add_column({arg})' for rel, n, arg in outside))


# ======================================================================
# Guard 6: button that navigates
# ======================================================================
#
# The other half of section 7: "a button is an action, never navigation
# nor a menu". The menu half was solved in Task 8 (`Tools` and the
# mode selector of `config_port` became a choosable list) and the
# centering one has guard 2. This one had no guard at all — and the scope
# note of Task 8 said that ONE call-to-action navigated. There are FOUR.
# That is what decided building this guard instead of leaving the rule to
# human review: a rule without a guard already got its own count wrong by
# a factor of 4 in the week it was written.

# What navigating is: switching the shell's tab, or opening another tool.
NAVIGATION = {"action_switch_tab", "open_tool"}

# Exemptions by (file, button id), with the reason written down. The four
# CTAs below are empty states: `EmptyState` (dbqm/ui/widgets/empty_state.py)
# REQUIRES `action_label` and `action_id` — the four parameters are mandatory
# on purpose, to prevent "No query configured" without offering
# the way out. When the honest way out of an empty state is in another tab
# (there is no query to create HERE; it is born in Collect), the only way
# to honor the contract is to navigate.
#
# Leaving the four like that was a decision, not an oversight: making the
# action optional changes the `EmptyState` contract in 14 call sites and
# is a flow change, outside the scope of the layout grammar (section 11 of
# the spec). What this guard delivers meanwhile is the CEILING: there are
# four, they are named, and the fifth fails the suite.
NAVIGATION_EXEMPT = {
    # "Run query" -> Queries tab. There is no history to create
    # here; it is born from an execution in another tab.
    ("dbqm/ui/screens/history.py", "run-query"),
    # "Create query" -> Collect tab. A query is saved from there ("Save
    # as query"), never from this screen.
    ("dbqm/ui/screens/query_exec.py", "create-query-collect"),
    # "Manage groups" -> Groups tool. This screen EXECUTES groups;
    # creating is the job of the tool next door.
    ("dbqm/ui/screens/group_run.py", "manage-groups"),
    # "Open Tools" -> Tools tab. The templates sidebar shows
    # templates; they are created in the Templates tool.
    ("dbqm/ui/widgets/templates_sidebar.py", "open-tools"),
}

# Known limits, chosen:
#   - only the body of the button handler is read. A handler that calls
#     `self._ir_para_consultas()`, and THAT method switches tabs, passes:
#     the AST does not follow a call between methods, and following it
#     would require a call graph of the whole module;
#   - the button id comes out of the literal comparison (`if
#     event.button.id == "x"`). A handler that resolves the id by variable
#     or by dict is reported with an empty id — and an empty id matches no
#     exemption, so it fails. That is the safe side: obscuring the id does
#     not buy silence;
#   - `action_switch_tab` called from a KEY handler, from `on_mount` or
#     from the `OptionList` is not failed, and that is the rule and not a
#     hole: list, tab and shortcut ARE legitimate navigation. Only a
#     button is not;
#   - the list of verbs is closed (`NAVIGATION`). A third way of
#     navigating that shows up tomorrow needs to be added here — the same
#     cost that `FRAMES` and `ITEM_BUILDERS` already pay;
#   - `_branch_ids` climbs through the `if`s that SURROUND the call and
#     collects every string literal it finds in each one's test; then
#     `botoes_que_navegam` keeps `sorted(ids)[0]`. The `if/elif` hole this
#     block used to describe is CLOSED: an `elif` is an `If` nested in the
#     previous one's `orelse`, and the climb now skips the test of any `If`
#     whose `orelse` it came out of, because that test governs the branch
#     ABOVE this one. Before the fix, a navigating branch whose id sorted
#     AFTER an exempt id in the same file inherited that exemption and passed
#     in silence. Verified by breakage both ways: an `elif "zzz-fuga"` beside
#     the exempt `"run-query"` in `history.py` escaped before and
#     FAILS now. What the climb still cannot see is a branch whose id is not
#     a literal — that is reported with an empty id, which matches no
#     exemption and therefore fails, the safe side;
#   - the verb is also accepted as a literal STRING, because that is the
#     shape the four real CTAs use (`getattr(self.app, "action_switch_tab", None)`).
#     The price: the guard proves that the NAME is written there, not that
#     the navigation happens. Emptying the call and leaving only the
#     `getattr` keeps this test green with a mute CTA — what covers that
#     side are the behavior tests of each CTA, not this scan.


def _is_button_handler(no: ast.AST) -> bool:
    if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    if no.name.startswith("on_button_pressed"):
        return True
    # Also by the parameter's TYPE and by the decorator: a renamed handler
    # (`@on(Button.Pressed)` or `def _cliquei(self, e: Button.Pressed)`)
    # is still a button handler.
    annotations = [ast.unparse(a.annotation) for a in no.args.args if a.annotation]
    decorators = [ast.unparse(d) for d in no.decorator_list]
    return any("Button.Pressed" in t for t in annotations + decorators)


def _branch_ids(no: ast.AST, parents: dict[ast.AST, ast.AST], root: ast.AST) -> set[str]:
    """The button ids compared in the `if` that surrounds *no*.

    An `elif` is an `If` nested in the previous one's `orelse`, so climbing
    every ancestor used to collect the SIBLING branch's test too. The ids then
    mixed, and `sorted(ids)[0]` could return an exempt neighbour's id — a
    navigating branch inherited an exemption it was never granted and passed in
    silence.

    The test of an `If` whose `orelse` we climbed out of governs the branch
    ABOVE this one, never this one. Skipping it closes the chain hole without
    losing the genuinely nested handlers that a nearest-`if`-only rule would
    have dropped.
    """
    ids: set[str] = set()
    child: ast.AST = no
    current = parents.get(no)
    while current is not None and current is not root:
        if isinstance(current, ast.If) and not any(child is s for s in current.orelse):
            for test_name in ast.walk(current.test):
                if isinstance(test_name, ast.Constant) and isinstance(test_name.value, str):
                    ids.add(test_name.value)
        child = current
        current = parents.get(current)
    return ids


def navigating_buttons() -> list[tuple[str, int, str, str]]:
    """Every button handler that switches tabs or opens another tool.

    Returns `(file, line, button id, navigation verb)`.
    """
    found: list[tuple[str, int, str, str]] = []
    for rel, module_ in _modules():
        for handler in ast.walk(module_):
            if not _is_button_handler(handler):
                continue
            parents: dict[ast.AST, ast.AST] = {}
            for parent in ast.walk(handler):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent
            for no in ast.walk(handler):
                verb = ""
                if isinstance(no, ast.Attribute) and no.attr in NAVIGATION:
                    verb = no.attr
                elif isinstance(no, ast.Name) and no.id in NAVIGATION:
                    verb = no.id
                elif (
                    isinstance(no, ast.Constant)
                    and isinstance(no.value, str)
                    and no.value in NAVIGATION
                ):
                    # `getattr(self.app, "action_switch_tab", None)` — the
                    # shape the four real CTAs use.
                    verb = no.value
                if not verb:
                    continue
                ids = _branch_ids(no, parents, handler) - NAVIGATION
                button = sorted(ids)[0] if ids else ""
                if (rel, button) in NAVIGATION_EXEMPT:
                    continue
                found.append((rel, no.lineno, button, verb))
    return found


def test_the_navigation_scan_sees_the_handlers():
    """A guard that finds no button handler watches no button at all."""
    handlers = [
        no
        for _rel_, module_ in _modules()
        for no in ast.walk(module_)
        if _is_button_handler(no)
    ]
    assert len(handlers) > 15, "varredura rasa demais: %d handlers" % len(handlers)
    # The exemptions are worth something by BEING real: if an exempt CTA
    # stops navigating (or stops existing), the exemption becomes dead
    # letter and the ceiling of four stops being a measured ceiling.
    without_exemption = {(rel, button) for rel, _n, button, _v in _navigating_buttons_raw()}
    assert NAVIGATION_EXEMPT <= without_exemption, (
        'an exemption matching no real button: %s' % (NAVIGATION_EXEMPT - without_exemption)
    )


def _navigating_buttons_raw() -> list[tuple[str, int, str, str]]:
    """`botoes_que_navegam()` without applying the exemptions."""
    kept = set(NAVIGATION_EXEMPT)
    NAVIGATION_EXEMPT.clear()
    try:
        return navigating_buttons()
    finally:
        NAVIGATION_EXEMPT.update(kept)


def test_button_does_not_navigate():
    """A button is an action, never navigation (section 7).

    Navigating is the job of a tab, of a list and of a shortcut. A button
    that switches tabs promises "this operates what you are seeing" and
    does something else — besides making the next layout grow a menu
    button, which is what Task 8 has just undone.
    """
    outside = navigating_buttons()
    assert not outside, "botao usado como navegacao:\n" + "\n".join(
        f"  {rel}:{n}  [{button or '?'}]  -> {verb}" for rel, n, button, verb in outside
    )
