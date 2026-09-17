"""The override list may shrink. It may never grow.

`[tool.mypy] strict = true` makes every module strict unless it is named in
the `ignore_errors` override. Without this test that list is a suggestion,
and the first person under a deadline adds a line to it -- which is how a
ratchet becomes a blanket.

Lives under `tests/design/` alongside the other repo-wide static guards
(`test_inventory.py`, `test_layout_inventory.py`) so it runs as part of the
`tests/models tests/design` slice with no change to that command.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

#: Measured when the ratchet landed. This number goes DOWN as modules are
#: typed, never up. Lowering it is the whole point; raising it needs a very
#: good reason written next to it.
MAX_LEGACY_MODULES = 35


def _legacy_modules() -> list[str]:
    """Every module exempted by every `ignore_errors` override.

    mypy honours all `[[tool.mypy.overrides]]` blocks, so reading only the
    first one would leave a side door open: a second `ignore_errors` block
    would exempt modules that these tests never see.
    """
    raiz = Path(__file__).resolve().parents[2]
    config = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    legado: list[str] = []
    for bloco in config["tool"]["mypy"].get("overrides", []):
        if bloco.get("ignore_errors"):
            modulo = bloco["module"]
            legado.extend([modulo] if isinstance(modulo, str) else modulo)
    return legado


def test_the_legacy_list_has_not_grown():
    legado = _legacy_modules()
    assert len(legado) <= MAX_LEGACY_MODULES, (
        f"{len(legado)} modules are exempt from strict typing, up from "
        f"{MAX_LEGACY_MODULES}. The list shrinks; it does not grow. A new "
        "module is strict from its first line."
    )


def test_every_exempt_module_exists():
    """A stale entry silently exempts nothing and hides the real count."""
    raiz = Path(__file__).resolve().parents[2]
    for modulo in _legacy_modules():
        caminho = raiz / (modulo.replace(".", "/") + ".py")
        assert caminho.exists(), (
            f"{modulo} is exempt from strict typing but does not exist. "
            "Remove the entry."
        )


def test_the_count_matches_the_list():
    """`MAX_LEGACY_MODULES` is the number someone must edit deliberately to
    grow the list, so it has to track reality."""
    assert len(_legacy_modules()) == MAX_LEGACY_MODULES
