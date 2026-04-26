"""Tests for v0.4 Mission / FeatureState / MissionStore."""
from __future__ import annotations

from pathlib import Path

import pytest

from autopilot.pipeline.context import (
    FeatureState,
    Mission,
    MissionStore,
    Phase,
    PipelineState,
)


@pytest.fixture()
def store(tmp_path: Path) -> MissionStore:
    return MissionStore(tmp_path / ".autopilot")


def test_get_or_create_mission_creates_new(store: MissionStore) -> None:
    m = store.get_or_create_mission("Test Mission")
    assert m.status == "active"
    assert m.title == "Test Mission"
    assert m.id.startswith("mission-")


def test_get_or_create_mission_returns_existing(store: MissionStore) -> None:
    m1 = store.get_or_create_mission("First")
    m2 = store.get_or_create_mission("Second")
    assert m1.id == m2.id


def test_active_mission_id_none_when_empty(store: MissionStore) -> None:
    assert store.active_mission_id() is None


def test_active_mission_id_returns_active(store: MissionStore) -> None:
    m = store.get_or_create_mission("My Mission")
    assert store.active_mission_id() == m.id


def test_feature_state_roundtrip(store: MissionStore) -> None:
    m = store.get_or_create_mission("Mission")
    fs = store.mark_feature_started(m.id, "feat-001", depends_on=["feat-000"])
    assert fs.status == "in_progress"
    assert fs.started_at is not None

    loaded = store.load_feature_state(m.id, "feat-001")
    assert loaded is not None
    assert loaded.status == "in_progress"


def test_mark_feature_done_success(store: MissionStore) -> None:
    m = store.get_or_create_mission("Mission")
    store.mark_feature_started(m.id, "feat-001", depends_on=[])
    fs = store.mark_feature_done(m.id, "feat-001", success=True, last_backend="claude", retry_count=2)
    assert fs.status == "completed"
    assert fs.last_backend == "claude"
    assert fs.retry_count == 2
    assert fs.completed_at is not None


def test_mark_feature_done_failure(store: MissionStore) -> None:
    m = store.get_or_create_mission("Mission")
    fs = store.mark_feature_done(m.id, "feat-002", success=False)
    assert fs.status == "failed"


def test_save_checkpoint(store: MissionStore) -> None:
    m = store.get_or_create_mission("Mission")
    pipeline_state = PipelineState(phase=Phase.DEV_LOOP)
    feature_states = {
        "feat-001": FeatureState(id="feat-001", mission_id=m.id, status="completed"),
    }
    store.save_checkpoint(pipeline_state, feature_states)
    checkpoint_dir = store._checkpoint_dir(m.id)
    checkpoints = list(checkpoint_dir.glob("*.json"))
    assert len(checkpoints) == 1


def test_complete_mission(store: MissionStore) -> None:
    m = store.get_or_create_mission("Mission")
    store.complete_mission(m.id)
    loaded = Mission.load(store._mission_dir(m.id) / "mission.json")
    assert loaded.status == "done"
    assert store.active_mission_id() is None


def test_load_feature_state_nonexistent(store: MissionStore) -> None:
    m = store.get_or_create_mission("M")
    assert store.load_feature_state(m.id, "nonexistent") is None


def test_mission_persisted_to_disk(store: MissionStore) -> None:
    m = store.get_or_create_mission("Disk Test")
    path = store._mission_dir(m.id) / "mission.json"
    assert path.exists()
    loaded = Mission.load(path)
    assert loaded.id == m.id
    assert loaded.title == "Disk Test"
