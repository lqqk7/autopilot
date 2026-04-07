import pytest
from pathlib import Path
from unittest.mock import MagicMock
from autopilot.pipeline.context import Phase, PipelineState, Feature, FeatureList
from autopilot.pipeline.engine import PipelineEngine
from autopilot.backends.base import BackendResult, RunContext


@pytest.fixture
def engine(tmp_path: Path) -> PipelineEngine:
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "requirements").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()
    (autopilot_dir / "knowledge" / "bugs").mkdir(parents=True)
    (autopilot_dir / "knowledge" / "decisions").mkdir()
    mock_backend = MagicMock()
    mock_backend.run.return_value = BackendResult(
        success=True,
        output='```json autopilot-result\n{"status":"success","summary":"done","artifacts":[],"issues":[],"next_hint":null}\n```',
        duration_seconds=1.0,
    )
    return PipelineEngine(project_path=tmp_path, backend=mock_backend)


def test_engine_initial_state(engine: PipelineEngine):
    state = engine.load_state()
    assert state.phase == Phase.INIT


def test_engine_transitions_to_doc_gen(engine: PipelineEngine, tmp_path: Path):
    # Seed requirements
    (tmp_path / ".autopilot" / "requirements" / "requirements.md").write_text("Build a todo app")
    state = engine.load_state()
    state.phase = Phase.INIT
    engine.save_state(state)
    next_phase = engine.advance(state)
    assert next_phase == Phase.DOC_GEN


def test_engine_human_pause_on_max_retries(engine: PipelineEngine, tmp_path: Path):
    state = PipelineState(phase=Phase.FIX, phase_retries=5)
    result = engine.check_pause(state)
    assert result is True
