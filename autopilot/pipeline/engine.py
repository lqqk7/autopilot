from __future__ import annotations

import logging
from pathlib import Path

from autopilot.backends.base import BackendBase, RunContext
from autopilot.pipeline.context import AgentOutput, Feature, FeatureList, Phase, PipelineState
from autopilot.pipeline.phases import ExitCondition, PhaseRunner
from autopilot.utils.toposort import topological_sort

logger = logging.getLogger(__name__)

MAX_FIX_RETRIES = 5
MAX_PHASE_RETRIES = 3


class PipelineEngine:
    def __init__(self, project_path: Path, backend: BackendBase) -> None:
        self.project_path = project_path
        self.autopilot_dir = project_path / ".autopilot"
        self.backend = backend
        self.phase_runner = PhaseRunner()
        self.exit_condition = ExitCondition()

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

    def check_pause(self, state: PipelineState) -> bool:
        """Return True if the pipeline should pause for human intervention."""
        if state.phase_retries >= MAX_FIX_RETRIES:
            return True
        return False

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
        state = self.load_state()
        logger.info("Starting pipeline at phase: %s", state.phase)

        while state.phase not in (Phase.DONE, Phase.HUMAN_PAUSE):
            if self.check_pause(state):
                state.phase = Phase.HUMAN_PAUSE
                state.pause_reason = f"Max retries ({MAX_FIX_RETRIES}) exceeded at {state.phase}"
                self.save_state(state)
                logger.warning("HUMAN_PAUSE: %s", state.pause_reason)
                break

            next_phase = self.advance(state)
            state.phase = next_phase
            self.save_state(state)
            logger.info("→ Phase: %s", state.phase)

        logger.info("Pipeline ended at: %s", state.phase)
