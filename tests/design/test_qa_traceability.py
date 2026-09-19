"""The QA documents may not rot.

Every scenario row in `docs/qa/*.md` names a test that proves it, or says
`—` because it is manual. This test reads the documents and fails when a
referenced test does not exist, when a `functional` or `unit` row still says
`—`, when a `functional` row points outside `tests/functional/`, or when an
ID is used twice. The same ratchet shape as the mypy exemption list: a
document a test enforces is a specification, one nothing enforces is a wish.

Tests are located by reading the test files, not by running pytest inside
pytest -- this suite never runs two pytest processes at once, and a nested
collection would be exactly that.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
QA = REPO_ROOT / "docs" / "qa"

_LINE = re.compile(r"^\|\s*(QA-[A-Z]+-\d{3})\s*\|(.*)\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|\s*$")
# `[ \t]*`, not `\s*`: under MULTILINE a greedy `\s*` anchored at the start
# of a blank line swallows the newlines before `def`, so a top-level test's
# "indentation" came back as "\n\n" and never matched the empty string.
_DEF = re.compile(r"^([ \t]*)(?:async\s+)?def\s+(test_\w+)\s*\(", re.MULTILINE)
_CLASS_LINE = re.compile(r"^class\s+(\w+)", re.MULTILINE)

LAYERS = {"unit", "functional", "manual"}
ENGINES = {"all", "sqlite", "oracle"}


def _lines() -> list[tuple[Path, str, str, str, str]]:
    """(document, id, camada, engine, teste) for every scenario row."""
    output = []
    for doc in sorted(QA.glob("*.md")):
        if doc.name == "README.md":
            continue
        for line in doc.read_text(encoding="utf-8").splitlines():
            m = _LINE.match(line)
            if m:
                output.append((doc, m.group(1), m.group(3), m.group(4), m.group(5)))
    return output


def _the_test_exists(ref: str) -> bool:
    """`tests/x.py::name` or `tests/x.py::Class::name`, found by reading."""
    parts = ref.split("::")
    file = REPO_ROOT / parts[0]
    if not file.exists() or len(parts) < 2:
        return False
    source = file.read_text(encoding="utf-8")
    name = parts[-1]
    if len(parts) == 2:
        return any(m.group(2) == name and m.group(1) == "" for m in _DEF.finditer(source))
    class_name = parts[1]
    # the method must sit under that class: find the class, then the next
    # top-level class (or EOF) bounds its body
    start = None
    for m in _CLASS_LINE.finditer(source):
        if start is not None:
            body = source[start:m.start()]
            break
        if m.group(1) == class_name:
            start = m.end()
    else:
        if start is None:
            return False
        body = source[start:]
    return any(m.group(2) == name for m in _DEF.finditer(body))


def test_every_id_is_used_once():
    ids = [line[1] for line in _lines()]
    repeated_ones = sorted({i for i in ids if ids.count(i) > 1})
    assert not repeated_ones, f"IDs repetidos entre os documentos: {repeated_ones}"


def test_every_row_has_a_known_layer_and_engine():
    for doc, ident, layer, engine, _ in _lines():
        assert layer in LAYERS, f"{doc.name} {ident}: camada {layer!r}"
        assert engine in ENGINES, f"{doc.name} {ident}: engine {engine!r}"


def test_no_functional_or_unit_row_is_still_a_dash():
    """A `—` is a finding, not a placeholder. Only `manual` may carry it."""
    missing_ones = [
        f"{doc.name} {ident}" for doc, ident, layer, _, test_name in _lines()
        if layer != "manual" and test_name in ("—", "-", "")
    ]
    assert not missing_ones, f"scenarios with no test: {missing_ones}"


def test_every_referenced_test_exists():
    missing = [
        f"{doc.name} {ident} -> {test_name}" for doc, ident, layer, _, test_name in _lines()
        if layer != "manual" and not _the_test_exists(test_name)
    ]
    assert not missing, f'referenced tests that do not exist: {missing}'


#: Where a `functional` row may point. `tests/ui/test_functional_screens.py`
#: is the UI's half of the same layer -- it drives the real screens against
#: the real SQLite file and patches nothing, which is the property that makes
#: a row `functional`. It cannot live under `tests/functional/`: the UI slice
#: is what runs it, and it needs `tests/ui/_helpers.py`.
FUNCTIONAL_SOURCES = ("tests/functional/", "tests/ui/test_functional_screens.py")


def test_functional_rows_point_at_the_functional_folder():
    """A `functional` row backed by a mocked test would claim a proof the
    program never gave."""
    outside = [
        f"{doc.name} {ident} -> {test_name}" for doc, ident, layer, _, test_name in _lines()
        if layer == "functional" and not test_name.startswith(FUNCTIONAL_SOURCES)
    ]
    assert not outside, f'functional rows pointing outside {FUNCTIONAL_SOURCES}: {outside}'


def test_manual_rows_carry_no_test_and_a_script():
    """`manual` means nobody automated it: the row must say `—`, and the
    document must give the person the commands to run."""
    for doc, ident, layer, _, test_name in _lines():
        if layer == "manual":
            assert test_name in ("—", "-"), f'{doc.name} {ident}: manual, yet carries the test {test_name!r}'
            assert "```" in doc.read_text(encoding="utf-8"), f"{doc.name}: sem roteiro"


@pytest.mark.parametrize("ref, expected", [
    ("tests/design/test_qa_traceability.py::test_every_id_is_used_once", True),
    ("tests/design/test_qa_traceability.py::test_nao_existe", False),
    ("tests/no/such.py::test_x", False),
])
def test_the_locator_itself(ref, expected):
    """The locator is what every other assertion here trusts; it gets its
    own proof, including the negative."""
    assert _the_test_exists(ref) is expected
