"""The CLI is the tokens' third consumer, beside the TUI and the report."""
import io

from rich.console import Console

from dbqm.cli import rich_theme
from dbqm.design.tokens import DARK_TOKENS


def test_rich_theme_exposes_one_style_per_token():
    styles = rich_theme().styles
    for key in DARK_TOKENS:
        assert key.replace("-", ".") in styles, f'token {key} never reaches the CLI'


def test_verdict_style_renders_the_token_color():
    console = Console(
        theme=rich_theme(), file=io.StringIO(),
        force_terminal=True, color_system="truecolor", width=40,
        no_color=False,
    )
    console.print("[ds.verdict.diff]DIFERE[/]")
    expected = DARK_TOKENS["ds-verdict-diff"].lstrip("#")
    rgb = ";".join(str(int(expected[i:i + 2], 16)) for i in (0, 2, 4))
    assert rgb in console.file.getvalue()
