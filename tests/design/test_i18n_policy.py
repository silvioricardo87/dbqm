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
MAX_LITERAIS = 0

#: The catalogue itself is Portuguese by definition, and the design tokens
#: carry Portuguese token names that are identifiers, not screen text.
FORA = ("dbqm/i18n/",)

#: Portuguese that must stay Portuguese in every language. These two name
#: directories on the user's disk; translating them would write the next
#: export into a new folder beside the ones already there, and everything
#: exported until now would simply stop being where it was.
NOMES_EM_DISCO = {
    ("dbqm/core/exporter.py", "consultas"),
    ("dbqm/core/exporter.py", "grupos"),
}


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


#: Keyword arguments whose value names a widget, never a label.
KEYWORDS_DE_IDENTIDADE = {"id", "action_id", "classes", "key"}

#: Calls whose string arguments are selectors or ids.
CHAMADAS_DE_IDENTIDADE = {"query_one", "query", "query_exactly_one",
                          "switch_tab", "action_switch_tab", "open_tool",
                          "get_child_by_id", "get_widget_by_id", "mount_all"}


def _identificadores(arvore) -> set[int]:
    """Nodes holding an identifier rather than screen text.

    By role: the value of `id=`/`action_id=`/`classes=`/`key=`, any string
    argument to a call that takes a selector or an id, and any string that
    looks like a CSS selector.
    """
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.keyword) and no.arg in KEYWORDS_DE_IDENTIDADE:
            for filho in ast.walk(no.value):
                if isinstance(filho, ast.Constant) and isinstance(filho.value, str):
                    ids.add(id(filho))
        if isinstance(no, ast.Call):
            nome = no.func.id if isinstance(no.func, ast.Name) else (
                no.func.attr if isinstance(no.func, ast.Attribute) else "")
            if nome in CHAMADAS_DE_IDENTIDADE:
                for arg in no.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        ids.add(id(arg))
        if isinstance(no, ast.Compare):
            # `event.button.id == "criar-consulta"`: the literal is the id
            # being matched, whatever side of the operator it sits on.
            lados = [no.left, *no.comparators]
            fonte = " ".join(ast.unparse(x) for x in lados)
            if re.search(r"\bid\b|_id\b|\bname\b|\bnome\b|\bchave\b|\bkey\b", fonte):
                for lado in lados:
                    for filho in ast.walk(lado):
                        if isinstance(filho, ast.Constant) and isinstance(filho.value, str):
                            ids.add(id(filho))
        if isinstance(no, ast.Tuple):
            # A route tuple: `("grupos", t("tools.manage_groups"), ...)`.
            # Where the labels come from the catalogue, the bare string
            # beside them is the key the screen routes on.
            tem_t = any(isinstance(e, ast.Call) and isinstance(e.func, ast.Name)
                        and e.func.id == "t" for e in no.elts)
            if tem_t:
                for e in no.elts:
                    if isinstance(e, ast.Constant) and isinstance(e.value, str):
                        ids.add(id(e))
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            texto = no.value.strip()
            if texto.startswith(("#", ".")) and " " not in texto:
                ids.add(id(no))
            # A Textual id: lowercase words joined by hyphens, no spaces.
            # Nothing a screen shows is written that way.
            if re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)+", texto):
                ids.add(id(no))
            # A Textual action string: `switch_tab('tab-conexoes')`.
            if re.fullmatch(r"[a-z_]+\(.*\)", texto):
                ids.add(id(no))
    return ids


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
        identificadores = _identificadores(arvore)
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Constant) and isinstance(no.value, str)
                    and not _e_docstring(no, docstrings)
                    and id(no) not in identificadores):
                texto = no.value.strip()
                if (len(texto) > 3 and "\n" not in texto
                        and MARCA.search(texto)
                        and (relativo, texto) not in NOMES_EM_DISCO):
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
    # `{{campo}}` is not a placeholder: it is dbqm's own template syntax,
    # shown as an example, and the example name is meant to be translated.
    # `(?<!\{)\{(\w+)\}(?!\})` reads a single brace pair only.
    campos = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")
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


def _chamadas_de_t_no_nivel_do_modulo(py: Path) -> list[int]:
    """Lines where `t(...)` runs as the module is imported."""
    fonte = py.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    linhas = []
    for no in arvore.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # A call inside a def runs when the def is called, which is the
            # whole point. A class body, though, executes at import.
            if not isinstance(no, ast.ClassDef):
                continue
            for corpo in no.body:
                if isinstance(corpo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                linhas.extend(_ts_em(corpo))
            continue
        linhas.extend(_ts_em(no))
    return linhas


def _ts_em(no) -> list[int]:
    return [f.lineno for f in ast.walk(no)
            if isinstance(f, ast.Call) and isinstance(f.func, ast.Name) and f.func.id == "t"]


def test_no_lookup_happens_at_import_time():
    """`t()` in a module-level constant freezes the language at import.

    Nothing raises, nothing is logged: the constant is built in whatever
    language was current when Python read the file -- the default, for every
    module imported before the app resolves the user's choice -- and it
    keeps that text for the life of the process. `connections.py` had its
    database-type list written that way.
    """
    culpados = {}
    for py in sorted((RAIZ / "dbqm").rglob("*.py")):
        relativo = py.relative_to(RAIZ).as_posix()
        if relativo.startswith(FORA):
            continue
        linhas = _chamadas_de_t_no_nivel_do_modulo(py)
        if linhas:
            culpados[relativo] = linhas
    assert not culpados, (
        f"t() runs at import time in {culpados}. Wrap it in a function so the "
        f"lookup happens after the language is resolved."
    )


def test_the_catalogue_carries_words_and_not_markup():
    """Rich tags belong to the call site, never to a catalogue value.

    Two reasons, and the second is the one that bit. A translator editing
    `pt.py` can unbalance `[bold]...[/]` and produce a screen of literal
    brackets -- a tag is not language, and nothing about editing prose
    suggests the brackets are load-bearing.

    And `tests/ui/test_widgets.py` holds two guards that read
    `dbqm/ui/**` looking for exactly this markup: one pins the `[bold]` of
    the success headers, the other counts every `$ds-op-failure` so a new
    one cannot appear unnoticed. Markup moved into a catalogue value makes
    both of them scan a file that no longer contains what they watch. They
    do not fail; they go quiet, which is worse.

    Markup reaches a message through a placeholder the caller fills, or it
    wraps the whole `t()` call. `[y/N]` in a confirmation prompt is not
    markup: this looks for a closing tag, which every Rich span has and no
    prompt does.
    """
    ofensores = {
        f"{idioma}:{chave}": texto
        for idioma, catalogo in CATALOGOS.items()
        for chave, texto in catalogo.items()
        if "[/" in texto
    }
    assert not ofensores, (
        f"Rich markup in the catalogue: {ofensores}. Wrap the t() call at the "
        f"call site, or pass the marked-up fragment in as a field."
    )
