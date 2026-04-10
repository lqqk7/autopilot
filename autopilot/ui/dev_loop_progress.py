"""DevLoopProgress: live terminal display for parallel feature development."""
from __future__ import annotations

import threading
import time
from typing import Callable

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Each entry: (feature_id, current_phase, backend_name, feature_title)
WorkerStatus = tuple[str, str, str, str]

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_PHASE_COLOR: dict[str, str] = {
    "CODE":   "bold green",
    "TEST":   "bold yellow",
    "REVIEW": "bold magenta",
    "FIX":    "bold red",
}

_BACKEND_COLOR: dict[str, str] = {
    "claudecode": "blue",
    "codex":      "bright_cyan",
    "opencode":   "cyan",
}


def _spinner_frame() -> str:
    return _SPINNER_FRAMES[int(time.monotonic() * 8) % len(_SPINNER_FRAMES)]


class DevLoopProgress:
    """Renders a live panel showing all active FeatureWorkers and their current phase."""

    def __init__(
        self,
        total: int,
        get_worker_status: Callable[[], list[WorkerStatus]],
    ) -> None:
        self._total = total
        self._done = 0
        self._get_status = get_worker_status
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._console = Console(stderr=False)

    def update_done(self, done: int) -> None:
        with self._lock:
            self._done = done

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    # ── rendering ────────────────────────────────────────────────────────────

    def _build_panel(self) -> Panel:
        with self._lock:
            done = self._done
        workers = self._get_status()
        frame = _spinner_frame()

        table = Table(show_header=True, box=None, padding=(0, 1), expand=False)
        table.add_column("Feature", style="dim", min_width=10)
        table.add_column("Phase", min_width=10)
        table.add_column("Tool", min_width=12)
        table.add_column("Task", min_width=20, no_wrap=True)

        if workers:
            for fid, phase, backend, title in workers:
                phase_style = _PHASE_COLOR.get(phase, "bold cyan")
                backend_style = _BACKEND_COLOR.get(backend, "cyan")
                short = title[:42] + "…" if len(title) > 42 else title
                table.add_row(
                    fid,
                    Text(f"{frame} {phase}", style=phase_style),
                    Text(f"● {backend}", style=backend_style),
                    short,
                )
        else:
            table.add_row("[dim]–[/dim]", "[dim]–[/dim]", "[dim]–[/dim]", "[dim]等待任务分配…[/dim]")

        pct = int(done / self._total * 100) if self._total else 0
        title_str = (
            f"[bold cyan]DEV_LOOP[/bold cyan]"
            f"  [white]{done}[/white][dim]/{self._total}[/dim] 完成"
            f"  [dim]{pct}%[/dim]"
        )
        return Panel(table, title=title_str, border_style="cyan", expand=False)

    def _run(self) -> None:
        with Live(console=self._console, refresh_per_second=8) as live:
            while not self._stop.is_set():
                live.update(self._build_panel())
                time.sleep(0.125)
            live.update(self._build_panel())
