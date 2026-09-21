"""User-facing text lives in the catalogue, and the catalogue stays honest.

Three jobs, and the division between the first two is the lesson of the
migration itself.

**By role.** `test_no_screen_takes_a_literal_instead_of_a_key` asks where a
string GOES: handed to a widget, a notification, a placeholder or a panel
title, it is screen text and belongs in `dbqm/i18n/`. This is the guard
that matters, because it does not care what language the literal is in --
English hard-coded in a widget is the same defect, and the one nobody
notices until a second language exists.

**By vocabulary.** The older ratchet asks what a string SAYS, matching a
list of Portuguese words. It is a heuristic and it failed the way heuristics
do: it reached zero with "Exportar como", "DE-PARA (Mapeamento de Valores)"
and "Exibindo valores originais (sem mapeamento)" still painted, none of
which carries one of its words. It is kept at zero anyway, because it looks
everywhere rather than only at known sinks -- a helper that builds a
sentence and returns it for someone else to render is outside the role
guard's reach and inside this one's.

**Integrity.** Every translation carries the keys the source language
defines, with the placeholders it defines, no Rich markup, and no accents in
Portuguese. A translation missing a `{nome}` renders a sentence with a hole
in it; a translation carrying a key English dropped is dead weight nobody
will notice.
"""
from __future__ import annotations

import ast
import re
from itertools import chain
from pathlib import Path

import pytest

from dbqm.i18n import CATALOGUES, DEFAULT_LANGUAGE, en

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Words that only appear in Portuguese screen text. Deliberately not a
#: language detector: it only has to be good enough to notice a sentence
#: someone typed straight into a widget.
WORDS = [
    "conexao", "conexoes", "consulta", "consultas", "avulso", "executar",
    "salvar", "remover", "voltar", "selecione", "informe", "registros",
    "grupos", "arquivo", "senha", "usuario", "configuracoes", "historico",
    "ferramentas", "parametro", "parametros", "resultado", "resultados",
    "nenhum", "nenhuma", "somente", "invalido", "encontrada", "encontrado",
    "obrigatorio", "sucesso", "falhou", "nao", "sao", "coluna", "colunas",
    "tabela", "rotina", "pacote", "registro", "vazio",
]
MARKER_WORD = re.compile(r"\b(" + "|".join(WORDS) + r")\b", re.IGNORECASE)

#: A `t("some.key")` call site, read as text rather than parsed: good enough
#: to collect the keys a module reaches, which is all this needs. The
#: negative lookbehind is a left boundary -- without it, `print("...")` and
#: `.get("...")` contribute phantom keys, because the pattern matches the
#: `t(` at the end of "prin`t(`" or ".ge`t(`" just as happily as a real call.
_KEY = re.compile(r'(?<![\w.])t\(\s*[\'"]([\w.]+)[\'"]')

#: Measured when the catalogue landed. This number goes DOWN as modules move
#: over, never up. Lowering it is the whole point.
MAX_LITERALS = 0

#: The catalogue itself is Portuguese by definition, and the design tokens
#: carry Portuguese token names that are identifiers, not screen text.
OUTSIDE = ("dbqm/i18n/",)

#: Portuguese that must stay Portuguese in every language. These two name
#: directories on the user's disk; translating them would write the next
#: export into a new folder beside the ones already there, and everything
#: exported until now would simply stop being where it was.
NAMES_ON_DISK = {
    ("dbqm/core/exporter.py", "consultas"),
    ("dbqm/core/exporter.py", "grupos"),
}


def _is_docstring(no, docstrings) -> bool:
    return id(no) in docstrings


def _docstrings(tree) -> set[int]:
    outside = set()
    for no in ast.walk(tree):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(no, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                outside.add(id(body[0].value))
    return outside


#: Keyword arguments whose value names a widget, never a label.
IDENTITY_KEYWORDS = {"id", "action_id", "classes", "key"}

#: Calls whose string arguments are selectors or ids.
IDENTITY_CALLS = {"query_one", "query", "query_exactly_one",
                          "switch_tab", "action_switch_tab", "open_tool",
                          "get_child_by_id", "get_widget_by_id", "mount_all"}


def _identifiers(tree) -> set[int]:
    """Nodes holding an identifier rather than screen text.

    By role: the value of `id=`/`action_id=`/`classes=`/`key=`, any string
    argument to a call that takes a selector or an id, and any string that
    looks like a CSS selector.
    """
    ids: set[int] = set()
    for no in ast.walk(tree):
        if isinstance(no, ast.keyword) and no.arg in IDENTITY_KEYWORDS:
            for child in ast.walk(no.value):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    ids.add(id(child))
        if isinstance(no, ast.Call):
            name = no.func.id if isinstance(no.func, ast.Name) else (
                no.func.attr if isinstance(no.func, ast.Attribute) else "")
            if name in IDENTITY_CALLS:
                for arg in no.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        ids.add(id(arg))
        if isinstance(no, ast.Compare):
            # `event.button.id == "create-query"`: the literal is the id
            # being matched, whatever side of the operator it sits on.
            sides = [no.left, *no.comparators]
            source = " ".join(ast.unparse(x) for x in sides)
            if re.search(r"\bid\b|_id\b|\bname\b|\bnome\b|\bchave\b|\bkey\b", source):
                for side in sides:
                    for child in ast.walk(side):
                        if isinstance(child, ast.Constant) and isinstance(child.value, str):
                            ids.add(id(child))
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
            text = no.value.strip()
            if text.startswith(("#", ".")) and " " not in text:
                ids.add(id(no))
            # A Textual id: lowercase words joined by hyphens, no spaces.
            # Nothing a screen shows is written that way.
            if re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)+", text):
                ids.add(id(no))
            # A Textual action string: `switch_tab('tab-connections')`.
            if re.fullmatch(r"[a-z_]+\(.*\)", text):
                ids.add(id(no))
    return ids


def screen_literals() -> list[tuple[str, int, str]]:
    """`(file, line, text)` for every Portuguese string constant still in the
    source. Docstrings are excluded: they are English by rule and nobody
    reads them on a screen."""
    found = []
    for py in sorted((REPO_ROOT / "dbqm").rglob("*.py")):
        relative = py.relative_to(REPO_ROOT).as_posix()
        if relative.startswith(OUTSIDE):
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        docstrings = _docstrings(tree)
        identifiers = _identifiers(tree)
        for no in ast.walk(tree):
            if (isinstance(no, ast.Constant) and isinstance(no.value, str)
                    and not _is_docstring(no, docstrings)
                    and id(no) not in identifiers):
                text = no.value.strip()
                if (len(text) > 3 and "\n" not in text
                        and MARKER_WORD.search(text)
                        and (relative, text) not in NAMES_ON_DISK):
                    found.append((relative, no.lineno, text))
    return found


def test_the_literal_count_only_falls():
    remaining = screen_literals()
    assert len(remaining) <= MAX_LITERALS, (
        f"{len(remaining)} Portuguese literals left in dbqm/, up from "
        f"{MAX_LITERALS}. New user-facing text goes in dbqm/i18n/, not in a "
        f"widget. First few: {remaining[:3]}"
    )


def test_the_count_matches_what_is_there():
    """`MAX_LITERAIS` is the number someone must edit deliberately to let the
    migration go backwards, so it has to track reality."""
    assert len(screen_literals()) == MAX_LITERALS


def test_every_language_translates_every_key():
    missing_ones = {
        language: sorted(set(en.TEXTS) - set(texts))
        for language, texts in CATALOGUES.items()
        if set(en.TEXTS) - set(texts)
    }
    assert not missing_ones, f"keys the source language defines and these do not: {missing_ones}"


def test_no_language_invents_a_key():
    """A key English dropped is dead weight: nothing reads it, and the next
    reader cannot tell it from a live one."""
    left_over = {
        language: sorted(set(texts) - set(en.TEXTS))
        for language, texts in CATALOGUES.items()
        if set(texts) - set(en.TEXTS)
    }
    assert not left_over, f"keys with no English source: {left_over}"


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_translation_keeps_the_placeholders(language):
    # `{{campo}}` is not a placeholder: it is dbqm's own template syntax,
    # shown as an example, and the example name is meant to be translated.
    # `(?<!\{)\{(\w+)\}(?!\})` reads a single brace pair only.
    fields = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")
    divergent = {}
    for key, source in en.TEXTS.items():
        translated = CATALOGUES[language].get(key)
        if translated is None:
            continue
        if set(fields.findall(source)) != set(fields.findall(translated)):
            divergent[key] = (sorted(fields.findall(source)),
                                  sorted(fields.findall(translated)))
    assert not divergent, f"{language}: placeholders that do not match English: {divergent}"


def test_portuguese_carries_no_accents():
    """The project's long-standing rule for anything read on screen."""
    accented = {
        key: text for key, text in CATALOGUES["pt"].items()
        if any(c in text for c in "áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ")
    }
    assert not accented, f"accents in the Portuguese catalogue: {accented}"


#: `connection.py:_print_connection_outcome` looks these up through
#: `_CONNECTION_OUTCOME_KEY[outcome]` -- a key held in a dict, never typed
#: as a literal inside a `t(...)` call -- so `_KEY` cannot see them. They are
#: CLI-printed (the Rich branch of `_print_connection_outcome`, in
#: `dbqm/cli/commands/connection.py`) and belong in the same ASCII check as
#: every key `_KEY` finds by pattern.
_DICT_HELD_CLI_KEYS = {"connection.created", "connection.updated", "connection.removed"}


def test_a_key_the_cli_prints_is_plain_ascii():
    """The console the CLI prints to is not always UTF-8.

    Measured on Windows: the em dash in `cli.description` left the process
    as a single cp1252 byte, which a UTF-8 terminal draws as a replacement
    character; an emoji would have raised `UnicodeEncodeError` outright.
    So a key whose name appears as a literal in a `t()` call under
    `dbqm/cli/` or `dbqm/ops/` stays ASCII, plus the handful of keys named
    in `_DICT_HELD_CLI_KEYS` that reach `t()` only through a dict lookup and
    so are invisible to the pattern that finds the rest.

    Deliberately NOT repo-wide: the TUI's tab emoji are identity, Textual
    renders them correctly, and a blanket rule would forbid them.
    """
    from dbqm.i18n import en, pt

    keys = set(_DICT_HELD_CLI_KEYS)
    for path in chain((REPO_ROOT / "dbqm" / "cli").rglob("*.py"),
                       (REPO_ROOT / "dbqm" / "ops").rglob("*.py")):
        keys.update(_KEY.findall(path.read_text(encoding="utf-8")))
    offenders = []
    for catalogue, name in ((en.TEXTS, "en"), (pt.TEXTS, "pt")):
        for key in sorted(keys):
            value = catalogue.get(key, "")
            if not value.isascii():
                offenders.append((name, key, value))
    assert not offenders, offenders


def test_english_is_the_default():
    """Not a preference: `t()` falls back to English for an untranslated key,
    which only works if English is the one language guaranteed complete."""
    assert DEFAULT_LANGUAGE == "en"
    assert set(CATALOGUES[DEFAULT_LANGUAGE]) == set(en.TEXTS)


def _module_level_t_calls(py: Path) -> list[int]:
    """Lines where `t(...)` runs as the module is imported."""
    source = py.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = []
    for no in tree.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # A call inside a def runs when the def is called, which is the
            # whole point. A class body, though, executes at import.
            if not isinstance(no, ast.ClassDef):
                continue
            for body in no.body:
                if isinstance(body, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                lines.extend(_ts_in(body))
            continue
        lines.extend(_ts_in(no))
    return lines


def _ts_in(no) -> list[int]:
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
    culprits = {}
    for py in sorted((REPO_ROOT / "dbqm").rglob("*.py")):
        relative = py.relative_to(REPO_ROOT).as_posix()
        if relative.startswith(OUTSIDE):
            continue
        lines = _module_level_t_calls(py)
        if lines:
            culprits[relative] = lines
    assert not culprits, (
        f"t() runs at import time in {culprits}. Wrap it in a function so the "
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
    offenders = {
        f"{language}:{key}": text
        for language, catalogue in CATALOGUES.items()
        for key, text in catalogue.items()
        if "[/" in text
    }
    assert not offenders, (
        f"Rich markup in the catalogue: {offenders}. Wrap the t() call at the "
        f"call site, or pass the marked-up fragment in as a field."
    )


# ---------------------------------------------------------------------------
# The structural guard
# ---------------------------------------------------------------------------
#
# `literais_de_tela` above asks what a string says, which is a heuristic and
# was always going to end this way: it reached zero while "Exportar como",
# "DE-PARA (Mapeamento de Valores)" and "Exibindo valores originais (sem
# mapeamento)" were still painted, because none of them carries one of its
# words. This asks where the string GOES instead. A literal handed to a
# widget, a notification or a panel title is screen text in any language.

#: Calls whose first positional argument is rendered.
SINKS_POSITIONAL = frozenset({
    "Static", "Button", "Label", "notify", "add_column", "Collapsible",
    "TabPane", "Checkbox", "RadioButton", "ListItem", "Markdown", "Tab",
    "Dialog", "ConfirmModal", "ErrorModal", "TextInputModal", "Action",
    "EmptyState", "Panel", "PathLabel", "Digits",
    # `console.print` is how the CLI paints; a literal in one is a message
    # in the terminal exactly as a literal in a `Static` is one on a screen.
    "print",
    # `ProgressIndicator.start(...)` and `Static.update(...)`: the widget
    # already exists, so its text arrives through a method rather than a
    # constructor. Six progress messages lived here, seen by nothing.
    "start", "update",
})

#: Attributes that are rendered when assigned. None of these carries a
#: literal today; the check is here so the next one is not a discovery.
RENDERED_ATTRIBUTES = frozenset({
    "border_title", "border_subtitle", "sub_title", "tooltip", "placeholder",
})

#: Calls that forward their remaining arguments to another callable. The
#: sink is named by the first argument, so the check has to look past it:
#: `call_from_thread(self.notify, "Erro ao importar: ...")` is a
#: notification, and reading the call by its own name says nothing.
SINKS_THAT_FORWARD = frozenset({"call_from_thread", "run_worker", "call_later"})

#: Calls where *every* positional argument becomes a cell someone reads.
#: `add_row` is how the history table said "grupo" while the CLI printed
#: "group" for the same field -- a row is as much screen text as a label.
#: `add_columns` is the plural of `add_column`, and a whole header row
#: in Portuguese sat behind that letter.
SINKS_ALL_POSITIONAL = frozenset({"add_row", "add_columns"})

#: Keyword arguments whose value is rendered.
SINKS_KEYWORD = frozenset({
    "placeholder", "title", "border_title", "prompt", "sub_title",
    "what", "why", "action_label", "message", "tooltip",
})

#: Files that build code rather than screens: PL/SQL templates, generated
#: SQL comments in an extracted `.sql`. Their `append`s are the artifact,
#: not a message, so only the keyword/positional sinks are checked there.
OUTSIDE_THE_APPEND_CHECK = frozenset({
    "dbqm/core/package_editor.py",   # PL/SQL skeletons
    "dbqm/core/object_browser.py",   # the anonymous block `call` sends
    "dbqm/core/ddl_extractor.py",    # `-- Type:` headers inside the .sql
    "dbqm/core/exporter.py",         # the txt export's own table drawing
    "dbqm/core/html_report.py",      # HTML fragments
    "dbqm/cli/render.py",            # table rows assembled for Rich
})

#: Words that are the same in every language: product names, formats,
#: SQL keywords, symbols. A sink may take one of these directly.
NEUTRAL = frozenset({
    "dbqm",
    "SQL", "CSV", "JSON", "TXT", "HTML", "XML", "OK", "DBMS_OUTPUT",
    "Spec", "Body", "Wizard", "PROCEDURE", "FUNCTION", "PACKAGE", "TABLE",
    "VIEW", "COMMIT", "ROLLBACK", "Oracle", "PostgreSQL", "MySQL",
    "SQL Server", "SQLite", "Oracle Instant Client", "Multi-Exec",
    "PK", "FK ->",  # database terms, not words
    "Flat/Pivot", "+", "-", "#", "*", "",
})


#: Nodes that open a scope of their own. A name assigned inside one is not
#: the same name outside it.
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _branches(no):
    """Every value an expression can evaluate to, flattened.

    `x if cond else y` and `x or y` each carry two, and a screen only
    ever sees one of them -- so both have to be looked at. Anything else
    is its own single value.
    """
    if isinstance(no, ast.IfExp):
        return [*_branches(no.body), *_branches(no.orelse)]
    if isinstance(no, ast.BoolOp):
        return [b for v in no.values for b in _branches(v)]
    return [no]


def _visible_literals(tree) -> dict[ast.Call, dict[str, list[ast.Constant]]]:
    """For every call, the plain string literals its scope binds to a name.

    Three strings reached a screen through a variable and neither half of
    this guard saw them: `tipo = "grupo"` handed to `add_row`, and a
    version that fell back to `"desconhecida"` before going into a
    translated sentence as a field. The sink check reads the argument at
    the call site, and the argument was a name.

    Only `x = "literal"` counts, and a name that is *also* assigned an
    expression anywhere in its scope counts for nothing -- what it holds
    at the call is then a question of control flow, not of reading. Scope
    matters for the same reason: `build()` sets `mode = "direct"` as a
    default and `validate()` echoes the user's own `mode` back in an error
    message, and they are two different names that happen to share
    spelling.
    """
    def _own_nodes(scope):
        """The nodes of one scope, without descending into a nested one."""
        stack = list(ast.iter_child_nodes(scope))
        while stack:
            no = stack.pop()
            yield no
            if not isinstance(no, SCOPES):
                stack.extend(ast.iter_child_nodes(no))

    def _assignments(nos):
        constants: dict[str, list[ast.Constant]] = {}
        computed: set[str] = set()
        for no in nos:
            if isinstance(no, ast.Assign):
                targets = no.targets
            elif isinstance(no, ast.AnnAssign) and no.value is not None:
                targets = [no.target]
            else:
                continue
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                literais = [b for b in _branches(no.value)
                            if isinstance(b, ast.Constant) and isinstance(b.value, str)]
                if literais:
                    # A conditional counts for its literal branches: what
                    # `folder or "(no folder)"` puts on screen when the
                    # folder is empty is exactly that string.
                    constants.setdefault(target.id, []).extend(literais)
                else:
                    computed.add(target.id)
        return {name: cs for name, cs in constants.items() if name not in computed}

    from_module = _assignments(_own_nodes(tree))
    by_call: dict[ast.Call, dict[str, list[ast.Constant]]] = {}
    for scope in [tree] + [n for n in ast.walk(tree) if isinstance(n, SCOPES)]:
        nos = list(_own_nodes(scope))
        visible = {**from_module, **_assignments(nos)}
        for no in nos:
            if isinstance(no, ast.Call):
                by_call[no] = visible
    return by_call


def _sinks_with_a_literal(py: Path) -> list[tuple[int, str, str]]:
    """`(line, sink, text)` for every bare literal handed to a screen."""
    source = py.read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = []
    visible_ones = _visible_literals(tree)

    def _raw_text(no):
        """The literal text, or None when the value is not a bare literal."""
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            return no.value
        if isinstance(no, ast.JoinedStr):
            # An f-string is bare only if some literal piece carries a word;
            # `f"[dim]{t(...)}[/dim]"` is markup around a lookup.
            pieces = [p.value for p in no.values
                       if isinstance(p, ast.Constant) and isinstance(p.value, str)]
            joined = "".join(pieces)
            sem_markup = re.sub(r"\[[^]]*]", "", joined)
            return sem_markup if re.search(r"[A-Za-z]{2,}", sem_markup) else None
        return None

    relative = py.relative_to(REPO_ROOT).as_posix()
    checks_append = relative not in OUTSIDE_THE_APPEND_CHECK

    for no in ast.walk(tree):
        if isinstance(no, ast.Assign):
            for tgt in no.targets:
                if isinstance(tgt, ast.Attribute) and tgt.attr in RENDERED_ATTRIBUTES:
                    text = _raw_text(no.value)
                    clean = re.sub(r"\[[^]]*]", "", text or "").strip()
                    if clean and re.search(r"[A-Za-z]{2,}", clean) and clean not in NEUTRAL:
                        found.append((no.lineno, f".{tgt.attr}=", clean))
            continue
        if not isinstance(no, ast.Call):
            continue
        name = no.func.id if isinstance(no.func, ast.Name) else (
            no.func.attr if isinstance(no.func, ast.Attribute) else "")

        targets = []
        if name in SINKS_POSITIONAL and no.args:
            targets.append((name, no.args[0]))
        if name in SINKS_ALL_POSITIONAL:
            targets += [(name, arg) for arg in no.args]
        if name in SINKS_THAT_FORWARD:
            targets += [(name, arg) for arg in no.args[1:]]
        # Text accumulated in a list and rendered later. A sentence appended
        # to `lines` is a message; a fragment of SQL being assembled is not,
        # which is what `FORA_DO_APPEND` separates.
        if checks_append and name in ("append", "extend", "insert") and no.args:
            for arg in no.args:
                pieces = arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]
                for piece in pieces:
                    targets.append((name, piece))
        for kw in no.keywords:
            if kw.arg in SINKS_KEYWORD:
                targets.append((f"{name}.{kw.arg}", kw.value))
            # A field handed to `t()` is rendered inside the translated
            # sentence, so it is screen text too -- and it is the one spot
            # where a hard-coded word hides behind a key that looks right.
            elif name == "t" and kw.arg:
                targets.append((f"t.{kw.arg}", kw.value))

        # A name is followed one step back to what its scope assigns it.
        literals = visible_ones.get(no, {})
        expanded = []
        for label, target in targets:
            if isinstance(target, ast.Name) and target.id in literals:
                expanded += [(f"{label} <- {target.id}", c)
                               for c in literals[target.id]]
            else:
                expanded += [(label, b) for b in _branches(target)]

        for label, target in expanded:
            text = _raw_text(target)
            if text is None:
                continue
            clean = re.sub(r"\[[^]]*]", "", text).strip()
            if not re.search(r"[A-Za-z]{2,}", clean) or clean in NEUTRAL:
                continue
            if re.fullmatch(r"https?://\S+", clean):
                # A URL has letters in it and is the same in every
                # language; the sentence around it is what gets translated.
                continue
            if label.split(" <- ")[0] in ("append", "extend", "insert") and " " not in clean:
                # A single word appended to a list is a column key or a
                # token, not a sentence someone reads.
                continue
            found.append((target.lineno, label, clean))
    return found


def test_no_screen_takes_a_literal_instead_of_a_key():
    """Every rendered string comes from the catalogue.

    Detection is by role, not by vocabulary: whatever language a literal is
    written in, if it is handed to `Button(...)`, `notify(...)`, a
    `placeholder=` or a panel title, someone reads it off a screen. English
    text hard-coded in a widget is the same defect as Portuguese text hard-
    coded in a widget -- it is simply the one nobody notices until a second
    language exists.

    `NEUTROS` holds what is genuinely the same everywhere: product names,
    file formats, SQL keywords, single symbols.
    """
    offenders = {}
    for py in sorted((REPO_ROOT / "dbqm").rglob("*.py")):
        relative = py.relative_to(REPO_ROOT).as_posix()
        if relative.startswith(OUTSIDE):
            continue
        found = _sinks_with_a_literal(py)
        if found:
            offenders[relative] = found
    assert not offenders, (
        f"screen text written straight into a widget: {offenders}. "
        f"It belongs in dbqm/i18n/, reached through t()."
    )


def test_every_call_site_passes_the_fields_its_key_declares():
    """`t("x.y", name=...)` against what `x.y` actually spells.

    `str.format` raises `KeyError` for a field the caller did not pass, and
    the caller only finds out when that message renders -- which for an
    error path can be the first time anything goes wrong in production. A
    field passed but not declared is the quieter half: it is silently
    dropped, so a message loses the value it was supposed to carry and
    nothing says so.

    This also makes renaming a placeholder safe: the text in `en.py`, the
    same key in `pt.py` and the call's keywords are the three places that
    have to agree, and two of them are checked here and by
    `test_the_same_placeholders_in_every_language`.

    Only literal keys are checked. A key built at runtime (`_OUTCOME_KEY[x]`)
    is out of reach of a static check, by nature.
    """
    problems = []
    for py in sorted((REPO_ROOT / "dbqm").rglob("*.py")):
        relative = py.relative_to(REPO_ROOT).as_posix()
        if relative.startswith(OUTSIDE):
            continue
        for no in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                    and no.func.id == "t" and no.args):
                continue
            key = no.args[0]
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            if key.value not in en.TEXTS:
                problems.append(f"{relative}:{no.lineno} unknown key {key.value!r}")
                continue
            fields = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")
            declared = set(fields.findall(en.TEXTS[key.value]))
            passed_in = {kw.arg for kw in no.keywords if kw.arg}
            if declared != passed_in:
                problems.append(
                    f"{relative}:{no.lineno} {key.value}: declares "
                    f"{sorted(declared)}, receives {sorted(passed_in)}"
                )
    assert not problems, "t() calls that do not match their key: " + "; ".join(problems)
