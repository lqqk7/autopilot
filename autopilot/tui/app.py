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

from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from autopilot.backends.base import BackendBase
from autopilot.tui.commands import COMMANDS, completions_for, lookup, parse
from autopilot.tui.event_bus import EventBus
from autopilot.tui.i18n import get_language, set_language, t
from autopilot.tui.widgets.feature_table import FeatureRow, FeatureTable
from autopilot.tui.widgets.header import AppHeader
from autopilot.tui.widgets.log_panel import LogPanel


class AutopilotApp(App):
    """Full-screen TUI for the autopilot pipeline."""

    CSS = """
    Screen {
        background: $background;
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    FeatureTable {
        height: 1fr;
        min-height: 4;
        border: tall $accent-darken-2;
    }

    LogPanel {
        height: 1fr;
    }

    #suggestions {
        height: auto;
        max-height: 10;
        background: $surface-darken-1;
        border: tall $accent;
        display: none;
    }

    #input-row {
        height: 1;
        padding: 0 1;
        background: $surface;
    }

    #prompt-label {
        width: auto;
        color: $accent;
    }

    #cmd-input {
        width: 1fr;
        border: none;
        background: $surface;
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("escape", "clear_input", "Clear / close suggestions"),
        Binding("f1", "show_help", "Help"),
    ]

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self.project_path = project_path
        self._event_bus = EventBus()
        self._pipeline_thread: threading.Thread | None = None
        self._pipeline_running = False
        self._quit_confirmed = False
        self._active_backends: list[BackendBase] = []

    # ── layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield AppHeader(self.project_path)
        with Vertical(id="main"):
            yield FeatureTable()
            yield LogPanel()
        yield OptionList(id="suggestions")
        with Horizontal(id="input-row"):
            yield Static("> ", id="prompt-label")
            yield Input(placeholder="/help  /run  /check  /redo  /status", id="cmd-input")

    def on_mount(self) -> None:
        self.title = "Autopilot"
        self._load_config()
        self.set_interval(0.1, self._poll_events)
        self._log(t("welcome"), level="info")
        self.query_one("#cmd-input", Input).focus()

    # ── config loading ────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        """Read .autopilot/config.toml and sync language + header config row."""
        config_path = self.project_path / ".autopilot" / "config.toml"
        if not config_path.exists():
            return
        try:
            cfg = toml.loads(config_path.read_text(encoding="utf-8"))
            ap_cfg = cfg.get("autopilot", {})
            set_language(ap_cfg.get("language", "en"))
            self.query_one(AppHeader).update_config(ap_cfg)
        except Exception:
            pass  # config unreadable → keep defaults

    # ── keyboard: arrow-key navigation in suggestions ─────────────────────────

    def on_key(self, event: events.Key) -> None:
        suggestions = self.query_one("#suggestions", OptionList)
        if not suggestions.display:
            return

        key = event.key
        if key == "up":
            suggestions.action_cursor_up()
            event.prevent_default()
            event.stop()
        elif key == "down":
            suggestions.action_cursor_down()
            event.prevent_default()
            event.stop()
        elif key in ("tab", "right"):
            self._accept_suggestion(suggestions)
            event.prevent_default()
            event.stop()
        elif key == "escape":
            suggestions.display = False
            event.prevent_default()
            event.stop()
        # Enter is handled by Input.Submitted; don't intercept here

    def _accept_suggestion(self, suggestions: OptionList) -> None:
        """Fill input with the highlighted suggestion and close the list."""
        idx = suggestions.highlighted
        if idx is not None:
            opt = suggestions.get_option_at_index(idx)
            cmd_input = self.query_one("#cmd-input", Input)
            # strip args_hint, keep just "/command"
            cmd_input.value = str(opt.id)
            suggestions.display = False

    # ── event bus polling ─────────────────────────────────────────────────────

    def _poll_events(self) -> None:
        table = self.query_one(FeatureTable)
        log = self.query_one(LogPanel)
        header = self.query_one(AppHeader)

        for ev in self._event_bus.drain():
            d = ev.data
            if ev.type == "phase_change":
                phase = d.get("to_phase", "")
                header.update_phase(phase)
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
                header.update_progress(table.count_done(), table.count_total())

            elif ev.type == "log":
                log.log_event(
                    d.get("message", ""),
                    level=d.get("level", "info"),
                    feature_id=d.get("feature_id"),
                )

            elif ev.type == "auto_commit":
                log.log_commit(d.get("feature_id", ""), d.get("message", ""))

            elif ev.type == "backend_switch":
                header.update_backend(d.get("to_backend", ""))
                log.log_event(
                    f"Backend switch: {d.get('from_backend')} → {d.get('to_backend')}",
                    level="warning",
                )

            elif ev.type == "worker_start":
                header.update_workers(d.get("active", 0), d.get("total", 0))

            elif ev.type == "human_pause":
                reason = d.get("reason", "")
                doc_path = d.get("doc_path", "")
                log.log_phase("HUMAN_PAUSE")
                log.log_event(t("human_pause_title"), level="success")
                if doc_path:
                    log.log_event(t("human_pause_path", doc_path=doc_path), level="info")
                log.log_event(t("human_pause_step1"), level="info")
                log.log_event(t("human_pause_step2"), level="info")
                log.log_event(t("human_pause_step3"), level="warning")

            elif ev.type == "pipeline_done":
                self._pipeline_running = False
                self._quit_confirmed = False
                phase = d.get("final_phase", "DONE")
                header.update_phase(phase)
                if phase == "HUMAN_PAUSE":
                    log.log_event(t("pipeline_paused"), level="warning")
                else:
                    log.log_event(
                        t("pipeline_finished", phase=phase, elapsed=d.get("elapsed", "")),
                        level="success",
                    )

            elif ev.type == "pipeline_error":
                self._pipeline_running = False
                self._quit_confirmed = False
                log.log_error(d.get("message", "Pipeline error"))

    # ── slash command input ───────────────────────────────────────────────────

    @on(Input.Changed, "#cmd-input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        text = event.value
        suggestions = self.query_one("#suggestions", OptionList)

        if text.startswith("/"):
            matches = completions_for(text)
            suggestions.clear_options()
            if matches:
                for usage, desc in matches:
                    suggestions.add_option(
                        Option(f"[bold]{usage}[/bold]  [dim]{desc}[/dim]", id=usage.split()[0])
                    )
                suggestions.display = True
            else:
                suggestions.display = False
        else:
            suggestions.display = False

    @on(Input.Submitted, "#cmd-input")
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        suggestions = self.query_one("#suggestions", OptionList)
        # If a suggestion is highlighted, Enter selects it instead of submitting
        if suggestions.display and suggestions.highlighted is not None:
            self._accept_suggestion(suggestions)
            return
        raw = event.value.strip()
        self.query_one("#cmd-input", Input).clear()
        suggestions.display = False
        if raw:
            self._execute(raw)

    @on(OptionList.OptionSelected, "#suggestions")
    def _on_suggestion_selected(self, event: OptionList.OptionSelected) -> None:
        cmd_input = self.query_one("#cmd-input", Input)
        cmd_input.value = str(event.option.id)
        cmd_input.focus()
        self.query_one("#suggestions", OptionList).display = False

    # ── command dispatch ──────────────────────────────────────────────────────

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

    def _cmd_lang(self, args: list[str]) -> None:
        log = self.query_one(LogPanel)
        if not args:
            log.log_event(t("lang_current", lang=get_language()), level="info")
            return
        lang = args[0].lower()
        if lang not in ("en", "zh"):
            log.log_event(t("lang_unknown", lang=lang), level="warning")
            return
        set_language(lang)
        # refresh all i18n-aware widgets
        self.query_one(AppHeader).refresh_labels()
        self.query_one(FeatureTable).rebuild_columns()
        log.log_event(t("lang_switched"), level="success")
        log.log_event(t("lang_restart_note"), level="info")

    def _cmd_quit(self, _args: list[str]) -> None:
        if self._pipeline_running and not self._quit_confirmed:
            self._quit_confirmed = True
            self._log(t("quit_warning"), "warning")
            return
        self._stop_pipeline()
        self.exit()

    def _cmd_exit(self, args: list[str]) -> None:
        self._cmd_quit(args)

    def action_quit(self) -> None:
        """Override Textual's built-in quit (Ctrl+C) to kill subprocesses first."""
        self._stop_pipeline()
        self.exit()

    def _stop_pipeline(self) -> None:
        """Send SIGKILL to every active backend subprocess, then clear the list."""
        for backend in self._active_backends:
            backend.stop()
        self._active_backends.clear()

    def _cmd_init(self, args: list[str]) -> None:
        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        if autopilot_dir.exists():
            log.log_event(".autopilot/ already exists — use /check to validate.", "warning")
            return
        backend = "claude"
        if "--backend" in args:
            idx = args.index("--backend")
            if idx + 1 < len(args):
                backend = args[idx + 1]
        elif args and not args[0].startswith("--"):
            backend = args[0]
        if backend not in ("claude", "codex", "opencode"):
            log.log_event(f"Unknown backend {backend!r}. Use: claude | codex | opencode", "warning")
            return
        try:
            from autopilot.init_project import init_project
            init_project(project_path=self.project_path, backend=backend)
            log.log_event(f"✓ Initialized .autopilot/  (backend: {backend})", "success")
            log.log_event("Add requirements to .autopilot/requirements/ then run /run", "info")
        except Exception as exc:
            log.log_error(str(exc))

    def _cmd_check(self, _args: list[str]) -> None:
        log = self.query_one(LogPanel)
        log.log_phase("CHECK")
        threading.Thread(target=self._run_check, args=(log,), daemon=True).start()

    def _run_check(self, log: LogPanel) -> None:
        import os
        import shutil

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

        ap_cfg: dict = {}
        try:
            raw_cfg = toml.loads(config_path.read_text(encoding="utf-8"))
            ap_cfg = raw_cfg.get("autopilot", {})
            from autopilot.pipeline.config import PipelineConfig
            PipelineConfig.from_toml(ap_cfg)
            ok("config.toml valid")
        except Exception as exc:
            fail(f"config.toml invalid: {exc}"); return

        cli_map = {"claude": "claude", "codex": "codex", "opencode": "opencode"}
        for bn in [ap_cfg.get("backend", "claude")] + ap_cfg.get("parallel_backends", []):
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

        self.call_from_thread(log.log_event, t("preflight_done"), "success")

    def _cmd_status(self, _args: list[str]) -> None:
        from autopilot.pipeline.context import FeatureList, PipelineState

        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        state_path = autopilot_dir / "state.json"
        if not state_path.exists():
            log.log_event(t("no_state_found"), "warning"); return
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

    def _cmd_sessions(self, args: list[str]) -> None:
        from autopilot.sessions.reader import list_sessions

        log = self.query_one(LogPanel)
        sessions_dir = self.project_path / ".autopilot" / "sessions"

        # /sessions show SESSION_ID
        if args and args[0] == "show":
            session_id = args[1] if len(args) > 1 else "latest"
            show_output = "--output" in args
            self._show_session(log, sessions_dir, session_id, show_output)
            return

        sessions = list_sessions(sessions_dir)
        if not sessions:
            log.log_event(t("no_sessions"), "info"); return
        log.log_phase("SESSIONS")
        for s in sessions[:15]:
            log.log_event(
                f"{s['session_id'][:20]}  {s['status']}  {s['phase']}  "
                f"{s['features_done']}/{s['features_total']} features",
                "info",
            )

    def _show_session(self, log: LogPanel, sessions_dir: "Path", session_id: str, show_output: bool) -> None:
        from autopilot.sessions.reader import list_sessions, load_session_events

        sessions = list_sessions(sessions_dir)
        if not sessions:
            log.log_event(t("no_sessions"), "info"); return

        if session_id == "latest":
            meta = sessions[0]
        else:
            matches = [s for s in sessions if s["session_id"].startswith(session_id)]
            if not matches:
                log.log_event(f"Session {session_id!r} not found", "error"); return
            meta = matches[0]

        log.log_phase(f"SESSION {meta['session_id'][:16]}")
        log.log_event(f"Status: {meta['status']}  Phase: {meta['phase']}  Features: {meta['features_done']}/{meta['features_total']}", "info")
        try:
            events_list = load_session_events(sessions_dir / f"{meta['session_id']}.jsonl")
            for ev in events_list[:30]:
                ev_type = ev.get("type", "")
                if ev_type == "phase_change":
                    log.log_event(f"→ {ev.get('to_phase')}", "info")
                elif ev_type == "feature_done":
                    status = "✅" if ev.get("success") else "✗"
                    log.log_event(f"  {status} {ev.get('feature_id')}  {ev.get('title', '')}", "info")
                elif ev_type == "agent_call" and show_output:
                    log.log_event(f"    [{ev.get('phase')}] {ev.get('agent_name')} {ev.get('backend_name')} {ev.get('duration_s', 0):.0f}s", "info")
        except Exception:
            pass

    def _cmd_run(self, _args: list[str]) -> None:
        if self._pipeline_running:
            self._log(t("pipeline_already_running"), "warning"); return
        self._start_pipeline(resume=False)

    def _cmd_resume(self, _args: list[str]) -> None:
        if self._pipeline_running:
            self._log(t("pipeline_already_running"), "warning"); return
        self._start_pipeline(resume=True)

    def _cmd_redo(self, args: list[str]) -> None:
        from autopilot.pipeline.context import FeatureList, Phase, PipelineState

        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        fl_path = autopilot_dir / "feature_list.json"
        if not fl_path.exists():
            log.log_event(t("no_feature_list"), "warning"); return

        fl = FeatureList.load(fl_path)
        if "--failed" in args:
            targets = [f for f in fl.features if f.status == "failed"]
        elif args:
            fid = args[0]
            targets = [f for f in fl.features if f.id == fid]
            if not targets:
                log.log_event(t("redo_not_found", fid=fid), "error"); return
        else:
            log.log_event(t("redo_usage"), "warning"); return

        for f in targets:
            f.status = "pending"
            f.fix_retries = 0
            log.log_event(t("redo_reset", fid=f.id), "info")
        fl.save(fl_path)

        state_path = autopilot_dir / "state.json"
        if not state_path.exists():
            log.log_event(t("state_not_found"), "error"); return
        state = PipelineState.load(state_path)
        if state.phase not in (Phase.DEV_LOOP,):
            state.phase = Phase.DEV_LOOP
        state.phase_retries = 0
        state.current_feature_id = None
        state.active_feature_ids = []
        state.save(state_path)
        log.log_event(t("redo_done", n=len(targets)), "success")

    def _cmd_add(self, args: list[str]) -> None:
        from autopilot.pipeline.context import Feature, FeatureList, Phase, PipelineState

        log = self.query_one(LogPanel)
        if not args:
            log.log_event(
                "Usage: /add TITLE [--phase backend|frontend|fullstack|infra] [--depends-on feat-001,feat-002]",
                "warning",
            )
            return

        # Parse flags; everything else is the title
        phase = "backend"
        depends_on = ""
        title_parts: list[str] = []
        i = 0
        while i < len(args):
            if args[i] == "--phase" and i + 1 < len(args):
                phase = args[i + 1]; i += 2
            elif args[i] == "--depends-on" and i + 1 < len(args):
                depends_on = args[i + 1]; i += 2
            else:
                title_parts.append(args[i]); i += 1

        title = " ".join(title_parts)
        if not title:
            log.log_event("Usage: /add TITLE [--phase X] [--depends-on IDs]", "warning"); return
        if phase not in ("backend", "frontend", "fullstack", "infra"):
            log.log_event(f"Unknown phase {phase!r}. Use: backend | frontend | fullstack | infra", "warning"); return

        autopilot_dir = self.project_path / ".autopilot"
        fl_path = autopilot_dir / "feature_list.json"
        if not fl_path.exists():
            log.log_event(t("no_feature_list"), "error"); return

        try:
            fl = FeatureList.load(fl_path)
            nums = []
            for f in fl.features:
                try:
                    nums.append(int(f.id.split("-")[1]))
                except (IndexError, ValueError):
                    pass
            new_id = f"feat-{max(nums, default=0) + 1:03d}"
            dep_list = [d.strip() for d in depends_on.split(",") if d.strip()] if depends_on else []
            fl.features.append(Feature(
                id=new_id, title=title, phase=phase,
                depends_on=dep_list, status="pending",
                test_file=f"tests/test_{new_id.replace('-', '_')}.py",
            ))
            fl.save(fl_path)

            state_path = autopilot_dir / "state.json"
            if state_path.exists():
                state = PipelineState.load(state_path)
                if state.phase in (Phase.DONE, Phase.DELIVERY, Phase.KNOWLEDGE, Phase.DOC_UPDATE):
                    state.phase = Phase.DEV_LOOP
                    state.phase_retries = 0
                    state.save(state_path)
                    log.log_event(f"✓ {new_id}: {title}  (pipeline reset to DEV_LOOP — run /resume)", "success")
                    return
            log.log_event(f"✓ {new_id}: {title}", "success")
        except Exception as exc:
            log.log_error(str(exc))

    def _cmd_kb(self, args: list[str]) -> None:
        self._cmd_knowledge(args)

    def _cmd_knowledge(self, args: list[str]) -> None:
        from autopilot.knowledge.local import LocalKnowledge

        log = self.query_one(LogPanel)
        kb_dir = self.project_path / ".autopilot" / "knowledge"
        if not kb_dir.exists():
            log.log_event("No knowledge base found — run the pipeline first.", "warning"); return

        sub = args[0].lower() if args else "list"

        if sub == "list" or not args:
            files = sorted(kb_dir.rglob("*.md"))
            log.log_phase("KNOWLEDGE")
            if not files:
                log.log_event("Knowledge base is empty.", "info"); return
            for md in files:
                log.log_event(str(md.relative_to(kb_dir)), "info")
        elif sub == "search":
            query = " ".join(args[1:])
            if not query:
                log.log_event("Usage: /knowledge search QUERY", "warning"); return
            self._knowledge_search(log, kb_dir, query)
        else:
            # Treat entire args as a search query (no sub-command prefix needed)
            self._knowledge_search(log, kb_dir, " ".join(args))

    def _knowledge_search(self, log: LogPanel, kb_dir: "Path", query: str) -> None:
        from autopilot.knowledge.local import LocalKnowledge

        kb = LocalKnowledge(kb_dir)
        content = kb.read_all()
        matches = [ln for ln in content.splitlines() if query.lower() in ln.lower() and ln.strip()]
        log.log_phase(f"SEARCH: {query}")
        if matches:
            for m in matches[:15]:
                log.log_event(m.strip(), "info")
        else:
            log.log_event("No matches found.", "info")

    # ── v0.4–v0.9 commands ────────────────────────────────────────────────────

    def _cmd_missions(self, _args: list[str]) -> None:
        """Show current mission and per-feature state (v0.4)."""
        from autopilot.pipeline.context import Mission, MissionStore

        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        store = MissionStore(autopilot_dir)
        mid = store.active_mission_id()
        if not mid:
            log.log_event(t("missions_none"), "warning")
            return

        mission_path = store._mission_dir(mid) / "mission.json"
        mission = Mission.load(mission_path)
        log.log_phase("MISSIONS")
        log.log_event(t("missions_header", title=mission.title, status=mission.status, mid=mid), "info")

        feat_dir = store._mission_dir(mid) / "features"
        if not feat_dir.exists() or not list(feat_dir.glob("*.json")):
            log.log_event(t("missions_no_features"), "info")
            return

        from autopilot.pipeline.context import FeatureState
        for path in sorted(feat_dir.glob("*.json")):
            try:
                fs = FeatureState.load(path)
                log.log_event(
                    t("missions_feat_row",
                      fid=fs.id,
                      status=fs.status,
                      retry=fs.retry_count,
                      backend=fs.last_backend or "—",
                      phase=fs.phase),
                    "success" if fs.status == "completed" else "warning" if fs.status == "failed" else "info",
                )
            except Exception:
                pass

    def _cmd_handoff(self, args: list[str]) -> None:
        """Show latest handoff or a specific handoff (v0.9)."""
        from autopilot.handoff.loader import HandoffLoader

        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        loader = HandoffLoader(autopilot_dir)

        if args and args[0].lower() != "latest":
            handoff = loader.load_by_id(args[0])
        else:
            handoff = loader.latest()

        if not handoff:
            log.log_event(t("handoff_none"), "warning")
            return

        log.log_phase("HANDOFF")
        log.log_event(t("handoff_header", hid=handoff.handoff_id, session=handoff.from_session), "info")
        for line in handoff.to_prompt_block().splitlines():
            if line.strip():
                log.log_event(line, "info")

    def _cmd_principles(self, args: list[str]) -> None:
        """List or add principles (v0.7)."""
        import json as _json

        from autopilot.principles.loader import PrinciplesLoader

        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        sub = args[0].lower() if args else "list"

        if sub == "add":
            # /principles add PHASE rule text...
            if len(args) < 3:
                log.log_event(t("principles_add_usage"), "warning")
                return
            phase = args[1].upper()
            rule = " ".join(args[2:])
            principles_path = autopilot_dir / "principles.jsonl"
            try:
                entry = {"phase": phase, "rule": rule, "severity": "warn"}
                with principles_path.open("a", encoding="utf-8") as f:
                    f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
                log.log_event(t("principles_added", severity="warn", phase=phase, rule=rule), "success")
            except Exception as exc:
                log.log_error(t("principles_add_error", exc=exc))
            return

        # list — show by phase (all phases)
        loader = PrinciplesLoader(autopilot_dir)
        log.log_phase("PRINCIPLES")
        from autopilot.pipeline.context import Phase
        all_phases = [p.value for p in Phase if p not in (Phase.INIT, Phase.HUMAN_PAUSE, Phase.DONE, Phase.DEV_LOOP)]
        found_any = False
        for phase in all_phases:
            rules = loader.load_for_phase(phase)
            if not rules:
                continue
            found_any = True
            log.log_event(t("principles_header", phase=phase), "info")
            for p in rules:
                icon = "❌" if p.severity == "error" else "⚠️" if p.severity == "warn" else "ℹ️"
                log.log_event(f"  {icon}  {p.rule}", "info")
        if not found_any:
            log.log_event(t("principles_none"), "info")

    def _cmd_skills(self, args: list[str]) -> None:
        """List built-in skills or match skills to a query (v0.6)."""
        from autopilot.skills.registry import SkillRegistry

        log = self.query_one(LogPanel)
        reg = SkillRegistry()
        sub = args[0].lower() if args else "list"

        if sub == "match" or (args and sub not in ("list",)):
            query = " ".join(args[1:]) if sub == "match" else " ".join(args)
            if not query:
                log.log_event("Usage: /skills match FEATURE_DESCRIPTION", "warning")
                return
            matches = reg.match(query)
            log.log_phase(f"SKILLS MATCH: {query}")
            if not matches:
                log.log_event(t("skills_no_match", query=query), "info")
                return
            log.log_event(t("skills_match_header", query=query), "info")
            for s in matches:
                log.log_event(t("skills_row", name=s.name, cat=s.category, desc=s.description or s.prompt_hint[:60]), "info")
                if s.prompt_hint:
                    for line in s.prompt_hint.splitlines()[:2]:
                        log.log_event(f"    {line}", "info")
        else:
            skills = reg.all_skills()
            log.log_phase("SKILLS")
            log.log_event(t("skills_list_header", n=len(skills)), "info")
            for s in skills:
                phases = f"  phases: {','.join(s.trigger.phases)}" if s.trigger.phases else ""
                kw = ", ".join(s.trigger.keywords[:4])
                log.log_event(
                    t("skills_row", name=s.name, cat=s.category, desc=s.description or "—"),
                    "info",
                )
                log.log_event(f"    keywords: {kw}{phases}", "info")

    # ── config commands ───────────────────────────────────────────────────────

    def _cmd_set(self, args: list[str]) -> None:  # noqa: C901
        log = self.query_one(LogPanel)
        config_path = self.project_path / ".autopilot" / "config.toml"
        if len(args) < 2:
            log.log_event(t("set_usage"), "warning"); return
        if not config_path.exists():
            log.log_event(t("config_not_init"), "error"); return

        key = args[0].lower()
        value_parts = args[1:]

        try:
            cfg = toml.loads(config_path.read_text(encoding="utf-8"))
            ap = cfg.setdefault("autopilot", {})

            if key == "backend":
                backend = value_parts[0]
                if backend not in ("claude", "codex", "opencode"):
                    log.log_event(t("set_bad_backend", backend=backend), "warning"); return
                ap["backend"] = backend

            elif key == "workers":
                try:
                    n = int(value_parts[0])
                    if n < 1: raise ValueError()
                except ValueError:
                    log.log_event(t("set_bad_workers"), "warning"); return
                ap["max_parallel"] = n

            elif key == "parallel-backends":
                backends = [b.strip() for b in value_parts[0].split(",") if b.strip()]
                invalid = [b for b in backends if b not in ("claude", "codex", "opencode")]
                if invalid:
                    log.log_event(t("set_bad_backend", backend=",".join(invalid)), "warning"); return
                ap["parallel_backends"] = backends

            elif key == "fallback-backends":
                backends = [b.strip() for b in value_parts[0].split(",") if b.strip()]
                invalid = [b for b in backends if b not in ("claude", "codex", "opencode")]
                if invalid:
                    log.log_event(t("set_bad_backend", backend=",".join(invalid)), "warning"); return
                ap["fallback_backends"] = backends

            elif key == "log-level":
                level = value_parts[0].upper()
                if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
                    log.log_event(t("set_bad_loglevel"), "warning"); return
                ap["log_level"] = level

            elif key == "model":
                # /set model BACKEND MODEL  (backend required for clarity)
                if len(value_parts) < 2:
                    log.log_event("Usage: /set model BACKEND MODEL  e.g. /set model claude claude-opus-4-6", "warning"); return
                backend_name, model_name = value_parts[0], value_parts[1]
                if backend_name not in ("claude", "codex", "opencode"):
                    log.log_event(t("set_bad_backend", backend=backend_name), "warning"); return
                ap["model"] = model_name
                log.log_event(t("set_ok", key=f"model ({backend_name})", value=model_name), "success")
                config_path.write_text(toml.dumps(cfg), encoding="utf-8")
                self.query_one(AppHeader).update_config(ap)
                return

            elif key == "review-mode":
                mode = value_parts[0].lower()
                if mode not in ("self", "cross", "backend"):
                    log.log_event(t("set_bad_review_mode"), "warning"); return
                ap.setdefault("review", {})["mode"] = mode

            elif key == "review-backend":
                backend = value_parts[0]
                if backend not in ("claude", "codex", "opencode"):
                    log.log_event(t("set_bad_backend", backend=backend), "warning"); return
                review = ap.setdefault("review", {})
                review["backend"] = backend
                review["mode"] = "backend"
                key = "review-backend (mode auto → backend)"

            else:
                log.log_event(t("set_unknown_key", key=key), "warning"); return

            config_path.write_text(toml.dumps(cfg), encoding="utf-8")
            self.query_one(AppHeader).update_config(ap)
            log.log_event(t("set_ok", key=key, value=value_parts[0]), "success")

        except Exception as exc:
            log.log_error(t("set_config_error", exc=exc))

    def _cmd_config(self, _args: list[str]) -> None:
        import subprocess
        log = self.query_one(LogPanel)
        config_path = self.project_path / ".autopilot" / "config.toml"
        if not config_path.exists():
            log.log_event(t("config_not_init"), "error"); return
        try:
            subprocess.Popen(["open", str(config_path)])
            log.log_event(t("config_opening"), "info")
        except Exception as exc:
            log.log_error(t("config_open_error", exc=exc))

    def _cmd_reload(self, _args: list[str]) -> None:
        log = self.query_one(LogPanel)
        config_path = self.project_path / ".autopilot" / "config.toml"
        if not config_path.exists():
            log.log_event(t("config_not_init"), "error"); return
        try:
            cfg = toml.loads(config_path.read_text(encoding="utf-8"))
            ap_cfg = cfg.get("autopilot", {})
            set_language(ap_cfg.get("language", "en"))
            header = self.query_one(AppHeader)
            header.update_config(ap_cfg)
            header.refresh_labels()
            self.query_one(FeatureTable).rebuild_columns()
            log.log_event(t("reload_ok"), "success")
        except Exception as exc:
            log.log_error(t("reload_error", exc=exc))

    # ── pipeline runner ───────────────────────────────────────────────────────

    def _start_pipeline(self, resume: bool) -> None:
        log = self.query_one(LogPanel)
        autopilot_dir = self.project_path / ".autopilot"
        if not autopilot_dir.exists():
            log.log_event(".autopilot/ not found — run /check first", "error"); return
        self._pipeline_running = True
        self._event_bus.clear()
        log.log_event(t("resuming" if resume else "starting"), "info")
        thread = threading.Thread(
            target=self._pipeline_worker, args=(resume,), daemon=True
        )
        self._pipeline_thread = thread
        thread.start()

    def _pipeline_worker(self, resume: bool) -> None:
        try:
            from autopilot.backends import get_backend
            from autopilot.pipeline.config import PipelineConfig
            from autopilot.pipeline.context import Phase, PipelineState
            from autopilot.pipeline.engine import PipelineEngine

            autopilot_dir = self.project_path / ".autopilot"
            cfg = toml.loads((autopilot_dir / "config.toml").read_text())
            ap_cfg = cfg.get("autopilot", {})
            pipeline_config = PipelineConfig.from_toml(ap_cfg)
            allow = pipeline_config.allow_dangerous_permissions
            backend = get_backend(
                ap_cfg["backend"], model=pipeline_config.model, allow_dangerous=allow
            )
            parallel_backends = [
                get_backend(n, model=pipeline_config.model, allow_dangerous=allow)
                for n in ap_cfg.get("parallel_backends", [])
            ]
            # Store refs so _stop_pipeline() can kill in-flight subprocesses on /quit
            self._active_backends = [backend] + parallel_backends

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
        finally:
            self._active_backends.clear()

    # ── keybinding actions ────────────────────────────────────────────────────

    def action_clear_input(self) -> None:
        self.query_one("#cmd-input", Input).clear()
        self.query_one("#suggestions", OptionList).display = False

    def action_show_help(self) -> None:
        self._cmd_help([])

    # ── helper ───────────────────────────────────────────────────────────────

    def _log(self, message: str, level: str = "info") -> None:
        self.query_one(LogPanel).log_event(message, level)


# ── entry point ───────────────────────────────────────────────────────────────

def launch() -> None:
    """Entry point for the `autopilot` CLI command."""
    app = AutopilotApp(project_path=Path.cwd())
    app.run()
