"""DB Query Manager (dbqm) — entry point."""
import sys


def main():
    # Version flag
    if len(sys.argv) == 2 and sys.argv[1] in ("--version", "-V"):
        from dbqm._version import __version__
        print(f"dbqm {__version__}")
        return

    # CLI mode
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

    # Ensure data directories exist before launching TUI
    from dbqm.core.paths import ensure_dirs
    ensure_dirs()

    # Interactive TUI
    from dbqm.ui.app import DBQMApp
    DBQMApp().run()


if __name__ == "__main__":
    main()
