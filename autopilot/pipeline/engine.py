from __future__ import annotations

import itertools
import logging
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

import click
import toml

from autopilot.agents.loader import AgentLoader
from autopilot.backends import get_backend
from autopilot.backends.base import BackendBase, BackendResult, ErrorType, RunContext
from autopilot.knowledge.compactor import KnowledgeCompactor
from autopilot.knowledge.local import LocalKnowledge
from autopilot.notifications.telegram import TelegramNotifier
from autopilot.pipeline.config import PipelineConfig
from autopilot.pipeline.context import AgentOutput, Feature, FeatureList, Phase, PipelineState, RunResult
from autopilot.pipeline.phases import DELIVERY_DOCS, ExitCondition, PhaseRunner
from autopilot.pipeline.retry import LOCAL_RETRY_TYPES, exponential_backoff, handle_error
from autopilot.pipeline.worker import FeatureWorker
from autopilot.sessions.recorder import SessionRecorder
from autopilot.tui.event_bus import EventBus

logger = logging.getLogger(__name__)

_PHASE_TO_AGENT: dict[Phase, str] = {
    Phase.INTERVIEW: "interviewer",
    Phase.DOC_GEN: "doc_gen",
    Phase.PLANNING: "planner",
    Phase.CODE: "coder",
    Phase.TEST: "tester",
    Phase.REVIEW: "reviewer",
    Phase.FIX: "fixer",
    Phase.DOC_UPDATE: "doc_gen",
    Phase.KNOWLEDGE: "doc_gen",
    Phase.DELIVERY: "doc_gen",
}


class PipelineEngine:
    def __init__(
        self,
        project_path: Path,
        backend: BackendBase,
        max_parallel: int = 2,
        parallel_backends: list[BackendBase] | None = None,
        log_level: str = "INFO",
        pipeline_config: PipelineConfig | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.project_path = project_path
        self.autopilot_dir = project_path / ".autopilot"
        self.backend = backend
        self._max_parallel = max(1, max_parallel)
        self._parallel_backends: list[BackendBase] = parallel_backends or []
        self._cfg = pipeline_config or PipelineConfig()
        self.phase_runner = PhaseRunner()
        self.exit_condition = ExitCondition()
        token = os.environ.get("AUTOPILOT_TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("AUTOPILOT_TELEGRAM_CHAT_ID", "")
        self.notifier = TelegramNotifier(token=token, chat_id=chat_id) if (token and self._cfg.telegram_enabled) else None
        self._run_start: float = 0.0
        self._collected_artifacts: list[str] = []
        self._knowledge_count: int = 0
        self._compaction_count: int = 0
        self._backend_name: str = type(backend).__name__.lower().replace("backend", "")
        self._log_level: int = getattr(logging, log_level.upper(), logging.INFO)
        self._fallback_backends: list[BackendBase] = self._load_fallback_backends()
        self._fallback_index: int = -1   # -1 = primary, 0+ = fallback
        self._backend_switches: int = 0
        self._loader = AgentLoader()
        self._compactor = KnowledgeCompactor()
        self._overview_lock = threading.Lock()
        self._git_lock = threading.Lock()
        self._recorder: SessionRecorder | None = None
        self._event_bus: EventBus | None = event_bus

    def state_path(self) -> Path:
        return self.autopilot_dir / "state.json"

    def load_state(self) -> PipelineState:
        return PipelineState.load(self.state_path())

    def save_state(self, state: PipelineState) -> None:
        state.save(self.state_path())

    def advance(self, state: PipelineState) -> Phase:
        """Determine the next phase based on current state (no AI involved)."""
        if state.phase == Phase.INIT:
            return Phase.INTERVIEW
        if state.phase == Phase.INTERVIEW:
            # Pause for human to fill in answers.
            # post_interview_phase tells resume where to go next (DOC_GEN or PLANNING).
            return Phase.HUMAN_PAUSE
        if state.phase == Phase.DOC_GEN:
            docs = self.autopilot_dir / "docs"
            return Phase.PLANNING if self.exit_condition.doc_gen_complete(docs) else Phase.DOC_GEN
        if state.phase == Phase.PLANNING:
            fl_path = self.autopilot_dir / "feature_list.json"
            return Phase.DEV_LOOP if self.exit_condition.planning_complete(fl_path) else Phase.PLANNING
        if state.phase == Phase.DELIVERY:
            docs = self.autopilot_dir / "docs"
            return Phase.DONE if self.exit_condition.delivery_complete(docs) else Phase.DELIVERY
        return self.phase_runner.next_phase(state.phase, passed=True)

    def _load_fallback_backends(self) -> list[BackendBase]:
        config_path = self.autopilot_dir / "config.toml"
        if not config_path.exists():
            return []
        try:
            config = toml.loads(config_path.read_text())
            names = config.get("autopilot", {}).get("fallback_backends", [])
            return [get_backend(n, model=self._cfg.model, allow_dangerous=self._cfg.allow_dangerous_permissions) for n in names if n]
        except Exception:
            logger.exception("Failed to load fallback_backends from %s — no fallback will be used", config_path)
            return []

    def _try_switch_backend(self, error_type: ErrorType) -> bool:
        """Switch to next fallback backend. Returns True if switched."""
        next_idx = self._fallback_index + 1
        if next_idx >= len(self._fallback_backends):
            return False
        old_name = self._backend_name
        self.backend = self._fallback_backends[next_idx]
        self._fallback_index = next_idx
        self._backend_name = type(self.backend).__name__.lower().replace("backend", "")
        self._backend_switches += 1
        logger.warning("Backend switch: %s → %s (reason: %s)", old_name, self._backend_name, error_type)
        if self.notifier:
            self.notifier.send_backend_switch(old_name, self._backend_name, error_type.value)
        if self._recorder:
            self._recorder.backend_switch(old_name, self._backend_name, error_type.value)
        if self._event_bus:
            self._event_bus.emit("backend_switch", from_backend=old_name, to_backend=self._backend_name, reason=error_type.value)
        return True

    def check_pause(self, state: PipelineState) -> bool:
        """Return True if the pipeline should pause for human intervention."""
        return state.phase_retries >= self._cfg.max_phase_retries

    @staticmethod
    def _exponential_backoff(attempt: int, base: float = 10.0) -> float:
        return exponential_backoff(attempt, base)

    def _handle_error(self, result: BackendResult, retry_count: int) -> tuple[bool, float]:
        return handle_error(result, retry_count)

    @staticmethod
    def _rebuild_ctx(ctx: RunContext, knowledge_md: str) -> RunContext:
        return RunContext(
            project_path=ctx.project_path,
            docs_path=ctx.docs_path,
            feature=ctx.feature,
            knowledge_md=knowledge_md,
            answers_md=ctx.answers_md,
            extra_files=ctx.extra_files,
        )

    def run_phase(self, state: PipelineState) -> bool:
        """Execute the current phase via the backend. Returns True on success."""
        kb = LocalKnowledge(self.autopilot_dir / "knowledge")

        feature = None
        if state.current_feature_id:
            fl = FeatureList.load(self.autopilot_dir / "feature_list.json")
            feature = next((f for f in fl.features if f.id == state.current_feature_id), None)

        ctx = RunContext(
            project_path=self.project_path,
            docs_path=self.autopilot_dir / "docs",
            feature=feature,
            knowledge_md=kb.read_all(),
        )

        agent_name = _PHASE_TO_AGENT.get(state.phase)
        if not agent_name:
            return True

        if self._compactor.needs_compaction(ctx.knowledge_md):
            ctx = self._rebuild_ctx(ctx, self._compactor.compact(ctx.knowledge_md, self.backend, self.autopilot_dir))
            self._compaction_count += 1

        prompt = self._loader.build_system_prompt(agent_name, ctx)
        local_retry = 0

        phase_timeout = self._cfg.timeout_for(state.phase)

        # Live progress — only in interactive terminals, not in tests/pipes
        progress = None
        if sys.stdout.isatty():
            from autopilot.ui.progress import PhaseProgress
            _doc_phases = (Phase.DOC_GEN, Phase.DELIVERY, Phase.DOC_UPDATE, Phase.KNOWLEDGE)
            docs_path = ctx.docs_path if state.phase in _doc_phases else None
            feature_progress: tuple[int, int] | None = None
            if state.current_feature_id:
                fl_p = FeatureList.load(self.autopilot_dir / "feature_list.json")
                done_p = sum(1 for f in fl_p.features if f.status == "completed")
                feature_progress = (done_p, len(fl_p.features))
            progress = PhaseProgress(
                state.phase.value,
                docs_path=docs_path,
                feature_progress=feature_progress,
                feature_title=feature.title if feature else None,
            )
            progress.start()

        try:
            while True:
                result = self.backend.run(agent_name, prompt, ctx, timeout=phase_timeout)

                if self._recorder:
                    self._recorder.agent_call(
                        phase=state.phase.value,
                        agent_name=agent_name,
                        backend_name=self._backend_name,
                        result=result,
                        local_retry=local_retry,
                        prompt=prompt,
                    )

                if result.success:
                    parsed = self._try_parse_output(result, state, local_retry)
                    if parsed is None:
                        local_retry += 1
                        continue
                    return parsed

                should_retry, wait = handle_error(result, local_retry)
                if should_retry and result.error_type in LOCAL_RETRY_TYPES:
                    local_retry += 1
                    if wait > 0:
                        time.sleep(wait)
                    continue

                if result.error_type == ErrorType.context_overflow:
                    ctx = self._rebuild_ctx(ctx, self._compactor.compact(ctx.knowledge_md, self.backend, self.autopilot_dir))
                    prompt = self._loader.build_system_prompt(agent_name, ctx)
                    self._compaction_count += 1
                    local_retry = 0
                    continue

                # v0.4: fallback backend on rate_limit / quota_exhausted
                if result.error_type in (ErrorType.rate_limit, ErrorType.quota_exhausted):
                    if self._try_switch_backend(result.error_type):
                        local_retry = 0
                        continue

                # File-based fallback for DOC_GEN/DELIVERY: files exist despite timeout/parse error
                if state.phase == Phase.DOC_GEN and self.exit_condition.doc_gen_complete(ctx.docs_path):
                    logger.info("DOC_GEN file-based fallback: all required docs present")
                    state.phase_retries = 0
                    return True
                if state.phase == Phase.DELIVERY and self.exit_condition.delivery_complete(ctx.docs_path):
                    logger.info("DELIVERY file-based fallback: all delivery docs present")
                    state.phase_retries = 0
                    return True

                state.phase_retries += 1
                if result.error_type == ErrorType.timeout and self.notifier:
                    self.notifier.send_timeout(phase=state.phase.value, retry=state.phase_retries)
                return False
        finally:
            if progress:
                progress.stop()

    def _try_parse_output(
        self, result: BackendResult, state: PipelineState, local_retry: int
    ) -> bool | None:
        """Parse agent output. Returns True on success, False on terminal failure, None to retry."""
        try:
            agent_output = AgentOutput.parse(result.output)
            self._collected_artifacts.extend(agent_output.artifacts)
            if agent_output.status != "success":
                logger.info(
                    "Agent status=%r at phase=%s: %s",
                    agent_output.status,
                    state.phase.value,
                    agent_output.summary[:200],
                )
                state.phase_retries += 1
                return False
            state.phase_retries = 0
            return True
        except ValueError:
            fake = BackendResult(
                success=False,
                output=result.output,
                duration_seconds=result.duration_seconds,
                error="output parse failed",
                error_type=ErrorType.parse_error,
            )
            should_retry, _ = handle_error(fake, local_retry)
            if should_retry and local_retry < 3:
                return None  # signal caller to increment local_retry and loop
            # parse failed terminally — check file-based fallback for doc phases
            docs_path = self.autopilot_dir / "docs"
            if state.phase == Phase.DOC_GEN and self.exit_condition.doc_gen_complete(docs_path):
                logger.info("DOC_GEN parse-error fallback: required docs present")
                state.phase_retries = 0
                return True
            if state.phase == Phase.DELIVERY and self.exit_condition.delivery_complete(docs_path):
                logger.info("DELIVERY parse-error fallback: delivery docs present")
                state.phase_retries = 0
                return True
            state.phase_retries += 1
            return False

    def _load_feature_list(self) -> FeatureList | None:
        fl_path = self.autopilot_dir / "feature_list.json"
        if not fl_path.exists():
            return None
        return FeatureList.load(fl_path)

    def _write_run_result(self, state: PipelineState) -> None:
        feature_list = self._load_feature_list()
        total = len(feature_list.features) if feature_list else 0
        done = sum(1 for f in feature_list.features if f.status == "completed") if feature_list else 0
        elapsed = time.monotonic() - self._run_start
        result = RunResult(
            status="done" if state.phase == Phase.DONE else "paused",
            phase=state.phase.value,
            elapsed_seconds=round(elapsed, 1),
            features_total=total,
            features_done=done,
            artifacts=self._collected_artifacts,
            pause_reason=state.pause_reason,
            backend_used=self._backend_name,
            backend_switches=self._backend_switches,
            knowledge_count=sum(1 for _ in (self.autopilot_dir / "knowledge").rglob("*.md")),
            compactions=self._compaction_count,
        )
        result.save(self.autopilot_dir / "run_result.json")

    def run(self) -> None:
        """Main pipeline loop."""
        logging.basicConfig(
            level=self._log_level,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.project_path / "logs" / "autopilot.log"),
            ],
        )
        self._run_start = time.monotonic()
        self._collected_artifacts = []
        self._compaction_count = 0
        self._backend_switches = 0
        self._fallback_index = -1
        self._compaction_count = 0
        state = self.load_state()
        logger.info("Starting pipeline at phase: %s", state.phase)
        start_time = self._run_start

        self._recorder = SessionRecorder(self.autopilot_dir / "sessions")
        self._recorder.session_start(
            backend=self._backend_name,
            phase=state.phase.value,
            max_parallel=self._max_parallel,
        )

        try:
            self._run_loop(state, start_time)
        finally:
            fl = self._load_feature_list()
            fd = sum(1 for f in fl.features if f.status == "completed") if fl else 0
            ft = len(fl.features) if fl else 0
            elapsed = f"{time.monotonic() - self._run_start:.0f}s"
            if self._event_bus:
                self._event_bus.emit(
                    "pipeline_done",
                    final_phase=state.phase.value,
                    elapsed=elapsed,
                    features_done=fd,
                    features_total=ft,
                )
            self._recorder.session_end(
                final_phase=state.phase.value,
                elapsed_s=time.monotonic() - self._run_start,
                features_done=fd,
                features_total=ft,
            )

    def _run_loop(self, state: PipelineState, start_time: float) -> None:
        while state.phase not in (Phase.DONE, Phase.HUMAN_PAUSE):
            if self.check_pause(state):
                failed_phase = state.phase
                state.phase = Phase.HUMAN_PAUSE
                state.pause_reason = f"Max retries exceeded at {failed_phase.value}"
                self.save_state(state)
                logger.warning("HUMAN_PAUSE: %s", state.pause_reason)
                if self.notifier:
                    self.notifier.send_pause(phase=failed_phase.value, reason=state.pause_reason or "")
                break

            if state.phase == Phase.DEV_LOOP:
                self._handle_dev_loop(state)
                continue

            if self._recorder:
                self._recorder.phase_enter(state.phase.value)
            if self._event_bus:
                self._event_bus.emit("phase_change", to_phase=state.phase.value)
            _phase_t0 = time.monotonic()
            passed = self.run_phase(state)
            if self._recorder:
                self._recorder.phase_exit(state.phase.value, passed, time.monotonic() - _phase_t0)
            if passed:
                self._on_phase_passed(state, start_time)
                # INTERVIEW done → pause for human to fill in answers
                if state.phase == Phase.HUMAN_PAUSE and not state.pause_reason:
                    doc_path = str(self.autopilot_dir / "requirements" / "INTERVIEW.md")
                    state.pause_reason = f"interview: please fill in {doc_path} then run `ap resume`"
                    self.save_state(state)
                    click.echo("\n" + "═" * 60)
                    click.echo("📋  需求澄清报告已生成！")
                    click.echo(f"    请打开并填写：{doc_path}")
                    click.echo("    填写完成后运行 `ap resume` 继续")
                    click.echo("═" * 60 + "\n")
                    if self._event_bus:
                        self._event_bus.emit(
                            "human_pause",
                            reason="interview",
                            doc_path=doc_path,
                        )
                    if self.notifier:
                        self.notifier.send_pause(
                            phase="INTERVIEW",
                            reason="请填写需求澄清报告后运行 ap resume",
                        )
            self.save_state(state)
            logger.info("Phase: %s | retries: %d", state.phase, state.phase_retries)

        elapsed = time.monotonic() - start_time
        if state.phase == Phase.DONE and self.notifier:
            count = sum(1 for _ in (self.autopilot_dir / "knowledge").rglob("*.md"))
            self.notifier.send_done(total_seconds=elapsed, knowledge_count=count)
        self._write_run_result(state)
        logger.info("Pipeline ended: %s (%.0fs)", state.phase, elapsed)

    def _handle_dev_loop(self, state: PipelineState) -> None:
        fl_path = self.autopilot_dir / "feature_list.json"
        if not fl_path.exists():
            state.phase = Phase.HUMAN_PAUSE
            state.pause_reason = "feature_list.json not found"
            self.save_state(state)
            return

        fl = FeatureList.load(fl_path)

        # Build runtime sets for DAG-aware scheduling
        completed_ids: set[str] = {f.id for f in fl.features if f.status == "completed"}
        pending_by_id: dict[str, Feature] = {f.id: f for f in fl.pending()}

        if not pending_by_id:
            state.phase = Phase.DOC_UPDATE
            self.save_state(state)
            return

        def is_ready(f: Feature) -> bool:
            """True when all deps are done or were never pending (completed before this run)."""
            return all(dep in completed_ids or dep not in pending_by_id for dep in f.depends_on)

        pool_backends = self._backend_pool()
        backend_cycle = itertools.cycle(enumerate(pool_backends))  # yields (idx, backend)
        backend_lock = threading.Lock()
        review_cfg = self._cfg.review

        # Track active workers for progress display
        active_workers: list[FeatureWorker] = []
        workers_lock = threading.Lock()

        def get_worker_status() -> list[tuple[str, str, str, str]]:
            with workers_lock:
                return [
                    (w.feature.id, w.current_phase.value, w.current_backend_name, w.feature.title)
                    for w in active_workers
                ]

        def next_backend() -> tuple[int, BackendBase]:
            with backend_lock:
                return next(backend_cycle)

        def resolve_review_backend(write_idx: int) -> BackendBase | None:
            """Return the review backend for a worker, or None to use self."""
            if review_cfg.mode == "cross":
                if len(pool_backends) <= 1:
                    return None  # fallback: self-review
                return pool_backends[(write_idx + 1) % len(pool_backends)]
            if review_cfg.mode == "backend" and review_cfg.backend_name:
                try:
                    return get_backend(
                        review_cfg.backend_name,
                        model=self._cfg.model,
                        allow_dangerous=self._cfg.allow_dangerous_permissions,
                    )
                except Exception:
                    return None  # fallback: self-review
            return None  # self mode

        start = time.monotonic()
        results: list[tuple[str, bool, list[str]]] = []

        # Live progress display
        progress = None
        _suppressed_handlers: list[logging.Handler] = []
        if sys.stdout.isatty():
            from autopilot.ui.dev_loop_progress import DevLoopProgress
            fl_done_init = sum(1 for f in fl.features if f.status == "completed")
            progress = DevLoopProgress(
                total=len(fl.features),
                get_worker_status=get_worker_status,
            )
            progress.update_done(fl_done_init)
            # Suppress terminal log handlers while Live display is active —
            # interleaved log lines break Rich's cursor positioning.
            root_log = logging.getLogger()
            _suppressed_handlers = [
                h for h in root_log.handlers
                if isinstance(h, logging.StreamHandler)
                and not isinstance(h, logging.FileHandler)
            ]
            for h in _suppressed_handlers:
                root_log.removeHandler(h)
            progress.start()

        # DAG-aware parallel scheduler: only submit features whose deps are all done.
        try:
            with ThreadPoolExecutor(max_workers=self._max_parallel) as pool:
                def run_worker(feature: Feature) -> tuple[str, bool, list[str]]:
                    write_idx, backend = next_backend()
                    review_backend = resolve_review_backend(write_idx)
                    logger.info(
                        "[%s] write=%s review=%s",
                        feature.id,
                        type(backend).__name__,
                        type(review_backend).__name__ if review_backend else "self",
                    )
                    worker = FeatureWorker(feature, backend, self.autopilot_dir, self.project_path, self._cfg, review_backend, recorder=self._recorder, event_bus=self._event_bus)
                    with workers_lock:
                        active_workers.append(worker)
                    try:
                        ok = worker.run()
                    finally:
                        with workers_lock:
                            active_workers.remove(worker)
                    return feature.id, ok, worker.artifacts

                # active_futures: future → feature_id; waiting: fid → feature (blocked by deps)
                active_futures: dict[Future[tuple[str, bool, list[str]]], str] = {}
                waiting: dict[str, Feature] = {}

                for fid, f in pending_by_id.items():
                    if is_ready(f):
                        active_futures[pool.submit(run_worker, f)] = fid
                    else:
                        waiting[fid] = f

                state.active_feature_ids = list(active_futures.values())
                self.save_state(state)

                while active_futures or waiting:
                    if not active_futures:
                        # Deadlock: nothing running, deps can never be satisfied
                        blocked = list(waiting)
                        logger.error(
                            "DAG deadlock: %d feature(s) still waiting with no active workers "
                            "(possible circular dependency or failed prerequisite): %s",
                            len(waiting), blocked,
                        )
                        for wfid in waiting:
                            for f in fl.features:
                                if f.id == wfid:
                                    f.status = "failed"
                                    break
                        fl.save(fl_path)
                        state.phase = Phase.HUMAN_PAUSE
                        state.pause_reason = (
                            f"DAG deadlock: {blocked} cannot be scheduled "
                            "(circular dependency or failed prerequisite)"
                        )
                        self.save_state(state)
                        break

                    done = next(as_completed(active_futures))
                    fid = active_futures.pop(done)
                    try:
                        _, ok, arts = done.result()
                    except Exception as exc:
                        logger.error("[%s] Worker raised unexpected exception: %s", fid, exc)
                        ok, arts = False, []

                    results.append((fid, ok, arts))
                    self._collected_artifacts.extend(arts)
                    # Always update feature status — leaving it "pending" on failure causes infinite re-runs
                    completed_feature: Feature | None = None
                    for f in fl.features:
                        if f.id == fid:
                            f.status = "completed" if ok else "failed"
                            if ok:
                                completed_feature = f
                            if self._event_bus:
                                self._event_bus.emit(
                                    "feature_update",
                                    feature_id=f.id,
                                    title=f.title,
                                    status=f.status,
                                    current_phase="",
                                    fix_retries=getattr(f, "fix_retries", 0),
                                    max_retries=self._cfg.max_fix_retries,
                                )
                            break
                    if ok:
                        completed_ids.add(fid)
                        if completed_feature is not None:
                            self._auto_commit_feature(completed_feature)
                    fl.save(fl_path)
                    done_count = sum(1 for f in fl.features if f.status == "completed")
                    self._update_progress_section(fl, done_count)
                    if progress:
                        progress.update_done(done_count)
                    if self.notifier and ok:
                        self.notifier.send_feature_done(
                            title=fid,
                            elapsed=time.monotonic() - start,
                            progress=(done_count, len(fl.features)),
                        )

                    # Unblock newly ready features
                    for wfid in list(waiting):
                        if is_ready(waiting[wfid]):
                            fut = pool.submit(run_worker, waiting.pop(wfid))
                            active_futures[fut] = wfid

                    state.active_feature_ids = list(active_futures.values())
                    self.save_state(state)
        finally:
            if progress:
                progress.stop()
            # Restore suppressed terminal log handlers
            root_log = logging.getLogger()
            for h in _suppressed_handlers:
                root_log.addHandler(h)

        state.active_feature_ids = []
        state.current_feature_id = None
        self.save_state(state)

    def _auto_commit_feature(self, feature: Feature) -> None:
        """Git-commit the working tree after a feature passes REVIEW."""
        if not self._cfg.auto_commit:
            return
        try:
            with self._git_lock:
                status = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True, text=True, cwd=self.project_path,
                )
                if not status.stdout.strip():
                    logger.debug("[%s] auto-commit: nothing to commit", feature.id)
                    return
                subprocess.run(
                    ["git", "add", "."],
                    capture_output=True, cwd=self.project_path, check=True,
                )
                msg = f"feat: [{feature.id}] {feature.title}"
                subprocess.run(
                    ["git", "commit", "-m", msg],
                    capture_output=True, cwd=self.project_path, check=True,
                )
                logger.info("[%s] auto-committed: %s", feature.id, msg)
                if self._event_bus:
                    self._event_bus.emit("auto_commit", feature_id=feature.id, message=msg)
        except Exception as exc:
            logger.warning("[%s] auto-commit failed (skipped): %s", feature.id, exc)

    def _backend_pool(self) -> list[BackendBase]:
        """Return the backend pool for round-robin worker assignment."""
        if self._parallel_backends:
            return self._parallel_backends
        return [self.backend]

    def _on_phase_passed(self, state: PipelineState, start_time: float) -> None:
        next_phase = self.advance(state)
        state.phase = next_phase
        state.phase_retries = 0

    def _update_progress_section(self, fl: FeatureList, done_count: int) -> None:
        """Write/replace the auto-maintained progress section in project-overview.md."""
        overview_path = self.autopilot_dir / "docs" / "00-overview" / "project-overview.md"
        if not overview_path.exists():
            return
        total = len(fl.features)
        lines = [
            "",
            "---",
            "",
            "## 自动化开发进度（实时更新）",
            "",
            f"**进度：{done_count} / {total} 功能已完成**",
            "",
            "| 功能 ID | 标题 | 状态 |",
            "|--------|------|------|",
        ]
        for feat in fl.features:
            status = "✅ 已完成" if feat.status == "completed" else "⏳ 待开发"
            lines.append(f"| {feat.id} | {feat.title} | {status} |")

        section = "\n".join(lines) + "\n"
        marker = "\n## 自动化开发进度（实时更新）"
        with self._overview_lock:
            content = overview_path.read_text(encoding="utf-8")
            if marker in content:
                content = content[: content.index(marker)] + section
            else:
                content = content.rstrip() + "\n" + section
            overview_path.write_text(content, encoding="utf-8")
