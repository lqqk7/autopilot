"""StatusBar: top header showing phase, elapsed time, backend, and worker info."""
from __future__ import annotations

import time

from textual.widget import Widget
from textual.widgets import Static


class StatusBar(Widget):
    """One-line header: Phase | Elapsed | Backend | Workers active | Features done/total."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $accent-darken-2;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._start_time: float = time.monotonic()
        self._phase: str = "INIT"
        self._backend: str = "claude"
        self._workers_active: int = 0
        self._workers_total: int = 0
        self._features_done: int = 0
        self._features_total: int = 0
        self._static: Static | None = None

    def compose(self):  # type: ignore[override]
        self._static = Static(self._render_line())
        yield self._static

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self._static:
            self._static.update(self._render_line())

    def _elapsed(self) -> str:
        secs = int(time.monotonic() - self._start_time)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _render_line(self) -> str:
        progress = (
            f"  [dim]features[/] [white]{self._features_done}[/][dim]/{self._features_total}[/]"
            if self._features_total
            else ""
        )
        workers = (
            f"  [dim]workers[/] [white]{self._workers_active}[/][dim]/{self._workers_total}[/]"
            if self._workers_total
            else ""
        )
        return (
            f"[bold cyan]{self._phase}[/]"
            f"  [dim]⏱[/] [white]{self._elapsed()}[/]"
            f"  [dim]via[/] [green]{self._backend}[/]"
            f"{progress}{workers}"
        )

    # ── public update API (call from app after draining EventBus) ────────────

    def update_phase(self, phase: str) -> None:
        self._phase = phase
        self._tick()

    def update_backend(self, backend: str) -> None:
        self._backend = backend
        self._tick()

    def update_progress(self, done: int, total: int) -> None:
        self._features_done = done
        self._features_total = total
        self._tick()

    def update_workers(self, active: int, total: int = 0) -> None:
        self._workers_active = active
        if total:
            self._workers_total = total
        self._tick()
