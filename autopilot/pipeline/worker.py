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
from autopilot.pipeline.context import AgentOutput, Feature, FeatureList, Phase
from autopilot.pipeline.phases import ExitCondition
from autopilot.pipeline.retry import LOCAL_RETRY_TYPES, handle_error

logger = logging.getLogger(__name__)

MAX_FIX_RETRIES = 5

_FEATURE_PHASES = (Phase.CODE, Phase.TEST, Phase.REVIEW, Phase.FIX)

_PHASE_TIMEOUT: dict[Phase, int] = {
    Phase.CODE: 1800,
    Phase.TEST: 900,
    Phase.REVIEW: 600,
    Phase.FIX: 900,
}

_PHASE_TO_AGENT: dict[Phase, str] = {
    Phase.CODE: "coder",
    Phase.TEST: "tester",
    Phase.REVIEW: "reviewer",
    Phase.FIX: "fixer",
}

_TRANSITIONS: dict[tuple[Phase, bool], Phase] = {
    (Phase.CODE, True): Phase.TEST,
    (Phase.TEST, True): Phase.REVIEW,
    (Phase.TEST, False): Phase.FIX,
    (Phase.REVIEW, True): Phase.DEV_LOOP,   # DEV_LOOP signals completion
    (Phase.REVIEW, False): Phase.FIX,
    (Phase.FIX, True): Phase.CODE,
    (Phase.FIX, False): Phase.CODE,
}

# Lock for writing to shared files (feature_list.json, project-overview.md)
_file_lock = threading.Lock()


class FeatureWorker:
    """Runs CODE→TEST→REVIEW→FIX for one feature. Thread-safe."""

    def __init__(
        self,
        feature: Feature,
        backend: BackendBase,
        autopilot_dir: Path,
        project_path: Path,
    ) -> None:
        self.feature = feature
        self.backend = backend
        self.autopilot_dir = autopilot_dir
        self.project_path = project_path
        self._loader = AgentLoader()
        self._compactor = KnowledgeCompactor()
        self.artifacts: list[str] = []
        self.fix_retries = 0

    def run(self) -> bool:
        """Execute the full feature cycle. Returns True on success."""
        phase = Phase.CODE
        phase_retries = 0

        while True:
            passed = self._run_single_phase(phase)

            next_phase = _TRANSITIONS.get((phase, passed))
            if next_phase is None:
                logger.error("[%s] No transition for (%s, passed=%s)", self.feature.id, phase, passed)
                return False

            if next_phase == Phase.DEV_LOOP:
                logger.info("[%s] Feature complete", self.feature.id)
                return True

            if next_phase == Phase.FIX:
                self.fix_retries += 1
                if self.fix_retries > MAX_FIX_RETRIES:
                    logger.warning("[%s] Max fix retries exceeded", self.feature.id)
                    return False

            phase = next_phase
            phase_retries = 0 if passed else phase_retries + 1

    def _run_single_phase(self, phase: Phase) -> bool:
        kb = LocalKnowledge(self.autopilot_dir / "knowledge")
        knowledge_md = kb.read_all()
        if self._compactor.needs_compaction(knowledge_md):
            knowledge_md = self._compactor.compact(knowledge_md, self.backend, self.autopilot_dir)

        ctx = RunContext(
            project_path=self.project_path,
            docs_path=self.autopilot_dir / "docs",
            feature=self.feature,
            knowledge_md=knowledge_md,
        )
        agent_name = _PHASE_TO_AGENT[phase]
        prompt = self._loader.build_system_prompt(agent_name, ctx)
        timeout = _PHASE_TIMEOUT.get(phase, 300)
        local_retry = 0

        logger.info("[%s] Starting phase %s", self.feature.id, phase.value)

        while True:
            result = self.backend.run(agent_name, prompt, ctx, timeout=timeout)

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
                knowledge_md = self._compactor.compact(knowledge_md, self.backend, self.autopilot_dir)
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
