import pytest
from pathlib import Path


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with .autopilot/ structure."""
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "input").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()
    (autopilot_dir / "knowledge" / "bugs").mkdir(parents=True)
    (autopilot_dir / "knowledge" / "decisions").mkdir()
    return tmp_path
