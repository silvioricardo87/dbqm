"""Whether there is a real console to draw a fullscreen app on."""
from __future__ import annotations

import sys


def has_a_console() -> bool:
    """True only when both standard streams are a real terminal.

    `isatty()` alone is not enough on Windows, which is this project's
    primary platform: `NUL` is a character device, so `dbqm < NUL` -- or
    `< /dev/null` under Git Bash -- answers True, and the TUI opened onto
    nothing and hung. Measured before this check existed: exit 124, eighty
    bytes of alt-screen escapes on stdout and nothing on stderr. A real
    console also answers `GetConsoleMode`; `NUL` does not.
    """
    try:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return False
    except (AttributeError, ValueError):
        # A replaced or closed stream is not a console either.
        return False
    if sys.platform != "win32":
        return True

    import ctypes
    import msvcrt

    try:
        handle = msvcrt.get_osfhandle(sys.stdin.fileno())
    except (OSError, ValueError):
        return False
    mode = ctypes.c_ulong()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return bool(kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
