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

    def run_phase(self, state: PipelineState) -> bool:
        """Execute the current phase via the backend. Returns True if phase exit condition is met."""
        from autopilot.agents.loader import AgentLoader
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

        phase_to_agent: dict[Phase, str] = {
            Phase.DOC_GEN: "doc_gen",
            Phase.PLANNING: "planner",
            Phase.CODE: "coder",
            Phase.TEST: "tester",
            Phase.REVIEW: "reviewer",
            Phase.FIX: "fixer",
            Phase.DOC_UPDATE: "doc_gen",
            Phase.KNOWLEDGE: "doc_gen",
        }

        agent_name = phase_to_agent.get(state.phase)
        if not agent_name:
            return True

        prompt = loader.build_system_prompt(agent_name, ctx)
        result = self.backend.run(agent_name, prompt, ctx)

        if not result.success:
            state.phase_retries += 1
            return False

        try:
            AgentOutput.parse(result.output)
            state.phase_retries = 0
            return True
        except ValueError:
            state.phase_retries += 1
            return False

    def run(self) -> None:
        """Main pipeline loop."""
        import time
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
        start_time = time.monotonic()

        while state.phase not in (Phase.DONE, Phase.HUMAN_PAUSE):
            if self.check_pause(state):
                state.phase = Phase.HUMAN_PAUSE
                state.pause_reason = f"Max retries exceeded at {state.phase.value}"
                self.save_state(state)
                logger.warning("HUMAN_PAUSE: %s", state.pause_reason)
                break

            if state.phase == Phase.DEV_LOOP:
                fl_path = self.autopilot_dir / "feature_list.json"
                if not fl_path.exists():
                    state.phase = Phase.HUMAN_PAUSE
                    state.pause_reason = "feature_list.json not found"
                    self.save_state(state)
                    break

                fl = FeatureList.load(fl_path)
                ordered = topological_sort(fl.pending())

                if not ordered:
                    state.phase = Phase.DOC_UPDATE
                    self.save_state(state)
                    continue

                state.current_feature_id = ordered[0].id
                state.phase = Phase.CODE
                self.save_state(state)
                continue

            passed = self.run_phase(state)

            if passed:
                next_phase = self.advance(state)
                state.phase = next_phase
                state.phase_retries = 0

                if next_phase == Phase.DEV_LOOP and state.current_feature_id:
                    fl = FeatureList.load(self.autopilot_dir / "feature_list.json")
                    for f in fl.features:
                        if f.id == state.current_feature_id:
                            f.status = "completed"
                    fl.save(self.autopilot_dir / "feature_list.json")
                    state.current_feature_id = None

            self.save_state(state)
            logger.info("Phase: %s | retries: %d", state.phase, state.phase_retries)

        elapsed = time.monotonic() - start_time
        logger.info("Pipeline ended: %s (%.0fs)", state.phase, elapsed)
