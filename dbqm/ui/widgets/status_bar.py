"""Status bar widget docked at the bottom of the application."""

from __future__ import annotations

from textual.widgets import Static


class StatusBar(Static):
    """A single-line status bar showing connection state and counters."""

    can_focus = False

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $background;
        text-style: bold;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self._connection: str | None = None
        self._queries: int = 0
        self._connections: int = 0
        self._groups: int = 0

    def set_connection(self, name: str | None) -> None:
        """Set the active connection name (None for disconnected)."""
        self._connection = name
        self._rebuild()

    def update_counts(
        self, queries: int = 0, connections: int = 0, groups: int = 0
    ) -> None:
        """Update the resource counters."""
        self._queries = queries
        self._connections = connections
        self._groups = groups
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild the status bar content."""
        if self._connection:
            left = f"[$identidade]●[/] {self._connection}"
        else:
            left = "[dim]●[/dim] sem conexão"

        right_parts: list[str] = []
        if self._queries:
            right_parts.append(f"{self._queries} queries")
        if self._connections:
            right_parts.append(f"{self._connections} conexões")
        if self._groups:
            right_parts.append(f"{self._groups} grupos")

        right = "  ".join(right_parts)
        if right:
            self.update(f"{left}  │  {right}")
        else:
            self.update(left)

    def render_text(self) -> str:
        """Return plain text representation for testing."""
        parts: list[str] = []
        if self._connection:
            parts.append(f"● {self._connection}")
        else:
            parts.append("● sem conexão")
        counts: list[str] = []
        if self._queries:
            counts.append(f"{self._queries} queries")
        if self._connections:
            counts.append(f"{self._connections} conexões")
        if self._groups:
            counts.append(f"{self._groups} grupos")
        if counts:
            parts.append("  ".join(counts))
        return "  │  ".join(parts) if len(parts) > 1 else parts[0]
