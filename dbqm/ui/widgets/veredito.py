"""Marcadores de veredito e de status de operacao.

Sao dois eixos diferentes e nao compartilham paleta: DIFERE nao e um aviso e
AUSENTE nao e um erro. Cada marcador leva glifo alem da cor, para que o estado
nao dependa de o leitor distinguir tons.

Fechado de proposito, no mesmo espirito de `dialog.py`: quem precisa de um
estado que nao esta aqui precisa de uma variante nova neste modulo, nunca de
markup montado a mao em outro arquivo — por isso `marcar_veredito` e
`marcar_operacao` rejeitam qualquer entrada fora do seu proprio vocabulario.
O eixo inteiro (`$veredito-*`/`$op-falha` fora daqui) e vigiado por
`tests/ui/test_widgets.py::test_veredito_sem_markup_montado_a_mao_fora_do_componente`.
"""
from __future__ import annotations

from dbqm.ui.utils import escape_markup

VEREDITOS: dict[str, tuple[str, str]] = {
    # status -> (glifo, token)
    "igual": ("=", "$veredito-igual"),
    "igual-normalizado": ("~", "$veredito-igual"),
    "difere": ("!", "$veredito-difere"),
    "ausente": ("-", "$veredito-ausente"),
}

OPERACOES: dict[str, tuple[str, str]] = {
    # estado -> (glifo, token); token vazio ("") significa "sem cor, so peso"
    "ok": ("", ""),
    "falha": ("x", "$op-falha"),
    "executando": ("*", "$identidade"),
}


def marcar_veredito(status: str, *, texto: str | None = None) -> str:
    """Markup do veredito de comparacao, com glifo e cor.

    `igual` (OK) usa o mesmo token de `texto-apoio` de proposito: um
    resultado igual nao carrega alarme nenhum, so o glifo confirma o estado.

    `texto`, se passado, troca so o ROTULO — glifo e token continuam vindo
    de `VEREDITOS`, fechados. Existe para o chamador que ja tem sua propria
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
    if status not in VEREDITOS:
        raise ValueError(f"status desconhecido: {status!r}; use {sorted(VEREDITOS)}")
    glifo, token = VEREDITOS[status]
    rotulo = escape_markup(texto) if texto is not None else {
        "igual": "OK",
        "igual-normalizado": "OK*",
        "difere": "DIFERE",
        "ausente": "AUSENTE",
    }[status]
    return f"[{token}]{glifo} {rotulo}[/]"


def marcar_operacao(estado: str, *, texto: str | None = None) -> str:
    """Markup do status de uma operacao (execucao de consulta/grupo).

    `ok` sai sem tinta de alarme — sucesso e a ausencia de alarme, so
    `falha` recebe cor de erro — mas mantem o PESO (`[bold]`): sem cor nao
    e sem legibilidade. A mesma regra que os call sites manuais de
    `adhoc.py`, `exec_routine.py` e `package_editor.py` ja aplicam com
    `[bold]` cravado ao lado do texto de sucesso. `executando` recebe a cor
    de identidade, para diferenciar "em andamento" de "resultado".

    `texto`, se passado, troca so o ROTULO (mesma razao e mesmo escape de
    `marcar_veredito`).
    """
    if estado not in OPERACOES:
        raise ValueError(f"estado desconhecido: {estado!r}; use {sorted(OPERACOES)}")
    glifo, token = OPERACOES[estado]
    rotulo = escape_markup(texto) if texto is not None else {
        "ok": "OK", "falha": "FALHA", "executando": "executando",
    }[estado]
    corpo = f"{(glifo + ' ') if glifo else ''}{rotulo}"
    if not token:
        return f"[bold]{corpo}[/]"
    return f"[{token}]{corpo}[/]"
