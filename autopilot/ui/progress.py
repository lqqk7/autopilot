from __future__ import annotations

import threading
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from autopilot.pipeline.phases import DELIVERY_DOCS, MIN_DOC_CHARS, REQUIRED_DOCS

_DOC_PHASE_LISTS: dict[str, list[str]] = {
    "DOC_GEN": REQUIRED_DOCS,
    "DELIVERY": DELIVERY_DOCS,
}


class PhaseProgress:
    """Renders live terminal progress while a pipeline phase runs in a subprocess.

    DOC_GEN/DELIVERY: shows a progress bar tracking how many docs have been written.
    Other phases: shows a spinner with phase name, feature progress, and elapsed time.
    """

    def __init__(
        self,
        phase_name: str,
        docs_path: Path | None = None,
        feature_progress: tuple[int, int] | None = None,
        feature_title: str | None = None,
    ) -> None:
        self.phase_name = phase_name
        self.docs_path = docs_path
        self.feature_progress = feature_progress  # (done, total)
        self.feature_title = feature_title
        self._doc_list = _DOC_PHASE_LISTS.get(phase_name) if docs_path else None
        self._is_doc_gen = self._doc_list is not None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._console = Console(stderr=False)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    # ── rendering ────────────────────────────────────────────────────────────

    def _run(self) -> None:
        if self._is_doc_gen:
            self._render_doc_gen()
        else:
            self._render_spinner()

    def _render_doc_gen(self) -> None:
        total = len(self._doc_list or [])
        progress = Progress(
            SpinnerColumn(),
            TextColumn(f"[bold cyan]{self.phase_name}"),
            BarColumn(bar_width=28),
            TextColumn("[bold white]{task.completed}[/]/[dim]{task.total}[/] 文档"),
            TextColumn("[dim]{task.fields[current_file]}"),
            TimeElapsedColumn(),
            console=self._console,
        )
        task = progress.add_task("doc_gen", total=total, current_file="")

        with Live(progress, console=self._console, refresh_per_second=2):
            while not self._stop.is_set():
                done, latest = self._scan_docs()
                progress.update(task, completed=done, current_file=latest)
                time.sleep(0.5)
            # Final update before exiting Live context
            done, latest = self._scan_docs()
            progress.update(task, completed=done, current_file=latest)

    def _render_spinner(self) -> None:
        # Build description: "CODE [36/49] 数据库Schema..." (truncated)
        desc = self._build_description()
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            TimeElapsedColumn(),
            console=self._console,
        )
        task = progress.add_task(desc, total=None)

        with Live(progress, console=self._console, refresh_per_second=4):
            while not self._stop.is_set():
                time.sleep(0.25)

    def _build_description(self) -> str:
        parts = [self.phase_name]
        if self.feature_progress:
            done, total = self.feature_progress
            parts.append(f"[{done}/{total}]")
        if self.feature_title:
            title = self.feature_title[:40] + "…" if len(self.feature_title) > 40 else self.feature_title
            parts.append(title)
        return " ".join(parts)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _scan_docs(self) -> tuple[int, str]:
        """Return (completed_count, latest_written_filename)."""
        if not self.docs_path or not self._doc_list:
            return 0, ""
        done = 0
        latest_file = ""
        latest_mtime = 0.0
        for rel in self._doc_list:
            f = self.docs_path / rel
            if not f.exists():
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                mtime = f.stat().st_mtime
            except OSError:
                continue
            if len(content) >= MIN_DOC_CHARS:
                done += 1
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_file = rel
        return done, latest_file
