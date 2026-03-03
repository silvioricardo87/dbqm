"""Shared UI helpers extracted from menu.py to eliminate duplication."""
from __future__ import annotations

import os
import platform
import subprocess
from typing import Any, Callable

from rich.console import Console

from dbqm.ui.prompts import select, text, is_esc

console = Console()


def prompt_open_file(path: str):
    """Ask user if they want to open the exported file."""
    from dbqm.ui.prompts import confirm

    should_open = confirm(message="Abrir arquivo exportado?", default=False)
    if is_esc(should_open) or not should_open:
        return

    path = os.path.abspath(path)
    system = platform.system()
    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def pick_format() -> str | None:
    """Let user pick an export format. Returns 'csv'/'json'/'txt' or None on ESC."""
    fmt = select(
        message="Formato:",
        choices=[
            {"name": "📄  CSV", "value": "csv"},
            {"name": "📋  JSON", "value": "json"},
            {"name": "📃  TXT (tabela formatada)", "value": "txt"},
        ],
    )
    if is_esc(fmt):
        return None
    return fmt


def pick_entity(
    items: list,
    formatter: Callable[[Any], str],
    message: str = "Selecione:",
    value_attr: str = "name",
    empty_msg: str = "Nenhum item disponivel.",
) -> Any | None:
    """Generic guard + select + find pattern.

    - items: list of objects
    - formatter: function that returns display string for each item
    - value_attr: attribute name to use as selection value
    - Returns the selected item or None on ESC/empty.
    """
    if not items:
        from dbqm.ui.display import show_warning
        show_warning(empty_msg)
        return None

    choices = [
        {"name": formatter(item), "value": getattr(item, value_attr)}
        for item in items
    ]

    selected = select(message=message, choices=choices)
    if is_esc(selected):
        return None

    return next((item for item in items if getattr(item, value_attr) == selected), None)


def gather_params(specs: list, last: dict) -> dict | None:
    """Gather parameter values from user input.

    specs: list of QueryParam objects (with .name, .description, .default)
    last: dict of last-used values
    Returns param_values dict or None if cancelled.
    """
    param_values = {}
    for p in specs:
        prompt = f"{p.name}"
        if p.description:
            prompt += f" ({p.description})"
        val = text(message=f"  {prompt}:", default=last.get(p.name, p.default))
        if is_esc(val):
            return None
        param_values[p.name] = val
    return param_values


def gather_shared_params(shared: dict, last: dict) -> dict | None:
    """Gather shared parameter values for group execution.

    shared: dict of {param_name: {description, default}}
    last: dict of last-used values
    Returns param_values dict or None if cancelled.
    """
    param_values = {}
    for param_name, param_info in shared.items():
        desc = param_info.get("description", "")
        prompt = f"{param_name}"
        if desc:
            prompt += f" ({desc})"
        val = text(message=f"  {prompt}:", default=last.get(param_name, ""))
        if is_esc(val):
            return None
        param_values[param_name] = val
    return param_values


def read_multiline_sql() -> str | None:
    """Read multi-line SQL input. Returns stripped SQL or None if empty."""
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "" and lines and lines[-1].strip() == "":
            break
        lines.append(line)

    raw_sql = "\n".join(lines).strip()
    if not raw_sql:
        return None
    return raw_sql
