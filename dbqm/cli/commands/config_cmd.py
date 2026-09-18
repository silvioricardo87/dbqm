"""Commands for reading and writing what dbqm stores in `settings.json`.

Mirrors `dbqm.cli.commands.connection`: the subparser-with-subcommands shape
and `_fail_or_print` are the same idiom, copied on purpose rather than
inventing a second one. Unlike `connection`, nothing here opens a database --
there is no `connection_failed` and no `sql_error`, only `not_found` for an
unknown key and `validation` for a value that fails a check.

A bad value is refused, not coerced: `set audit_log_enabled talvez` must exit
with `validation` and leave the stored value exactly as it was, never quietly
become `False`.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, NoReturn

from rich.markup import escape
from rich.table import Table

from dbqm.cli import deps
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.render import console
from dbqm.i18n import t
from dbqm.design.tokens import THEMES
from dbqm.models.settings import Settings

# Set by `build_parser` (in `dbqm.cli`) so `cmd_config` can print the group's
# own help (get/set/list) on a bare `dbqm config`, the same trick
# `connection.py`/`saved.py` use to reach a subparser created deep inside
# that function.
_config_parser: argparse.ArgumentParser | None = None

# Read from the dataclass itself, never hand-typed: a hand-typed copy drifts
# silently the day a field is added to `Settings`.
_KEYS: tuple[str, ...] = tuple(field.name for field in fields(Settings))

_BOOL_KEYS = ("audit_log_enabled", "export_dir_prompted", "create_export_subdirs")
_DIR_KEYS = ("default_export_dir", "oracle_client_dir")

_TRUE_WORDS = {"true", "1", "sim"}
_FALSE_WORDS = {"false", "0", "nao"}


def _fail_or_print(
    args: argparse.Namespace, command: str, code: str, message: str,
) -> NoReturn:
    """Mirrors `connection._fail_or_print`: one branch point for `-f json`."""
    if args.format == "json":
        fail(command, code, message)
    console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
    sys.exit(int(exit_for(code)))


def _require_known_key(args: argparse.Namespace, command: str, key: str) -> None:
    if key not in _KEYS:
        _fail_or_print(
            args, command, "not_found",
            t("config.key_unknown", key=key, valid=", ".join(_KEYS)),
        )


def _parse_bool(args: argparse.Namespace, command: str, key: str, raw: str) -> bool:
    lowered = raw.strip().lower()
    if lowered in _TRUE_WORDS:
        return True
    if lowered in _FALSE_WORDS:
        return False
    _fail_or_print(
        args, command, "validation",
        t("config.bool_invalid", key=key, value=raw),
    )


def _parse_theme(args: argparse.Namespace, command: str, raw: str) -> str:
    if raw not in THEMES:
        temas = ", ".join(sorted(THEMES.keys()))
        _fail_or_print(
            args, command, "validation",
            t("config.theme_invalid", theme=raw, valid=temas),
        )
    return raw


def _parse_language(args: argparse.Namespace, command: str, raw: str) -> str:
    """Valid languages come from the catalogue at runtime, the same way valid
    themes come from the design tokens: a language added later needs no edit
    here, and one that does not exist cannot be stored."""
    from dbqm.i18n import available_languages

    idiomas = available_languages()
    if raw not in idiomas:
        _fail_or_print(
            args, command, "validation",
            t("config.language_invalid", language=raw, valid=", ".join(idiomas)),
        )
    return raw


def _parse_dir(args: argparse.Namespace, command: str, key: str, raw: str) -> str:
    # Empty means "auto-detect" (oracle_client_dir) / "usar o diretorio atual"
    # (default_export_dir) and must stay settable.
    if raw == "":
        return raw
    if not Path(raw).is_dir():
        _fail_or_print(
            args, command, "validation",
            t("config.dir_not_found", key=key, path=raw),
        )
    return raw


def _convert(args: argparse.Namespace, command: str, key: str, raw: str) -> Any:
    if key in _BOOL_KEYS:
        return _parse_bool(args, command, key, raw)
    if key == "theme":
        return _parse_theme(args, command, raw)
    if key == "language":
        return _parse_language(args, command, raw)
    if key in _DIR_KEYS:
        return _parse_dir(args, command, key, raw)
    # Unreachable for the six known `Settings` fields: `_require_known_key`
    # runs before this and every real key is one of the three groups above.
    return raw


def _cmd_config_list(args: argparse.Namespace) -> None:
    settings = deps.load_settings()
    data = settings.to_dict()
    if args.format == "json":
        ok("config.list", data)
        return
    table = Table(title=t("config.list_title"))
    table.add_column(t("common.key"))
    table.add_column(t("common.value"))
    for key, value in data.items():
        table.add_row(key, escape(str(value)))
    console.print(table)


def _cmd_config_get(args: argparse.Namespace) -> None:
    _require_known_key(args, "config.get", args.key)
    settings = deps.load_settings()
    value = getattr(settings, args.key)
    if args.format == "json":
        ok("config.get", {"key": args.key, "value": value})
        return
    console.print(f"{escape(args.key)}: {escape(str(value))}")


def _cmd_config_set(args: argparse.Namespace) -> None:
    _require_known_key(args, "config.set", args.key)
    value = _convert(args, "config.set", args.key, args.value)

    settings = deps.load_settings()
    setattr(settings, args.key, value)
    deps.save_settings(settings)

    if args.format == "json":
        ok("config.set", {"key": args.key, "value": value})
        return
    console.print(f'Configuracao "{escape(args.key)}" definida como {escape(str(value))}.')


_CONFIG_SUBCOMMANDS = {
    "list": _cmd_config_list,
    "get": _cmd_config_get,
    "set": _cmd_config_set,
}


def cmd_config(args: argparse.Namespace) -> None:
    """Read and write dbqm's stored settings (audit_log_enabled, theme, ...)."""
    subcommand = getattr(args, "subcommand", None)
    handler = _CONFIG_SUBCOMMANDS.get(subcommand) if isinstance(subcommand, str) else None
    if handler is None:
        # A bare `dbqm config` prints the group's own help (get/set/list,
        # with their flags) rather than a one-line reminder.
        if _config_parser is not None:
            _config_parser.print_help()
        else:
            console.print(
                f"[ds.op.failure]{t('config.usage')}[/ds.op.failure]"
            )
        sys.exit(int(exit_for("validation")))
    handler(args)
