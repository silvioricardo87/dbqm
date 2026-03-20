#!/usr/bin/env python3
"""DB Query Manager (dbqm) — Multi-database interactive query tool."""
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    # If CLI arguments provided, run in non-interactive mode
    if len(sys.argv) > 1:
        from dbqm.cli import run_cli
        try:
            handled = run_cli()
            if handled:
                return
        except KeyboardInterrupt:
            print("\nInterrompido.")
            sys.exit(130)
        except SystemExit:
            raise
        except Exception as e:
            print(f"Erro inesperado: {e}", file=sys.stderr)
            sys.exit(1)

    # No arguments — launch interactive TUI
    from dbqm.ui.app import DBQMApp
    DBQMApp().run()


if __name__ == "__main__":
    main()
