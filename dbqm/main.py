"""DB Query Manager (dbqm) — entry point."""
import sys


def main() -> None:
    # Version flag
    if len(sys.argv) == 2 and sys.argv[1] in ("--version", "-V"):
        from dbqm._version import __version__
        print(f"dbqm {__version__}")
        return

    # CLI mode
    if len(sys.argv) > 1:
        from dbqm.cli import run_cli
        from dbqm.i18n import t
        try:
            handled = run_cli()
            if handled:
                return
        except KeyboardInterrupt:
            print("\n" + t("common.interrupted"), file=sys.stderr)
            sys.exit(130)
        except SystemExit:
            raise
        except Exception as e:
            print(t("common.unexpected_error", error=e), file=sys.stderr)
            sys.exit(1)

    # Interactive TUI. A terminal is required: see
    # `dbqm.cli.refuse_without_a_terminal` for what used to happen without one.
    if not sys.stdin.isatty():
        from dbqm.cli import refuse_without_a_terminal

        refuse_without_a_terminal()

    from dbqm.core.paths import ensure_dirs

    ensure_dirs()

    from dbqm.ui.app import DBQMApp

    DBQMApp().run()


if __name__ == "__main__":
    main()
