"""O CLI e o terceiro consumidor dos tokens, ao lado da TUI e do relatorio."""
import io

from rich.console import Console

from dbqm.cli import tema_rich
from dbqm.design.tokens import TOKENS_ESCURO


def test_tema_rich_expoe_um_estilo_por_token():
    estilos = tema_rich().styles
    for chave in TOKENS_ESCURO:
        assert chave.replace("-", ".") in estilos, f"token {chave} nao chega ao CLI"


def test_estilo_de_veredito_renderiza_a_cor_do_token():
    console = Console(
        theme=tema_rich(), file=io.StringIO(),
        force_terminal=True, color_system="truecolor", width=40,
    )
    console.print("[veredito.difere]DIFERE[/]")
    esperado = TOKENS_ESCURO["veredito-difere"].lstrip("#")
    rgb = ";".join(str(int(esperado[i:i + 2], 16)) for i in (0, 2, 4))
    assert rgb in console.file.getvalue()
