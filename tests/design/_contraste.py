"""Matematica de contraste WCAG. Utilitario de teste, fora do produto."""
from __future__ import annotations


def luminancia(hex_cor: str) -> float:
    h = hex_cor.lstrip("#")
    canais = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    canais = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]


def razao(a: str, b: str) -> float:
    la, lb = luminancia(a), luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
