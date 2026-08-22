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

VEREDITOS: dict[str, tuple[str, str]] = {
    # status -> (glifo, token)
    "igual": ("=", "$veredito-igual"),
    "igual-normalizado": ("~", "$veredito-igual"),
    "difere": ("!", "$veredito-difere"),
    "ausente": ("-", "$veredito-ausente"),
}

OPERACOES: dict[str, tuple[str, str]] = {
    # estado -> (glifo, token)
    "ok": ("", "$texto-apoio"),
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
    """
    if status not in VEREDITOS:
        raise ValueError(f"status desconhecido: {status!r}; use {sorted(VEREDITOS)}")
    glifo, token = VEREDITOS[status]
    rotulo = texto if texto is not None else {
        "igual": "OK",
        "igual-normalizado": "OK*",
        "difere": "DIFERE",
        "ausente": "AUSENTE",
    }[status]
    return f"[{token}]{glifo} {rotulo}[/]"


def marcar_operacao(estado: str, *, texto: str | None = None) -> str:
    """Markup do status de uma operacao (execucao de consulta/grupo).

    `ok` sai sem tinta de alarme — sucesso e a ausencia de alarme, so
    `falha` recebe cor de erro. `executando` recebe a cor de identidade,
    para diferenciar "em andamento" de "resultado".

    `texto`, se passado, troca so o ROTULO (mesma razao de `marcar_veredito`).
    """
    if estado not in OPERACOES:
        raise ValueError(f"estado desconhecido: {estado!r}; use {sorted(OPERACOES)}")
    glifo, token = OPERACOES[estado]
    rotulo = texto if texto is not None else {
        "ok": "OK", "falha": "FALHA", "executando": "executando",
    }[estado]
    return f"[{token}]{(glifo + ' ') if glifo else ''}{rotulo}[/]"
