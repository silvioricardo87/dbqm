"""Centralized prompt helpers with ESC-to-back and custom icons."""
from __future__ import annotations

from typing import Any

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from prompt_toolkit.keys import Keys

# Sentinel value to indicate ESC was pressed (go back)
ESC_BACK = "__ESC_BACK__"

# Custom icons/markers
ICON_POINTER = "❯"
ICON_SELECTOR = "❯"
ICON_SELECTED = "◉"
ICON_UNSELECTED = "○"


def _apply_keybindings(prompt):
    """Add ESC keybinding that sets result to ESC_BACK and exits."""
    @prompt.register_kb(Keys.Escape)
    def _escape(event):
        prompt.status["result"] = ESC_BACK
        prompt.status["answered"] = True
        prompt.status["skipped"] = True
        event.app.exit(result=ESC_BACK)


def select(message: str, choices: list, **kwargs) -> Any:
    """inquirer.select wrapper with ESC support and custom icons."""
    prompt = inquirer.select(
        message=message,
        choices=choices,
        pointer=ICON_POINTER,
        show_cursor=False,
        **kwargs,
    )
    _apply_keybindings(prompt)
    result = prompt.execute()
    return result


def checkbox(message: str, choices: list, **kwargs) -> Any:
    """inquirer.checkbox wrapper with ESC support and custom icons."""
    prompt = inquirer.checkbox(
        message=message,
        choices=choices,
        pointer=ICON_POINTER,
        enabled_symbol=ICON_SELECTED,
        disabled_symbol=ICON_UNSELECTED,
        **kwargs,
    )
    _apply_keybindings(prompt)
    result = prompt.execute()
    return result


def text(message: str, **kwargs) -> Any:
    """inquirer.text wrapper with ESC support."""
    prompt = inquirer.text(
        message=message,
        amark="❯",
        qmark="❯",
        **kwargs,
    )
    _apply_keybindings(prompt)
    result = prompt.execute()
    return result


def secret(message: str, **kwargs) -> Any:
    """inquirer.secret wrapper with ESC support."""
    prompt = inquirer.secret(
        message=message,
        amark="❯",
        qmark="❯",
        **kwargs,
    )
    _apply_keybindings(prompt)
    result = prompt.execute()
    return result


def confirm(message: str, **kwargs) -> Any:
    """inquirer.confirm wrapper with ESC support."""
    prompt = inquirer.confirm(
        message=message,
        amark="❯",
        qmark="❯",
        **kwargs,
    )
    _apply_keybindings(prompt)
    result = prompt.execute()
    return result


def is_esc(value: Any) -> bool:
    """Check if user pressed ESC."""
    return value == ESC_BACK
