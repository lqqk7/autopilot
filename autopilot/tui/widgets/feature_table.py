"""FeatureTable: live DataTable showing all features and their pipeline status."""
from __future__ import annotations

from dataclasses import dataclass, field

from rich.text import Text
from textual.widgets import DataTable

from autopilot.tui.i18n import t

_STATUS_ICON: dict[str, str] = {
    "pending":   "⏳",
    "active":    "🔄",
    "completed": "✅",
    "failed":    "✗ ",
    "waiting":   "⏸ ",
}

_PHASE_STYLE: dict[str, str] = {
    "CODE":   "bold green",
    "TEST":   "bold yellow",
    "REVIEW": "bold magenta",
    "FIX":    "bold red",
}


@dataclass
class FeatureRow:
    feature_id: str
    title: str
    status: str = "pending"
    current_phase: str = ""
    backend: str = ""
    fix_retries: int = 0
    max_retries: int = 5
    elapsed: str = ""
    note: str = ""
    depends_on: list[str] = field(default_factory=list)


class FeatureTable(DataTable):
    """Reactive DataTable for pipeline feature tracking."""

    DEFAULT_CSS = """
    FeatureTable {
        height: 1fr;
        border: tall $accent-darken-2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._rows: dict[str, FeatureRow] = {}

    def on_mount(self) -> None:
        self._add_columns()
        self.cursor_type = "row"
        self.zebra_stripes = True

    def _add_columns(self) -> None:
        self.add_columns(
            "",
            t("col_id"),
            t("col_title"),
            t("col_phase"),
            t("col_backend"),
            t("col_retries"),
            t("col_note"),
        )

    def rebuild_columns(self) -> None:
        """Re-add column headers in the current i18n language. Preserves rows."""
        self.clear(columns=True)
        self._add_columns()
        self._rebuild()

    def upsert(self, row: FeatureRow) -> None:
        """Add or update a feature row."""
        self._rows[row.feature_id] = row
        self._rebuild()

    def upsert_many(self, rows: list[FeatureRow]) -> None:
        for r in rows:
            self._rows[r.feature_id] = r
        self._rebuild()

    def count_done(self) -> int:
        """Return number of features with status 'completed'."""
        return sum(1 for r in self._rows.values() if r.status == "completed")

    def count_total(self) -> int:
        """Return total number of tracked features."""
        return len(self._rows)

    def _rebuild(self) -> None:
        self.clear()
        for row in self._rows.values():
            icon = _STATUS_ICON.get(row.status, "?")
            title_short = row.title[:38] + "…" if len(row.title) > 38 else row.title

            if row.status == "active" and row.current_phase:
                style = _PHASE_STYLE.get(row.current_phase, "bold cyan")
                phase_cell = Text(f"{row.current_phase}", style=style)
            elif row.status == "completed":
                phase_cell = Text("done", style="dim green")
            elif row.status == "failed":
                phase_cell = Text("failed", style="bold red")
            elif row.status == "waiting":
                deps = ", ".join(row.depends_on[:2])
                phase_cell = Text(f"waits: {deps}", style="dim")
            else:
                phase_cell = Text("pending", style="dim")

            retries_cell = (
                Text(f"{row.fix_retries}/{row.max_retries}", style="bold red")
                if row.fix_retries > 0
                else Text("–", style="dim")
            )

            self.add_row(
                icon,
                row.feature_id,
                title_short,
                phase_cell,
                Text(row.backend, style="dim cyan") if row.backend else Text("–", style="dim"),
                retries_cell,
                Text(row.note, style="dim") if row.note else Text("", style="dim"),
            )
