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

    # No command: the help, on stdout, exit 0. Until 3.0.0 this opened the
    # interactive interface; `dbqm tui` does that now, and the help says so
    # in its first lines.
    from dbqm.cli import print_the_help

    print_the_help()


if __name__ == "__main__":
    main()
