from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopilot.pipeline.context import RunResult


# ─── RunResult 数据结构 ────────────────────────────────────────────────────────

def test_run_result_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "run_result.json"
    rr = RunResult(
        status="done",
        phase="DONE",
        elapsed_seconds=120.5,
        features_total=5,
        features_done=5,
        artifacts=["src/foo.py", "tests/test_foo.py"],
        pause_reason=None,
        backend_used="claude",
        backend_switches=0,
        knowledge_count=2,
        compactions=0,
    )
    rr.save(path)
    loaded = RunResult.load(path)
    assert loaded.status == "done"
    assert loaded.phase == "DONE"
    assert loaded.elapsed_seconds == 120.5
    assert loaded.features_total == 5
    assert loaded.features_done == 5
    assert loaded.artifacts == ["src/foo.py", "tests/test_foo.py"]
    assert loaded.pause_reason is None
    assert loaded.backend_used == "claude"
    assert loaded.knowledge_count == 2


def test_run_result_save_produces_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "run_result.json"
    RunResult(status="paused", phase="CODE", elapsed_seconds=30.0,
              features_total=3, features_done=1, pause_reason="max retries").save(path)
    data = json.loads(path.read_text())
    assert data["status"] == "paused"
    assert data["pause_reason"] == "max retries"


def test_run_result_timestamp_auto_filled() -> None:
    rr = RunResult(status="done", phase="DONE", elapsed_seconds=0,
                   features_total=0, features_done=0)
    assert rr.timestamp != ""
    assert "T" in rr.timestamp  # ISO 8601 format


def test_run_result_timestamp_not_overwritten_if_provided() -> None:
    ts = "2026-01-01T00:00:00Z"
    rr = RunResult(status="done", phase="DONE", elapsed_seconds=0,
                   features_total=0, features_done=0, timestamp=ts)
    assert rr.timestamp == ts


# ─── Engine 写出 run_result.json ──────────────────────────────────────────────

def _make_autopilot_dir(tmp_path: Path) -> Path:
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "requirements").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()
    (autopilot_dir / "knowledge" / "bugs").mkdir(parents=True)
    (autopilot_dir / "knowledge" / "decisions").mkdir()
    (tmp_path / "logs").mkdir()
    return autopilot_dir


def test_engine_writes_run_result_on_done(tmp_path: Path) -> None:
    from autopilot.backends.base import BackendBase, BackendResult, RunContext
    from autopilot.pipeline.context import Phase, PipelineState
    from autopilot.pipeline.engine import PipelineEngine

    autopilot_dir = _make_autopilot_dir(tmp_path)

    # Seed state at DONE so the loop exits immediately
    state = PipelineState(phase=Phase.DONE)
    state.save(autopilot_dir / "state.json")

    mock_backend = MagicMock(spec=BackendBase)
    engine = PipelineEngine(project_path=tmp_path, backend=mock_backend)

    engine.run()

    result_path = autopilot_dir / "run_result.json"
    assert result_path.exists()
    data = json.loads(result_path.read_text())
    assert data["status"] == "done"
    assert data["phase"] == "DONE"


def test_engine_writes_run_result_on_human_pause(tmp_path: Path) -> None:
    from autopilot.backends.base import BackendBase, BackendResult, RunContext
    from autopilot.pipeline.context import Phase, PipelineState
    from autopilot.pipeline.config import PipelineConfig
    from autopilot.pipeline.engine import PipelineEngine

    autopilot_dir = _make_autopilot_dir(tmp_path)

    # Seed state with retries maxed → check_pause() triggers when phase_retries >= max_phase_retries
    state = PipelineState(phase=Phase.DOC_GEN, phase_retries=PipelineConfig().max_phase_retries)
    state.save(autopilot_dir / "state.json")

    mock_backend = MagicMock(spec=BackendBase)
    engine = PipelineEngine(project_path=tmp_path, backend=mock_backend)

    engine.run()

    result_path = autopilot_dir / "run_result.json"
    assert result_path.exists()
    data = json.loads(result_path.read_text())
    assert data["status"] == "paused"
    assert data["pause_reason"] is not None
