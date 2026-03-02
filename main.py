#!/usr/bin/env python3
"""DB Query Manager (dbqm) — Multi-database interactive query tool."""
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dbqm.ui.menu import main_menu


def main():
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nSaindo...")
        sys.exit(0)


if __name__ == "__main__":
    main()
