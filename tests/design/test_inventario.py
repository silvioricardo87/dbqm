"""Teste 4 do design system: inventario de componentes.

Falha quando aparece um segundo componente com a mesma funcao, e quando o
chrome que o Dialog entrega volta a ser escrito a mao.

O veredito ja tem guarda propria em
`tests/ui/test_widgets.py::test_veredito_sem_markup_montado_a_mao_fora_do_componente`
— nao duplicado aqui.
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2] / "dbqm"

# ---------------------------------------------------------------------------
# "Nenhum X" escrito a mao em vez de EmptyState
# ---------------------------------------------------------------------------
#
# Um grep linha-a-linha por "Nenhum"/"Nenhuma" produz falso positivo: a
# palavra aparece legitimamente em prosa (docstrings, textos de notificacao,
# rotulo de botao "Nenhum (remover)"). O que importa e a palavra dentro de
# uma chamada Static(...)/add_row(...)/update(...) — e essas chamadas podem
# atravessar varias linhas, entao a varredura precisa ser multi-linha
# (parenteses balanceados sobre o texto inteiro do arquivo, nao linha a
# linha). Uma varredura ingenua ja deixou passar 4 casos escondidos assim.
_CHAMADA = re.compile(r"\b(?:Static|add_row|update)\s*\(")
_PALAVRA_VAZIO = re.compile(r"Nenhum[a-z]*", re.I | re.S)

# Isencoes: "Nenhum X" dentro de uma chamada vigiada que NAO e estado vazio
# de lista — sao leituras de status de um unico campo, sem "criar o
# primeiro" possivel. Isentas com o motivo, para ninguem "corrigir" de volta.
ISENCOES_ESTADO_VAZIO = {
    # history.py: "Nenhum registro selecionado" e o placeholder de
    # nada-selecionado do painel de detalhe — aparece mesmo com a tabela
    # cheia de linhas, quando nenhuma esta destacada. Nao ha "criar o
    # primeiro" para "destacar uma linha"; EmptyState nao se aplica.
    "dbqm/ui/screens/history.py",
    # settings.py: "Client em uso: nenhum encontrado" e leitura de status de
    # configuracao (qual Instant Client esta ativo), um campo entre varios
    # na tela de Settings — nao uma lista vazia com acao de criar o
    # primeiro item.
    "dbqm/ui/screens/settings.py",
}


def _chamadas_vigiadas(texto: str):
    """Rende `(posicao, texto_da_chamada)` para cada Static(/add_row(/update(
    do arquivo, com parenteses balanceados — multi-linha por construcao,
    porque o balanceamento anda pelo texto inteiro sem parar em quebra de
    linha."""
    for m in _CHAMADA.finditer(texto):
        inicio_parens = m.end() - 1
        profundidade = 0
        fim = None
        for i in range(inicio_parens, len(texto)):
            if texto[i] == "(":
                profundidade += 1
            elif texto[i] == ")":
                profundidade -= 1
                if profundidade == 0:
                    fim = i
                    break
        if fim is not None:
            yield m.start(), texto[m.start() : fim + 1]


def test_estado_vazio_nao_e_escrito_a_mao():
    """"Nenhum X" solto em Static/add_row/update e o antipadrao que o
    EmptyState resolve."""
    fora = []
    for arquivo in sorted((RAIZ / "ui").rglob("*.py")):
        if arquivo.name == "empty_state.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        rel = arquivo.relative_to(RAIZ.parent).as_posix()
        for pos, chamada in _chamadas_vigiadas(texto):
            if not _PALAVRA_VAZIO.search(chamada):
                continue
            if rel in ISENCOES_ESTADO_VAZIO:
                continue
            linha = texto.count("\n", 0, pos) + 1
            fora.append(f"{rel}:{linha}")
    assert not fora, f"estado vazio escrito a mao em: {fora}"


# ---------------------------------------------------------------------------
# Moldura de dialogo (`border: thick`) escrita a mao fora do Dialog
# ---------------------------------------------------------------------------
#
# `dialog.py` e o unico arquivo excluido: la, "border: thick" aparece tanto
# no DEFAULT_CSS de verdade (que e o dono legitimo dessa moldura agora)
# quanto na docstring que explica por que o componente existe. Excluir o
# arquivo inteiro cobre as duas ocorrencias de uma vez, sem precisar
# distinguir CSS de prosa.


def test_moldura_de_dialog_existe_em_um_lugar_so():
    fora = []
    for arquivo in sorted(RAIZ.rglob("*.py")):
        if arquivo.name == "dialog.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "border: thick" in texto:
            fora.append(arquivo.relative_to(RAIZ.parent).as_posix())
    assert not fora, f"moldura de dialog escrita a mao em: {fora}"
