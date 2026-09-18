"""User-facing text lives in the catalogue, and the catalogue stays honest.

Two jobs. The first is a ratchet, in the shape this repo already uses for the
mypy exemptions and the design tokens: the number of Portuguese literals left
in the source goes down, never up. Without it, the migration stalls halfway
and the next person adds a literal because the file next door has one.

The second is the catalogue's own integrity — every translation carries the
keys the source language defines, with the placeholders it defines. A
translation missing a `{nome}` renders a sentence with a hole in it, and a
translation carrying a key English dropped is dead weight nobody will notice.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from dbqm.i18n import CATALOGOS, IDIOMA_PADRAO, en

RAIZ = Path(__file__).resolve().parents[2]

#: Words that only appear in Portuguese screen text. Deliberately not a
#: language detector: it only has to be good enough to notice a sentence
#: someone typed straight into a widget.
PALAVRAS = [
    "conexao", "conexoes", "consulta", "consultas", "avulso", "executar",
    "salvar", "remover", "voltar", "selecione", "informe", "registros",
    "grupos", "arquivo", "senha", "usuario", "configuracoes", "historico",
    "ferramentas", "parametro", "parametros", "resultado", "resultados",
    "nenhum", "nenhuma", "somente", "invalido", "encontrada", "encontrado",
    "obrigatorio", "sucesso", "falhou", "nao", "sao", "coluna", "colunas",
    "tabela", "rotina", "pacote",
]
MARCA = re.compile(r"\b(" + "|".join(PALAVRAS) + r")\b", re.IGNORECASE)

#: Measured when the catalogue landed. This number goes DOWN as modules move
#: over, never up. Lowering it is the whole point.
MAX_LITERAIS = 748

#: The catalogue itself is Portuguese by definition, and the design tokens
#: carry Portuguese token names that are identifiers, not screen text.
FORA = ("dbqm/i18n/",)


def _e_docstring(no, docstrings) -> bool:
    return id(no) in docstrings


def _docstrings(arvore) -> set[int]:
    fora = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = getattr(no, "body", [])
            if (corpo and isinstance(corpo[0], ast.Expr)
                    and isinstance(corpo[0].value, ast.Constant)
                    and isinstance(corpo[0].value.value, str)):
                fora.add(id(corpo[0].value))
    return fora


def literais_de_tela() -> list[tuple[str, int, str]]:
    """`(file, line, text)` for every Portuguese string constant still in the
    source. Docstrings are excluded: they are English by rule and nobody
    reads them on a screen."""
    achados = []
    for py in sorted((RAIZ / "dbqm").rglob("*.py")):
        relativo = py.relative_to(RAIZ).as_posix()
        if relativo.startswith(FORA):
            continue
        arvore = ast.parse(py.read_text(encoding="utf-8"))
        docstrings = _docstrings(arvore)
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Constant) and isinstance(no.value, str)
                    and not _e_docstring(no, docstrings)):
                texto = no.value.strip()
                if len(texto) > 3 and "\n" not in texto and MARCA.search(texto):
                    achados.append((relativo, no.lineno, texto))
    return achados


def test_the_literal_count_only_falls():
    restantes = literais_de_tela()
    assert len(restantes) <= MAX_LITERAIS, (
        f"{len(restantes)} Portuguese literals left in dbqm/, up from "
        f"{MAX_LITERAIS}. New user-facing text goes in dbqm/i18n/, not in a "
        f"widget. First few: {restantes[:3]}"
    )


def test_the_count_matches_what_is_there():
    """`MAX_LITERAIS` is the number someone must edit deliberately to let the
    migration go backwards, so it has to track reality."""
    assert len(literais_de_tela()) == MAX_LITERAIS


def test_every_language_translates_every_key():
    faltando = {
        idioma: sorted(set(en.TEXTOS) - set(textos))
        for idioma, textos in CATALOGOS.items()
        if set(en.TEXTOS) - set(textos)
    }
    assert not faltando, f"keys the source language defines and these do not: {faltando}"


def test_no_language_invents_a_key():
    """A key English dropped is dead weight: nothing reads it, and the next
    reader cannot tell it from a live one."""
    sobrando = {
        idioma: sorted(set(textos) - set(en.TEXTOS))
        for idioma, textos in CATALOGOS.items()
        if set(textos) - set(en.TEXTOS)
    }
    assert not sobrando, f"keys with no English source: {sobrando}"


@pytest.mark.parametrize("idioma", sorted(CATALOGOS))
def test_every_translation_keeps_the_placeholders(idioma):
    campos = re.compile(r"\{(\w+)\}")
    divergentes = {}
    for chave, fonte in en.TEXTOS.items():
        traduzido = CATALOGOS[idioma].get(chave)
        if traduzido is None:
            continue
        if set(campos.findall(fonte)) != set(campos.findall(traduzido)):
            divergentes[chave] = (sorted(campos.findall(fonte)),
                                  sorted(campos.findall(traduzido)))
    assert not divergentes, f"{idioma}: placeholders that do not match English: {divergentes}"


def test_portuguese_carries_no_accents():
    """The project's long-standing rule for anything read on screen."""
    acentuadas = {
        chave: texto for chave, texto in CATALOGOS["pt"].items()
        if any(c in texto for c in "áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ")
    }
    assert not acentuadas, f"accents in the Portuguese catalogue: {acentuadas}"


def test_english_is_the_default():
    """Not a preference: `t()` falls back to English for an untranslated key,
    which only works if English is the one language guaranteed complete."""
    assert IDIOMA_PADRAO == "en"
    assert set(CATALOGOS[IDIOMA_PADRAO]) == set(en.TEXTOS)
