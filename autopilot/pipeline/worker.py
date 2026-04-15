"""FeatureWorker: runs the full CODE→TEST→REVIEW→FIX cycle for a single feature."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from autopilot.agents.loader import AgentLoader
from autopilot.backends.base import BackendBase, BackendResult, ErrorType, RunContext
from autopilot.knowledge.compactor import KnowledgeCompactor
from autopilot.knowledge.local import LocalKnowledge
from autopilot.pipeline.config import PipelineConfig
from autopilot.pipeline.context import AgentOutput, Feature, Phase
from autopilot.pipeline.retry import LOCAL_RETRY_TYPES, handle_error
from autopilot.sessions.recorder import SessionRecorder
from autopilot.tui.event_bus import EventBus

logger = logging.getLogger(__name__)

_FEATURE_PHASES = (Phase.CODE, Phase.TEST, Phase.REVIEW, Phase.FIX)

_PHASE_TO_AGENT: dict[Phase, str] = {
    Phase.CODE: "coder",
    Phase.TEST: "tester",
    Phase.REVIEW: "reviewer",
    Phase.FIX: "fixer",
}

_TRANSITIONS: dict[tuple[Phase, bool], Phase] = {
    (Phase.CODE, True): Phase.TEST,
    (Phase.CODE, False): Phase.FIX,
    (Phase.TEST, True): Phase.REVIEW,
    (Phase.TEST, False): Phase.FIX,
    (Phase.REVIEW, True): Phase.DEV_LOOP,
    (Phase.REVIEW, False): Phase.FIX,
    (Phase.FIX, True): Phase.CODE,
    (Phase.FIX, False): Phase.CODE,
}

_file_lock = threading.Lock()


def _backend_name(backend: BackendBase) -> str:
    return type(backend).__name__.lower().replace("backend", "")


class FeatureWorker:
    """Runs CODE→TEST→REVIEW→FIX for one feature. Thread-safe."""

    def __init__(
        self,
        feature: Feature,
        backend: BackendBase,
        autopilot_dir: Path,
        project_path: Path,
        config: PipelineConfig | None = None,
        review_backend: BackendBase | None = None,
        recorder: SessionRecorder | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.feature = feature
        self.backend = backend
        self.autopilot_dir = autopilot_dir
        self.project_path = project_path
        self._cfg = config or PipelineConfig()
        # None = use self.backend for review (self / fallback)
        self._review_backend = review_backend
        self._recorder = recorder
        self._event_bus: EventBus | None = event_bus
        self._loader = AgentLoader()
        self._compactor = KnowledgeCompactor()
        self.artifacts: list[str] = []
        self.fix_retries = 0
        self.current_phase: Phase = Phase.CODE
        self.backend_name: str = _backend_name(backend)
        self.current_backend_name: str = self.backend_name

    def run(self) -> bool:
        """Execute the full feature cycle. Returns True on success."""
        _feature_start = time.monotonic()
        phase = Phase.CODE
        success = False

        while True:
            passed = self._run_single_phase(phase)

            next_phase = _TRANSITIONS.get((phase, passed))
            if next_phase is None:
                logger.error("[%s] No transition for (%s, passed=%s)", self.feature.id, phase, passed)
                break

            if next_phase == Phase.DEV_LOOP:
                logger.info("[%s] Feature complete", self.feature.id)
                success = True
                break

            if next_phase == Phase.FIX:
                self.fix_retries += 1
                if self.fix_retries > self._cfg.max_fix_retries:
                    logger.warning("[%s] Max fix retries exceeded", self.feature.id)
                    break

            phase = next_phase

        if self._recorder:
            self._recorder.feature_done(
                feature_id=self.feature.id,
                title=self.feature.title,
                success=success,
                duration_s=time.monotonic() - _feature_start,
                fix_retries=self.fix_retries,
            )
        return success

    def _active_backend(self, phase: Phase) -> BackendBase:
        """Return the backend to use for this phase."""
        if phase == Phase.REVIEW and self._review_backend is not None:
            return self._review_backend
        return self.backend

    def _run_single_phase(self, phase: Phase) -> bool:
        self.current_phase = phase
        active = self._active_backend(phase)
        self.current_backend_name = _backend_name(active)
        if self._event_bus:
            self._event_bus.emit(
                "feature_update",
                feature_id=self.feature.id,
                title=self.feature.title,
                status="active",
                current_phase=phase.value,
                backend=self.current_backend_name,
                fix_retries=self.fix_retries,
                max_retries=self._cfg.max_fix_retries,
            )

        kb = LocalKnowledge(self.autopilot_dir / "knowledge")
        knowledge_md = kb.read_all()
        if self._compactor.needs_compaction(knowledge_md):
            knowledge_md = self._compactor.compact(knowledge_md, active, self.autopilot_dir)

        ctx = RunContext(
            project_path=self.project_path,
            docs_path=self.autopilot_dir / "docs",
            feature=self.feature,
            knowledge_md=knowledge_md,
        )
        agent_name = _PHASE_TO_AGENT[phase]
        prompt = self._loader.build_system_prompt(agent_name, ctx)
        timeout = self._cfg.timeout_for(phase)
        local_retry = 0

        logger.info("[%s] Starting phase %s (backend: %s)", self.feature.id, phase.value, self.current_backend_name)

        while True:
            result = active.run(agent_name, prompt, ctx, timeout=timeout)

            if self._recorder:
                self._recorder.agent_call(
                    phase=phase.value,
                    agent_name=agent_name,
                    backend_name=self.current_backend_name,
                    result=result,
                    feature_id=self.feature.id,
                    local_retry=local_retry,
                    prompt=prompt,
                )

            if result.success:
                parsed = self._parse_output(result, local_retry)
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
                knowledge_md = self._compactor.compact(knowledge_md, active, self.autopilot_dir)
                ctx = RunContext(
                    project_path=self.project_path,
                    docs_path=self.autopilot_dir / "docs",
                    feature=self.feature,
                    knowledge_md=knowledge_md,
                )
                prompt = self._loader.build_system_prompt(agent_name, ctx)
                local_retry = 0
                continue

            logger.warning("[%s] Phase %s failed: %s", self.feature.id, phase.value, result.error)
            return False

    def _parse_output(self, result: BackendResult, local_retry: int) -> bool | None:
        try:
            agent_output = AgentOutput.parse(result.output)
            self.artifacts.extend(agent_output.artifacts)
            if agent_output.status != "success":
                logger.info(
                    "[%s] Agent reported status=%r: %s",
                    self.feature.id,
                    agent_output.status,
                    agent_output.summary[:200],
                )
                return False  # failure / partial → FIX via _TRANSITIONS
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
                return None
            return False
