"""AppHeader: persistent 3-row header for the Autopilot TUI.

Row 1 — identity:  autopilot vX.Y.Z  ──  ~/project-path  ──  date  HH:MM:SS
Row 2 — runtime:   [PHASE]  via backend  │  features N/N  │  workers A/max  │  elapsed
Row 3 — config:    model: X  │  review: X  │  log: X  │  max-workers: N  [│  parallel: …]  [│  fallback: …]
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from autopilot import __version__
from autopilot.tui.i18n import t


def _shorten_path(path: Path) -> str:
    home = Path.home()
    try:
        rel = path.relative_to(home)
        return "~/" + str(rel)
    except ValueError:
        return str(path)


class AppHeader(Widget):
    """Persistent 3-row header (identity + runtime + config). Always visible."""

    DEFAULT_CSS = """
    AppHeader {
        height: 5;
        background: $surface;
        border: tall $accent;
        padding: 0 1;
    }
    AppHeader Static {
        height: 1;
    }
    """

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self._project_path = project_path
        self._start_time = time.monotonic()

        # runtime state (updated by event bus)
        self._phase = "INIT"
        self._backend = "claude"
        self._features_done = 0
        self._features_total = 0
        self._workers_active = 0
        self._workers_total = 0

        # config state (updated by _load_config / /set / /reload)
        self._max_parallel = 2
        self._parallel_backends: list[str] = []
        self._fallback_backends: list[str] = []
        self._log_level = "INFO"
        self._model = ""
        self._review_mode = "self"
        self._review_backend = ""

        self._row1: Static | None = None
        self._row2: Static | None = None
        self._row3: Static | None = None

    def compose(self) -> ComposeResult:
        self._row1 = Static(self._render_row1())
        self._row2 = Static(self._render_row2())
        self._row3 = Static(self._render_row3())
        yield self._row1
        yield self._row2
        yield self._row3

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self._row1:
            self._row1.update(self._render_row1())
        if self._row2:
            self._row2.update(self._render_row2())
        if self._row3:
            self._row3.update(self._render_row3())

    # ── renderers ─────────────────────────────────────────────────────────────

    def _render_row1(self) -> str:
        path_str = _shorten_path(self._project_path)
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        return (
            f"[bold cyan]autopilot[/bold cyan] [dim]v{__version__}[/dim]"
            f"  [dim]│[/dim]  [white]{path_str}[/white]"
            f"  [dim]│[/dim]  [dim]{date_str}[/dim]  [bold white]{time_str}[/bold white]"
        )

    def _render_row2(self) -> str:
        elapsed = self._elapsed()
        phase_style = _PHASE_STYLE.get(self._phase, "bold cyan")

        features = (
            f"[dim]{t('lbl_features')}[/dim] "
            f"[white]{self._features_done}[/white][dim]/{self._features_total}[/dim]"
            if self._features_total
            else f"[dim]{t('lbl_features')} –[/dim]"
        )
        workers_label = t("lbl_workers")
        if self._workers_total:
            workers = (
                f"[dim]{workers_label}[/dim] "
                f"[white]{self._workers_active}[/white][dim]/{self._workers_total}[/dim]"
            )
        else:
            workers = f"[dim]{workers_label} –[/dim]"

        return (
            f"[{phase_style}]{self._phase}[/{phase_style}]"
            f"  [dim]{t('lbl_backend')}[/dim] [green]{self._backend}[/green]"
            f"  [dim]│[/dim]  {features}"
            f"  [dim]│[/dim]  {workers}"
            f"  [dim]│[/dim]  [dim]{elapsed}[/dim]"
        )

    def _render_row3(self) -> str:
        model_str = self._model or "default"
        review_str = self._review_mode
        if self._review_mode == "backend" and self._review_backend:
            review_str = f"backend:{self._review_backend}"

        parts = [
            f"[dim]model:[/dim] [white]{model_str}[/white]",
            f"[dim]review:[/dim] [white]{review_str}[/white]",
            f"[dim]log:[/dim] [white]{self._log_level}[/white]",
            f"[dim]max-workers:[/dim] [white]{self._max_parallel}[/white]",
        ]
        if self._parallel_backends:
            parts.append(
                f"[dim]parallel:[/dim] [white]{','.join(self._parallel_backends)}[/white]"
            )
        if self._fallback_backends:
            parts.append(
                f"[dim]fallback:[/dim] [white]{','.join(self._fallback_backends)}[/white]"
            )

        sep = "  [dim]│[/dim]  "
        return sep.join(parts)

    def _elapsed(self) -> str:
        secs = int(time.monotonic() - self._start_time)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    # ── public update API ──────────────────────────────────────────────────────

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

    def update_config(self, ap_cfg: dict) -> None:
        """Sync config-row state from a parsed [autopilot] config dict."""
        self._backend = ap_cfg.get("backend", self._backend)
        self._max_parallel = int(ap_cfg.get("max_parallel", self._max_parallel))
        self._parallel_backends = list(ap_cfg.get("parallel_backends", self._parallel_backends))
        self._fallback_backends = list(ap_cfg.get("fallback_backends", self._fallback_backends))
        self._log_level = ap_cfg.get("log_level", self._log_level)
        self._model = ap_cfg.get("model", self._model)
        review_cfg = ap_cfg.get("review", {})
        if isinstance(review_cfg, dict):
            self._review_mode = review_cfg.get("mode", self._review_mode)
            self._review_backend = review_cfg.get("backend", self._review_backend)
        self._tick()

    def refresh_labels(self) -> None:
        """Re-render after a language switch."""
        self._tick()


_PHASE_STYLE: dict[str, str] = {
    "INIT":        "bold cyan",
    "INTERVIEW":   "bold yellow",
    "DOC_GEN":     "bold yellow",
    "DOC_UPDATE":  "bold yellow",
    "PLANNING":    "bold yellow",
    "DEV_LOOP":    "bold green",
    "KNOWLEDGE":   "bold yellow",
    "DELIVERY":    "bold green",
    "DONE":        "bold green",
    "HUMAN_PAUSE": "bold red",
    "CODE":        "bold green",
    "TEST":        "bold yellow",
    "REVIEW":      "bold magenta",
    "FIX":         "bold red",
}
