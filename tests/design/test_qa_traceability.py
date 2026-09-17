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

RAIZ = Path(__file__).resolve().parents[2]
QA = RAIZ / "docs" / "qa"

_LINHA = re.compile(r"^\|\s*(QA-[A-Z]+-\d{3})\s*\|(.*)\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|\s*$")
# `[ \t]*`, not `\s*`: under MULTILINE a greedy `\s*` anchored at the start
# of a blank line swallows the newlines before `def`, so a top-level test's
# "indentation" came back as "\n\n" and never matched the empty string.
_DEF = re.compile(r"^([ \t]*)(?:async\s+)?def\s+(test_\w+)\s*\(", re.MULTILINE)
_CLASSE = re.compile(r"^class\s+(\w+)", re.MULTILINE)

CAMADAS = {"unit", "functional", "manual"}
ENGINES = {"all", "sqlite", "oracle"}


def _linhas() -> list[tuple[Path, str, str, str, str]]:
    """(document, id, camada, engine, teste) for every scenario row."""
    saida = []
    for doc in sorted(QA.glob("*.md")):
        if doc.name == "README.md":
            continue
        for linha in doc.read_text(encoding="utf-8").splitlines():
            m = _LINHA.match(linha)
            if m:
                saida.append((doc, m.group(1), m.group(3), m.group(4), m.group(5)))
    return saida


def _teste_existe(ref: str) -> bool:
    """`tests/x.py::name` or `tests/x.py::Class::name`, found by reading."""
    partes = ref.split("::")
    arquivo = RAIZ / partes[0]
    if not arquivo.exists() or len(partes) < 2:
        return False
    fonte = arquivo.read_text(encoding="utf-8")
    nome = partes[-1]
    if len(partes) == 2:
        return any(m.group(2) == nome and m.group(1) == "" for m in _DEF.finditer(fonte))
    classe = partes[1]
    # the method must sit under that class: find the class, then the next
    # top-level class (or EOF) bounds its body
    inicio = None
    for m in _CLASSE.finditer(fonte):
        if inicio is not None:
            corpo = fonte[inicio:m.start()]
            break
        if m.group(1) == classe:
            inicio = m.end()
    else:
        if inicio is None:
            return False
        corpo = fonte[inicio:]
    return any(m.group(2) == nome for m in _DEF.finditer(corpo))


def test_every_id_is_used_once():
    ids = [linha[1] for linha in _linhas()]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    assert not repetidos, f"IDs repetidos entre os documentos: {repetidos}"


def test_every_row_has_a_known_layer_and_engine():
    for doc, ident, camada, engine, _ in _linhas():
        assert camada in CAMADAS, f"{doc.name} {ident}: camada {camada!r}"
        assert engine in ENGINES, f"{doc.name} {ident}: engine {engine!r}"


def test_no_functional_or_unit_row_is_still_a_dash():
    """A `—` is a finding, not a placeholder. Only `manual` may carry it."""
    faltando = [
        f"{doc.name} {ident}" for doc, ident, camada, _, teste in _linhas()
        if camada != "manual" and teste in ("—", "-", "")
    ]
    assert not faltando, f"cenarios sem teste: {faltando}"


def test_every_referenced_test_exists():
    ausentes = [
        f"{doc.name} {ident} -> {teste}" for doc, ident, camada, _, teste in _linhas()
        if camada != "manual" and not _teste_existe(teste)
    ]
    assert not ausentes, f"testes referenciados que nao existem: {ausentes}"


#: Where a `functional` row may point. `tests/ui/test_functional_screens.py`
#: is the UI's half of the same layer -- it drives the real screens against
#: the real SQLite file and patches nothing, which is the property that makes
#: a row `functional`. It cannot live under `tests/functional/`: the UI slice
#: is what runs it, and it needs `tests/ui/_helpers.py`.
FONTES_FUNCIONAIS = ("tests/functional/", "tests/ui/test_functional_screens.py")


def test_functional_rows_point_at_the_functional_folder():
    """A `functional` row backed by a mocked test would claim a proof the
    program never gave."""
    fora = [
        f"{doc.name} {ident} -> {teste}" for doc, ident, camada, _, teste in _linhas()
        if camada == "functional" and not teste.startswith(FONTES_FUNCIONAIS)
    ]
    assert not fora, f"linhas funcionais apontando para fora de {FONTES_FUNCIONAIS}: {fora}"


def test_manual_rows_carry_no_test_and_a_script():
    """`manual` means nobody automated it: the row must say `—`, and the
    document must give the person the commands to run."""
    for doc, ident, camada, _, teste in _linhas():
        if camada == "manual":
            assert teste in ("—", "-"), f"{doc.name} {ident}: manual com teste {teste!r}"
            assert "```" in doc.read_text(encoding="utf-8"), f"{doc.name}: sem roteiro"


@pytest.mark.parametrize("ref,esperado", [
    ("tests/design/test_qa_traceability.py::test_every_id_is_used_once", True),
    ("tests/design/test_qa_traceability.py::test_nao_existe", False),
    ("tests/nao/existe.py::test_x", False),
])
def test_the_locator_itself(ref, esperado):
    """The locator is what every other assertion here trusts; it gets its
    own proof, including the negative."""
    assert _teste_existe(ref) is esperado
