import pytest
from pathlib import Path
from autopilot.init_project import init_project


def test_init_creates_directory_structure(tmp_path: Path):
    init_project(project_path=tmp_path, backend="claude")
    assert (tmp_path / ".autopilot" / "input").exists()
    assert (tmp_path / ".autopilot" / "docs").exists()
    assert (tmp_path / ".autopilot" / "knowledge" / "bugs").exists()
    assert (tmp_path / ".autopilot" / "knowledge" / "decisions").exists()


def test_init_creates_config(tmp_path: Path):
    init_project(project_path=tmp_path, backend="codex")
    config_path = tmp_path / ".autopilot" / "config.toml"
    assert config_path.exists()
    import toml
    config = toml.loads(config_path.read_text())
    assert config["autopilot"]["backend"] == "codex"


def test_init_creates_state(tmp_path: Path):
    init_project(project_path=tmp_path, backend="claude")
    from autopilot.pipeline.context import PipelineState, Phase
    state = PipelineState.load(tmp_path / ".autopilot" / "state.json")
    assert state.phase == Phase.INIT


def test_init_idempotent(tmp_path: Path):
    init_project(project_path=tmp_path, backend="claude")
    init_project(project_path=tmp_path, backend="claude")
    # Should not raise, directories already exist
