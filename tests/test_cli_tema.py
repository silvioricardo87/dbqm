"""O CLI e o terceiro consumidor dos tokens, ao lado da TUI e do relatorio."""
import io

from rich.console import Console

from dbqm.cli import rich_theme
from dbqm.design.tokens import DARK_TOKENS


def test_rich_theme_exposes_one_style_per_token():
    estilos = rich_theme().styles
    for chave in DARK_TOKENS:
        assert chave.replace("-", ".") in estilos, f"token {chave} nao chega ao CLI"


def test_verdict_style_renders_the_token_color():
    console = Console(
        theme=rich_theme(), file=io.StringIO(),
        force_terminal=True, color_system="truecolor", width=40,
    )
    console.print("[ds.verdict.diff]DIFERE[/]")
    esperado = DARK_TOKENS["ds-verdict-diff"].lstrip("#")
    rgb = ";".join(str(int(esperado[i:i + 2], 16)) for i in (0, 2, 4))
    assert rgb in console.file.getvalue()
