from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from autopilot.backends.base import BackendBase, BackendResult, ErrorType, RunContext
from autopilot.notifications.telegram import TelegramNotifier
from autopilot.pipeline.context import AgentOutput, FeatureList, Phase, PipelineState, RunResult
from autopilot.pipeline.phases import ExitCondition, PhaseRunner
from autopilot.pipeline.retry import LOCAL_RETRY_TYPES, exponential_backoff, handle_error
from autopilot.utils.toposort import topological_sort

logger = logging.getLogger(__name__)

MAX_FIX_RETRIES = 5
MAX_PHASE_RETRIES = 3

# Per-phase backend timeout (seconds). Heavy phases need more time.
_PHASE_TIMEOUT: dict[Phase, int] = {
    Phase.DOC_GEN: 900,      # 15 min: generates 12+ docs
    Phase.DOC_UPDATE: 600,   # 10 min: updates multiple docs
    Phase.PLANNING: 600,     # 10 min: feature decomposition can be complex
}
_DEFAULT_TIMEOUT = 300       # 5 min for CODE/TEST/REVIEW/FIX/KNOWLEDGE

_PHASE_TO_AGENT: dict[Phase, str] = {
    Phase.DOC_GEN: "doc_gen",
    Phase.PLANNING: "planner",
    Phase.CODE: "coder",
    Phase.TEST: "tester",
    Phase.REVIEW: "reviewer",
    Phase.FIX: "fixer",
    Phase.DOC_UPDATE: "doc_gen",
    Phase.KNOWLEDGE: "doc_gen",
}


class PipelineEngine:
    def __init__(self, project_path: Path, backend: BackendBase) -> None:
        self.project_path = project_path
        self.autopilot_dir = project_path / ".autopilot"
        self.backend = backend
        self.phase_runner = PhaseRunner()
        self.exit_condition = ExitCondition()
        token = os.environ.get("AUTOPILOT_TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("AUTOPILOT_TELEGRAM_CHAT_ID", "")
        self.notifier = TelegramNotifier(token=token, chat_id=chat_id) if token else None
        self._run_start: float = 0.0
        self._collected_artifacts: list[str] = []
        self._knowledge_count: int = 0
        self._compaction_count: int = 0
        self._backend_name: str = type(backend).__name__.lower().replace("backend", "")
        self._fallback_backends: list[BackendBase] = self._load_fallback_backends()
        self._fallback_index: int = -1   # -1 = primary, 0+ = fallback
        self._backend_switches: int = 0

    def state_path(self) -> Path:
        return self.autopilot_dir / "state.json"

    def load_state(self) -> PipelineState:
        return PipelineState.load(self.state_path())

    def save_state(self, state: PipelineState) -> None:
        state.save(self.state_path())

    def advance(self, state: PipelineState) -> Phase:
        """Determine the next phase based on current state (no AI involved)."""
        if state.phase == Phase.INIT:
            return Phase.DOC_GEN
        if state.phase == Phase.DOC_GEN:
            docs = self.autopilot_dir / "docs"
            return Phase.PLANNING if self.exit_condition.doc_gen_complete(docs) else Phase.DOC_GEN
        if state.phase == Phase.PLANNING:
            fl_path = self.autopilot_dir / "feature_list.json"
            return Phase.DEV_LOOP if self.exit_condition.planning_complete(fl_path) else Phase.PLANNING
        return self.phase_runner.next_phase(state.phase, passed=True)

    def _load_fallback_backends(self) -> list[BackendBase]:
        config_path = self.autopilot_dir / "config.toml"
        if not config_path.exists():
            return []
        try:
            import toml
            from autopilot.backends import get_backend
            config = toml.loads(config_path.read_text())
            names = config.get("autopilot", {}).get("fallback_backends", [])
            return [get_backend(n) for n in names if n]
        except Exception:
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
        return True

    def check_pause(self, state: PipelineState) -> bool:
        """Return True if the pipeline should pause for human intervention."""
        return state.phase_retries >= MAX_FIX_RETRIES

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
        import sys

        from autopilot.agents.loader import AgentLoader
        from autopilot.knowledge.compactor import KnowledgeCompactor
        from autopilot.knowledge.local import LocalKnowledge

        kb = LocalKnowledge(self.autopilot_dir / "knowledge")
        loader = AgentLoader()

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

        compactor = KnowledgeCompactor()
        if compactor.needs_compaction(ctx.knowledge_md):
            ctx = self._rebuild_ctx(ctx, compactor.compact(ctx.knowledge_md, self.backend, self.autopilot_dir))
            self._compaction_count += 1

        prompt = loader.build_system_prompt(agent_name, ctx)
        local_retry = 0

        phase_timeout = _PHASE_TIMEOUT.get(state.phase, _DEFAULT_TIMEOUT)

        # Live progress — only in interactive terminals, not in tests/pipes
        progress = None
        if sys.stdout.isatty():
            from autopilot.ui.progress import PhaseProgress
            docs_path = ctx.docs_path if state.phase == Phase.DOC_GEN else None
            progress = PhaseProgress(state.phase.value, docs_path=docs_path)
            progress.start()

        try:
            while True:
                result = self.backend.run(agent_name, prompt, ctx, timeout=phase_timeout)

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
                    ctx = self._rebuild_ctx(ctx, compactor.compact(ctx.knowledge_md, self.backend, self.autopilot_dir))
                    prompt = loader.build_system_prompt(agent_name, ctx)
                    self._compaction_count += 1
                    local_retry = 0
                    continue

                # v0.4: fallback backend on rate_limit / quota_exhausted
                if result.error_type in (ErrorType.rate_limit, ErrorType.quota_exhausted):
                    if self._try_switch_backend(result.error_type):
                        local_retry = 0
                        continue

                # File-based fallback for DOC_GEN: files exist despite timeout/parse error
                if state.phase == Phase.DOC_GEN and self.exit_condition.doc_gen_complete(ctx.docs_path):
                    logger.info("DOC_GEN file-based fallback: all required docs present")
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
            # parse failed terminally — check file-based fallback for DOC_GEN
            if state.phase == Phase.DOC_GEN and self.exit_condition.doc_gen_complete(
                self.autopilot_dir / "docs"
            ):
                logger.info("DOC_GEN parse-error fallback: required docs present")
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
            knowledge_count=self._knowledge_count,
            compactions=self._compaction_count,
        )
        result.save(self.autopilot_dir / "run_result.json")

    def run(self) -> None:
        """Main pipeline loop."""
        logging.basicConfig(
            level=logging.INFO,
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

        while state.phase not in (Phase.DONE, Phase.HUMAN_PAUSE):
            if self.check_pause(state):
                state.phase = Phase.HUMAN_PAUSE
                state.pause_reason = f"Max retries exceeded at {state.phase.value}"
                self.save_state(state)
                logger.warning("HUMAN_PAUSE: %s", state.pause_reason)
                if self.notifier:
                    self.notifier.send_pause(phase=state.phase.value, reason=state.pause_reason or "")
                break

            if state.phase == Phase.DEV_LOOP:
                self._handle_dev_loop(state)
                continue

            passed = self.run_phase(state)
            if passed:
                self._on_phase_passed(state, start_time)
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
        ordered = topological_sort(fl.pending())
        if not ordered:
            state.phase = Phase.DOC_UPDATE
        else:
            state.current_feature_id = ordered[0].id
            state.phase = Phase.CODE
        self.save_state(state)

    def _on_phase_passed(self, state: PipelineState, start_time: float) -> None:
        next_phase = self.advance(state)
        state.phase = next_phase
        state.phase_retries = 0
        if next_phase == Phase.DEV_LOOP and state.current_feature_id:
            self._complete_feature(state, start_time)

    def _complete_feature(self, state: PipelineState, start_time: float) -> None:
        fl = FeatureList.load(self.autopilot_dir / "feature_list.json")
        for f in fl.features:
            if f.id == state.current_feature_id:
                f.status = "completed"
        fl.save(self.autopilot_dir / "feature_list.json")
        if self.notifier:
            fl_updated = FeatureList.load(self.autopilot_dir / "feature_list.json")
            done_count = sum(1 for feat in fl_updated.features if feat.status == "completed")
            self.notifier.send_feature_done(
                title=state.current_feature_id or "",
                elapsed=time.monotonic() - start_time,
                progress=(done_count, len(fl_updated.features)),
            )
        state.current_feature_id = None
