"""AutopilotApp: the main Textual TUI application.

Entry point: `autopilot` command → launch()
Architecture:
  - EventBus bridges the pipeline engine (background threads) and the UI
  - App polls EventBus every 100ms via set_interval and dispatches to widgets
  - All pipeline operations run in daemon threads; UI stays fully responsive
"""
from __future__ import annotations

import threading
import toml
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from autopilot.tui.commands import COMMANDS, completions_for, lookup, parse
from autopilot.tui.event_bus import EventBus
from autopilot.tui.widgets.feature_table import FeatureRow, FeatureTable
from autopilot.tui.widgets.log_panel import LogPanel
from autopilot.tui.widgets.status_bar import StatusBar

_LOGO = "[bold cyan]autopilot[/bold cyan] [dim]v0.3.0[/dim]"


class AutopilotApp(App):
    """Full-screen TUI for the autopilot pipeline."""

    CSS = """
    Screen {
        background: $background;
    }

    #layout {
        height: 1fr;
    }

    #input-row {
        height: 3;
        background: $surface;
        border: tall $accent-darken-2;
        padding: 0 1;
    }

    #prompt-label {
        width: 2;
        color: $accent;
        content-align: left middle;
        height: 3;
        padding: 1 0 0 0;
    }

    #cmd-input {
        width: 1fr;
        border: none;
        background: $surface;
    }

    #suggestions {
        height: auto;
        max-height: 12;
        background: $surface-darken-1;
        border: tall $accent;
        display: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("escape", "clear_input", "Clear input"),
        Binding("f1", "show_help", "Help"),
    ]

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self.project_path = project_path
        self._event_bus = EventBus()
        self._pipeline_thread: threading.Thread | None = None
        self._pipeline_running = False
        self._quit_confirmed = False

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield StatusBar()
        with Vertical(id="layout"):
            yield FeatureTable()
            yield LogPanel()
        with Vertical(id="input-area"):
            yield OptionList(id="suggestions")
            with Vertical(id="input-row"):
                yield Static("> ", id="prompt-label")
                yield Input(placeholder="type /help for commands…", id="cmd-input")

    def on_mount(self) -> None:
        self.title = "Autopilot"
        self.sub_title = str(self.project_path)
        self.set_interval(0.1, self._poll_events)
        self._log("Autopilot ready. Type [bold]/help[/bold] or [bold]/run[/bold] to start.", level="info")

    # ── event bus polling ────────────────────────────────────────────────────

    def _poll_events(self) -> None:
        table = self.query_one(FeatureTable)
        log = self.query_one(LogPanel)
        status = self.query_one(StatusBar)

        for ev in self._event_bus.drain():
            d = ev.data
            if ev.type == "phase_change":
                phase = d.get("to_phase", "")
                status.update_phase(phase)
                log.log_phase(phase)

            elif ev.type == "feature_update":
                table.upsert(FeatureRow(
                    feature_id=d.get("feature_id", ""),
                    title=d.get("title", ""),
                    status=d.get("status", "pending"),
                    current_phase=d.get("current_phase", ""),
                    backend=d.get("backend", ""),
                    fix_retries=d.get("fix_retries", 0),
                    max_retries=d.get("max_retries", 5),
                    note=d.get("note", ""),
                    depends_on=d.get("depends_on", []),
                ))
                status.update_progress(table.count_done(), table.count_total())

            elif ev.type == "log":
                log.log_event(
                    d.get("message", ""),
                    level=d.get("level", "info"),
                    feature_id=d.get("feature_id"),
                )

            elif ev.type == "auto_commit":
                log.log_commit(d.get("feature_id", ""), d.get("message", ""))

            elif ev.type == "backend_switch":
                status.update_backend(d.get("to_backend", ""))
                log.log_event(
                    f"Backend switch: {d.get('from_backend')} → {d.get('to_backend')}",
                    level="warning",
                )

            elif ev.type == "worker_start":
                status.update_workers(d.get("active", 0), d.get("total", 0))

            elif ev.type == "pipeline_done":
                self._pipeline_running = False
                self._quit_confirmed = False
                phase = d.get("final_phase", "DONE")
                status.update_phase(phase)
                log.log_event(
                    f"Pipeline finished → {phase}  ({d.get('elapsed', '')})",
                    level="success",
                )

            elif ev.type == "pipeline_error":
                self._pipeline_running = False
                self._quit_confirmed = False
                log.log_error(d.get("message", "Pipeline error"))

    # ── slash command input ──────────────────────────────────────────────────

    @on(Input.Changed, "#cmd-input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        text = event.value
        suggestions = self.query_one("#suggestions", OptionList)

        if text.startswith("/"):
            matches = completions_for(text)
            suggestions.clear_options()
            if matches:
                for usage, desc in matches:
                    suggestions.add_option(Option(f"{usage}  [dim]{desc}[/dim]", id=usage.split()[0]))
                suggestions.display = True
            else:
                suggestions.display = False
        else:
            suggestions.display = False

    @on(Input.Submitted, "#cmd-input")
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        self.query_one("#cmd-input", Input).clear()
        self.query_one("#suggestions", OptionList).display = False
        if raw:
            self._execute(raw)

    @on(OptionList.OptionSelected, "#suggestions")
    def _on_suggestion_selected(self, event: OptionList.OptionSelected) -> None:
        cmd_input = self.query_one("#cmd-input", Input)
        cmd_input.value = str(event.option.id)
        cmd_input.focus()
        self.query_one("#suggestions", OptionList).display = False

    # ── command execution ────────────────────────────────────────────────────

    def _execute(self, raw: str) -> None:
        log = self.query_one(LogPanel)

        if not raw.startswith("/"):
            log.log_event(f"Unknown input: {raw!r}  (commands start with /)", level="warning")
            return

        cmd_name, args = parse(raw)
        cmd = lookup(cmd_name)
        if cmd is None:
            log.log_event(f"Unknown command: /{cmd_name}  — type /help", level="warning")
            return

        handler = getattr(self, f"_cmd_{cmd_name}", None)
        if handler:
            handler(args)
        else:
            log.log_event(f"/{cmd_name}: not implemented yet", level="warning")

    # ── command handlers ──────────────────────────────────────────────────────

    def _cmd_help(self, _args: list[str]) -> None:
        log = self.query_one(LogPanel)
        log.log_phase("HELP")
        for cmd in COMMANDS:
            hint = f" {cmd.args_hint}" if cmd.args_hint else ""
            log.log_event(f"[bold]/{cmd.name}{hint}[/bold]  — {cmd.description}", level="info")

    def _cmd_quit(self, _args: list[str]) -> None:
        if self._pipeline_running and not self._quit_confirmed:
            self._quit_confirmed = True
            self._log(
                "Pipeline is running — background threads will be stopped. "
                "Run /quit again to confirm, or wait for pipeline to finish.",
                "warning",
            )
            return
        self.exit()

    # alias
    def _cmd_exit(self, args: list[str]) -> None:
        self._cmd_quit(args)

    def _cmd_check(self, _args: list[str]) -> None:
        log = self.query_one(LogPanel)
        log.log_phase("CHECK")
        # capture widget reference in main thread; pass it to background thread
        threading.Thread(target=self._run_check, args=(log,), daemon=True).start()

    def _run_check(self, log: LogPanel) -> None:
        import shutil, os
        autopilot_dir = self.project_path / ".autopilot"

        def ok(msg: str) -> None:
            self.call_from_thread(log.log_event, f"✓  {msg}", "success")

        def fail(msg: str) -> None:
            self.call_from_thread(log.log_event, f"✗  {msg}", "error")

        def warn(msg: str) -> None:
            self.call_from_thread(log.log_event, f"⚠  {msg}", "warning")

        if not autopilot_dir.exists():
            fail(".autopilot/ not found — run `ap init` first"); return
        ok(".autopilot/ exists")

        config_path = autopilot_dir / "config.toml"
        if not config_path.exists():
            fail("config.toml not found"); return

        try:
            raw = toml.loads(config_path.read_text(encoding="utf-8"))
            ap_cfg = raw.get("autopilot", {})
            from autopilot.pipeline.config import PipelineConfig
            PipelineConfig.from_toml(ap_cfg)
            ok("config.toml valid")
        except Exception as exc:
            fail(f"config.toml invalid: {exc}"); return

        backend_name = ap_cfg.get("backend", "claude")
        cli_map = {"claude": "claude", "codex": "codex", "opencode": "opencode"}
        for bn in [backend_name] + ap_cfg.get("parallel_backends", []):
            cli = cli_map.get(bn, bn)
            if shutil.which(cli):
                ok(f"{bn} CLI found")
            else:
                fail(f"{bn} CLI ({cli}) not in PATH")

        if ap_cfg.get("notifications", {}).get("enabled"):
            for var in ("AUTOPILOT_TELEGRAM_TOKEN", "AUTOPILOT_TELEGRAM_CHAT_ID"):
                ok(var) if os.environ.get(var) else fail(f"{var} not set")
        else:
            ok("Telegram disabled")

        git_dir = self.project_path / ".git"
        if git_dir.exists():
            ok(".git found")
        elif ap_cfg.get("auto_commit", True):
            warn("Not a git repo — auto_commit will be skipped")
        else:
            ok("Not a git repo (auto_commit = false)")

        self.call_from_thread(log.log_event, "Pre-flight done.", "success")

    def _cmd_status(self, _args: list[str]) -> None:
        from autopilot.pipeline.context import PipelineState, FeatureList
        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        state_path = autopilot_dir / "state.json"
        if not state_path.exists():
            log.log_event("No state found — run /run first", "warning"); return
        state = PipelineState.load(state_path)
        log.log_phase("STATUS")
        log.log_event(f"Phase: {state.phase.value}  retries: {state.phase_retries}", "info")
        fl_path = autopilot_dir / "feature_list.json"
        if fl_path.exists():
            fl = FeatureList.load(fl_path)
            done = sum(1 for f in fl.features if f.status == "completed")
            failed = sum(1 for f in fl.features if f.status == "failed")
            log.log_event(
                f"Features: {done}/{len(fl.features)} done, {failed} failed", "info"
            )

    def _cmd_sessions(self, _args: list[str]) -> None:
        from autopilot.sessions.reader import list_sessions, format_list
        log = self.query_one(LogPanel)
        sessions_dir = self.project_path / ".autopilot" / "sessions"
        sessions = list_sessions(sessions_dir)
        if not sessions:
            log.log_event("No sessions recorded yet.", "info"); return
        log.log_phase("SESSIONS")
        for s in sessions[:10]:
            log.log_event(
                f"{s['session_id'][:20]}  {s['status']}  {s['phase']}  "
                f"{s['features_done']}/{s['features_total']} features",
                "info",
            )

    def _cmd_run(self, _args: list[str]) -> None:
        if self._pipeline_running:
            self.query_one(LogPanel).log_event("Pipeline already running.", "warning"); return
        self._start_pipeline(resume=False)

    def _cmd_resume(self, _args: list[str]) -> None:
        if self._pipeline_running:
            self.query_one(LogPanel).log_event("Pipeline already running.", "warning"); return
        self._start_pipeline(resume=True)

    def _cmd_redo(self, args: list[str]) -> None:
        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        fl_path = autopilot_dir / "feature_list.json"
        if not fl_path.exists():
            log.log_event("No feature_list.json — run /run first", "warning"); return
        from autopilot.pipeline.context import FeatureList, PipelineState, Phase
        fl = FeatureList.load(fl_path)
        if "--failed" in args:
            targets = [f for f in fl.features if f.status == "failed"]
        elif args:
            fid = args[0]
            targets = [f for f in fl.features if f.id == fid]
            if not targets:
                log.log_event(f"Feature {fid!r} not found", "error"); return
        else:
            log.log_event("Usage: /redo FEATURE_ID  or  /redo --failed", "warning"); return
        for f in targets:
            f.status = "pending"
            f.fix_retries = 0
            log.log_event(f"↩ reset {f.id}", "info")
        fl.save(fl_path)
        state_path = autopilot_dir / "state.json"
        if not state_path.exists():
            log.log_event("state.json not found — run /run first", "error"); return
        state = PipelineState.load(state_path)
        if state.phase not in (Phase.DEV_LOOP,):
            state.phase = Phase.DEV_LOOP
        state.phase_retries = 0
        state.current_feature_id = None
        state.active_feature_ids = []
        state.save(state_path)
        log.log_event(f"Reset {len(targets)} feature(s). Run /resume to continue.", "success")

    # ── pipeline runner (background thread) ──────────────────────────────────

    def _start_pipeline(self, resume: bool) -> None:
        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        if not autopilot_dir.exists():
            log.log_event(".autopilot/ not found — run /check first", "error"); return
        self._pipeline_running = True
        self._event_bus.clear()
        log.log_event(f"{'Resuming' if resume else 'Starting'} pipeline…", "info")
        thread = threading.Thread(
            target=self._pipeline_worker,
            args=(resume,),
            daemon=True,
        )
        self._pipeline_thread = thread
        thread.start()

    def _pipeline_worker(self, resume: bool) -> None:
        try:
            import toml
            from autopilot.backends import get_backend
            from autopilot.pipeline.engine import PipelineEngine
            from autopilot.pipeline.config import PipelineConfig
            from autopilot.pipeline.context import PipelineState, Phase

            autopilot_dir = self.project_path / ".autopilot"
            config = toml.loads((autopilot_dir / "config.toml").read_text())
            ap_cfg = config.get("autopilot", {})
            pipeline_config = PipelineConfig.from_toml(ap_cfg)
            _dangerous = pipeline_config.allow_dangerous_permissions
            backend = get_backend(
                ap_cfg["backend"],
                model=pipeline_config.model,
                allow_dangerous=_dangerous,
            )
            parallel_backends_names: list[str] = ap_cfg.get("parallel_backends", [])
            parallel_backends = [
                get_backend(n, model=pipeline_config.model, allow_dangerous=_dangerous)
                for n in parallel_backends_names
            ]

            if resume:
                state = PipelineState.load(autopilot_dir / "state.json")
                if state.phase.value == "HUMAN_PAUSE":
                    state.phase = Phase.DOC_GEN
                    state.phase_retries = 0
                    state.pause_reason = None
                    state.save(autopilot_dir / "state.json")

            engine = PipelineEngine(
                project_path=self.project_path,
                backend=backend,
                max_parallel=ap_cfg.get("max_parallel", 2),
                parallel_backends=parallel_backends,
                log_level=ap_cfg.get("log_level", "INFO"),
                pipeline_config=pipeline_config,
                event_bus=self._event_bus,
            )
            engine.run()
        except Exception as exc:
            self._event_bus.emit("pipeline_error", message=str(exc))

    # ── keybinding actions ────────────────────────────────────────────────────

    def action_clear_input(self) -> None:
        self.query_one("#cmd-input", Input).clear()
        self.query_one("#suggestions", OptionList).display = False

    def action_show_help(self) -> None:
        self._cmd_help([])

    # ── helpers ───────────────────────────────────────────────────────────────

    def _log(self, message: str, level: str = "info") -> None:
        self.query_one(LogPanel).log_event(message, level)


# ── entry point ───────────────────────────────────────────────────────────────

def launch() -> None:
    """Entry point for the `autopilot` CLI command."""
    app = AutopilotApp(project_path=Path.cwd())
    app.run()
