"""Tests for UI utilities."""
from dbqm.ui.utils import sanitize_id, escape_markup, prefixo_comum_de_pastas


def test_sanitize_id_ascii():
    assert sanitize_id("hello-world") == "hello-world"


def test_sanitize_id_accents():
    assert sanitize_id("investigacao-apolice") == "investigacao-apolice"


def test_sanitize_id_accents_unicode():
    result = sanitize_id("investigacao-apolice")
    assert result == "investigacao-apolice"


def test_sanitize_id_spaces():
    assert sanitize_id("my folder name") == "my-folder-name"


def test_sanitize_id_special_chars():
    assert sanitize_id("test@#$%^&*()") == "test"


def test_sanitize_id_starts_with_number():
    assert sanitize_id("123abc").startswith("id-")


def test_sanitize_id_empty():
    result = sanitize_id("")
    assert result  # should not be empty


def test_sanitize_id_unicode_only():
    result = sanitize_id("\u65e5\u672c\u8a9e")
    assert result  # should not be empty, fallback to "item" or "id-"


def test_sanitize_id_cedilla():
    assert "c" in sanitize_id("a\u00e7\u00e3o")


def test_sanitize_id_tilde():
    assert sanitize_id("n\u00e3o") == "nao"


def test_sanitize_id_accented_folder():
    """Accented folder names should produce valid IDs."""
    result = sanitize_id("Investiga\u00e7\u00e3o")
    assert result  # not empty
    assert all(c.isalnum() or c in "-_" for c in result)
    # Should not start with a digit
    assert not result[0].isdigit()


def test_sanitize_id_slash_and_space():
    """Slashes and spaces should be converted to hyphens."""
    result = sanitize_id("folder/sub folder")
    assert " " not in result
    assert "/" not in result


def test_escape_markup_brackets():
    assert escape_markup("test[bold]") == "test\\[bold\\]"


def test_escape_markup_clean():
    assert escape_markup("hello") == "hello"


def test_escape_markup_nested():
    assert escape_markup("[red]error[/]") == "\\[red\\]error\\[/\\]"


# ---------------------------------------------------------------------------
# prefixo_comum_de_pastas
# ---------------------------------------------------------------------------
#
# Existia sem teste nenhum: toda pasta usada na suite de UI era livre de
# prefixo ("Grupo A", "FolderA", "Pasta0") e nenhuma continha "/", entao o
# ramo de elisao nunca rodava — trocar o corpo da funcao por `return ""`
# mantinha 326 testes verdes. Estes casos, mais o teste de tela que le o
# ROTULO pintado, sao o que faz esse mutante morrer.


def test_prefixo_comum_de_pastas_familia_unica():
    """O caso que motivou a funcao: uma familia domina a lista inteira."""
    assert prefixo_comum_de_pastas([
        "Mapfre Sustentacao/Faturamento",
        "Mapfre Sustentacao/Apolice",
    ]) == "Mapfre Sustentacao/"


def test_prefixo_comum_de_pastas_varios_segmentos():
    """O prefixo cresce por segmento, nao para no primeiro."""
    assert prefixo_comum_de_pastas(["A/B/C", "A/B/D"]) == "A/B/"


def test_prefixo_comum_de_pastas_sem_nada_em_comum():
    """Duas familias lado a lado: o prefixo comum encolhe sozinho para ""
    e a lista volta a mostrar o caminho inteiro — a razao de o prefixo ser
    calculado a cada carga em vez de fixado como literal no codigo."""
    assert prefixo_comum_de_pastas(["Mapfre/Faturamento", "Interno/Backlog"]) == ""


def test_prefixo_comum_de_pastas_compara_segmento_nao_caractere():
    """"Fatura" e prefixo de "Faturamento" em caracteres, mas nao em
    segmentos — elidir aqui cortaria o comeco de um nome de pasta."""
    assert prefixo_comum_de_pastas(["Faturamento", "Fatura"]) == ""


def test_prefixo_comum_de_pastas_menos_de_duas():
    """Com zero ou uma pasta nao ha redundancia a eliminar: o unico rotulo
    da lista tem de aparecer inteiro."""
    assert prefixo_comum_de_pastas([]) == ""
    assert prefixo_comum_de_pastas(["Mapfre Sustentacao/Faturamento"]) == ""


def test_prefixo_comum_de_pastas_pasta_que_e_prefixo_da_irma():
    """Caso irmao: uma pasta E o prefixo comum da outra.

    O prefixo devolvido ("A/B/") nao se aplica a propria "A/B" — quem
    chama tem de checar `startswith` antes de cortar, e e isso que impede
    o rotulo de "A/B" de virar string vazia. A funcao devolve o prefixo
    correto; o `startswith` do chamador (query_exec.py/group_run.py) e
    load-bearing, nao defensivo."""
    assert prefixo_comum_de_pastas(["A/B", "A/B/C"]) == "A/B/"


def test_prefixo_comum_de_pastas_lista_repetida_devolveria_tudo():
    """Comportamento fixado, nao endossado: com a MESMA pasta repetida o
    prefixo comum e ela inteira, e cortar isso apagaria o rotulo.

    Nao ha guarda contra isso dentro da funcao de proposito — os dois
    chamadores passam `sorted(Counter(...))`, ou seja, chaves de um
    dicionario, que sao unicas por construcao. Com entradas unicas, o unico
    jeito de o prefixo cobrir uma pasta inteira e o caso irmao acima, onde
    o `startswith` do chamador ja salva o rotulo. Este teste existe para
    que, se um terceiro chamador passar uma lista com repeticoes um dia, a
    consequencia esteja escrita aqui em vez de aparecer como uma lista de
    rotulos em branco."""
    assert prefixo_comum_de_pastas(["A/B", "A/B"]) == "A/B/"
