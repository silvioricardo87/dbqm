"""Marcadores de veredito e de status de operacao.

Sao dois eixos diferentes e nao compartilham paleta: DIFERE nao e um aviso e
AUSENTE nao e um erro. Cada marcador leva glifo alem da cor, para que o estado
nao dependa de o leitor distinguir tons.

Fechado de proposito, no mesmo espirito de `dialog.py`: quem precisa de um
estado que nao esta aqui precisa de uma variante nova neste modulo, nunca de
markup montado a mao em outro arquivo — por isso `mark_verdict` e
`mark_operation` rejeitam qualquer entrada fora do seu proprio vocabulario.
O eixo inteiro (`$veredito-*`/`$ds-op-failure` fora daqui) e vigiado por
`tests/ui/test_widgets.py::test_no_hand_rolled_verdict_markup_outside_the_component`.
"""
from __future__ import annotations

from dbqm.ui.utils import escape_markup

VERDICTS: dict[str, tuple[str, str]] = {
    # status -> (glifo, token)
    "match": ("=", "$ds-verdict-match"),
    "match-normalized": ("~", "$ds-verdict-match"),
    "diff": ("!", "$ds-verdict-diff"),
    "absent": ("-", "$ds-verdict-absent"),
}

OPERATIONS: dict[str, tuple[str, str]] = {
    # estado -> (glifo, token); token vazio ("") significa "sem cor, so peso"
    "ok": ("", ""),
    "failure": ("x", "$ds-op-failure"),
    "running": ("*", "$ds-identity"),
}


def mark_verdict(status: str, *, label: str | None = None) -> str:
    """Markup do veredito de comparacao, com glifo e cor.

    `igual` (OK) usa o mesmo token de `texto-apoio` de proposito: um
    resultado igual nao carrega alarme nenhum, so o glifo confirma o estado.

    `texto`, se passado, troca so o ROTULO — glifo e token continuam vindo
    de `VERDICTS`, fechados. Existe para o chamador que ja tem sua propria
    palavra para o estado (`"Iguais:"`, `"DIVERGENTE"`, ...) e precisa
    pinta-la sem duplicar o rotulo padrao do componente ao lado dela. Nao
    expõe o token em si — so o componente sabe qual token vai com qual
    status, entao a cor nunca se descola do estado que ela representa.
    `texto` e sempre escapado antes de entrar no markup: o parametro existe
    para um rotulo, nunca para injetar markup novo, e nenhum chamador de
    hoje passa nada alem de literal fixo — mas nada impede um futuro
    chamador de passar texto vindo de dado, e um `[/]`/token ali dentro
    fecharia a tag cedo demais.
    """
    if status not in VERDICTS:
        raise ValueError(f"status desconhecido: {status!r}; use {sorted(VERDICTS)}")
    glyph, token = VERDICTS[status]
    text = escape_markup(label) if label is not None else {
        "match": "OK",
        "match-normalized": "OK*",
        "diff": "DIFERE",
        "absent": "AUSENTE",
    }[status]
    return f"[{token}]{glyph} {text}[/]"


def mark_operation(state: str, *, label: str | None = None) -> str:
    """Markup do status de uma operacao (execucao de consulta/grupo).

    `ok` sai sem tinta de alarme — sucesso e a ausencia de alarme, so
    `falha` recebe cor de erro — mas mantem o PESO (`[bold]`): sem cor nao
    e sem legibilidade. A mesma regra que os call sites manuais de
    `adhoc.py`, `exec_routine.py` e `package_editor.py` ja aplicam com
    `[bold]` cravado ao lado do texto de sucesso. `executando` recebe a cor
    de identidade, para diferenciar "em andamento" de "resultado".

    `texto`, se passado, troca so o ROTULO (mesma razao e mesmo escape de
    `mark_verdict`).
    """
    if state not in OPERATIONS:
        raise ValueError(f"estado desconhecido: {state!r}; use {sorted(OPERATIONS)}")
    glyph, token = OPERATIONS[state]
    text = escape_markup(label) if label is not None else {
        "ok": "OK", "failure": "FALHA", "running": "executando",
    }[state]
    body = f"{(glyph + ' ') if glyph else ''}{text}"
    if not token:
        return f"[bold]{body}[/]"
    return f"[{token}]{body}[/]"
