"""LogPanel: scrolling Rich log stream for pipeline events."""
from __future__ import annotations

from datetime import datetime

from rich.markup import escape
from textual.widgets import RichLog

_LEVEL_STYLE: dict[str, str] = {
    "info":    "dim white",
    "success": "bold green",
    "warning": "bold yellow",
    "error":   "bold red",
    "debug":   "dim",
    "phase":   "bold cyan",
    "commit":  "bold blue",
}

_MAX_LINES = 500


class LogPanel(RichLog):
    """Scrolling log panel with timestamp and colour-coded levels."""

    DEFAULT_CSS = """
    LogPanel {
        height: 1fr;
        border: tall $accent-darken-3;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__(highlight=True, markup=True, max_lines=_MAX_LINES)

    def log_event(
        self,
        message: str,
        level: str = "info",
        feature_id: str | None = None,
    ) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        style = _LEVEL_STYLE.get(level, "white")
        prefix = f"[dim]{ts}[/dim]"
        tag = f"  [dim cyan][{escape(feature_id)}][/dim cyan]" if feature_id else ""
        self.write(f"{prefix}{tag}  [{style}]{escape(message)}[/{style}]")

    def log_phase(self, phase: str, note: str = "") -> None:
        self.log_event(
            f"━━ {phase}{(' — ' + note) if note else ''} ━━",
            level="phase",
        )

    def log_commit(self, feature_id: str, message: str) -> None:
        self.log_event(f"🔖 {message}", level="commit", feature_id=feature_id)

    def log_error(self, message: str, feature_id: str | None = None) -> None:
        self.log_event(message, level="error", feature_id=feature_id)
