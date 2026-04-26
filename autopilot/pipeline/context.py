from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Phase(str, Enum):
    INIT = "INIT"
    INTERVIEW = "INTERVIEW"
    DOC_GEN = "DOC_GEN"
    PLANNING = "PLANNING"
    DEV_LOOP = "DEV_LOOP"
    CODE = "CODE"
    TEST = "TEST"
    REVIEW = "REVIEW"
    FIX = "FIX"
    DOC_UPDATE = "DOC_UPDATE"
    KNOWLEDGE = "KNOWLEDGE"
    DELIVERY = "DELIVERY"
    DONE = "DONE"
    HUMAN_PAUSE = "HUMAN_PAUSE"


class Feature(BaseModel):
    id: str
    title: str
    phase: str
    depends_on: list[str] = Field(default_factory=list)
    status: str = "pending"
    test_file: str | None = None
    fix_retries: int = 0


class FeatureList(BaseModel):
    features: list[Feature]

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "FeatureList":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def pending(self) -> list[Feature]:
        return [f for f in self.features if f.status == "pending"]

    def all_done(self) -> bool:
        return all(f.status == "completed" for f in self.features)


class PipelineState(BaseModel):
    phase: Phase = Phase.INIT
    current_feature_id: str | None = None      # serial mode compat
    active_feature_ids: list[str] = Field(default_factory=list)  # parallel mode
    phase_retries: int = 0
    pause_reason: str | None = None
    post_interview_phase: Phase | None = None   # where to go after INTERVIEW pause

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PipelineState":
        if not path.exists():
            return cls()
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


@dataclass
class RunResult:
    status: str                          # "done" | "paused" | "error"
    phase: str
    elapsed_seconds: float
    features_total: int
    features_done: int
    artifacts: list[str] = field(default_factory=list)
    pause_reason: str | None = None
    backend_used: str = ""
    backend_switches: int = 0
    knowledge_count: int = 0
    compactions: int = 0
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def save(self, path: Path) -> None:
        import dataclasses
        path.write_text(json.dumps(dataclasses.asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "RunResult":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)


# ── v0.4: Mission / FeatureState / Checkpoint / MissionStore ─────────────────


class Mission(BaseModel):
    id: str
    title: str
    description: str = ""
    created_at: str
    status: str = "active"   # draft | active | paused | done

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Mission":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class FeatureState(BaseModel):
    id: str
    mission_id: str
    phase: str = "CODE"
    status: str = "pending"  # pending | in_progress | completed | failed
    depends_on: list[str] = Field(default_factory=list)
    retry_count: int = 0
    last_backend: str | None = None
    last_output: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "FeatureState":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class Checkpoint(BaseModel):
    timestamp: str
    mission_id: str
    pipeline_state: PipelineState
    feature_states: dict[str, FeatureState]

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")


class MissionStore:
    """Manages per-mission directories and per-feature state files under .autopilot/missions/."""

    def __init__(self, autopilot_dir: Path) -> None:
        self.missions_dir = autopilot_dir / "missions"

    def _mission_dir(self, mission_id: str) -> Path:
        return self.missions_dir / mission_id

    def _feature_path(self, mission_id: str, feature_id: str) -> Path:
        return self._mission_dir(mission_id) / "features" / f"{feature_id}.json"

    def _checkpoint_dir(self, mission_id: str) -> Path:
        return self._mission_dir(mission_id) / "checkpoints"

    def active_mission_id(self) -> str | None:
        """Return the ID of the first active mission, or None."""
        if not self.missions_dir.exists():
            return None
        for entry in sorted(self.missions_dir.iterdir()):
            mission_path = entry / "mission.json"
            if mission_path.exists():
                try:
                    m = Mission.load(mission_path)
                    if m.status == "active":
                        return m.id
                except Exception:
                    pass
        return None

    def get_or_create_mission(self, title: str, description: str = "") -> Mission:
        existing_id = self.active_mission_id()
        if existing_id:
            return Mission.load(self._mission_dir(existing_id) / "mission.json")
        mission_id = f"mission-{uuid.uuid4().hex[:8]}"
        mission = Mission(
            id=mission_id,
            title=title,
            description=description,
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        mission_dir = self._mission_dir(mission_id)
        (mission_dir / "features").mkdir(parents=True, exist_ok=True)
        (mission_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
        mission.save(mission_dir / "mission.json")
        return mission

    def load_feature_state(self, mission_id: str, feature_id: str) -> FeatureState | None:
        path = self._feature_path(mission_id, feature_id)
        if not path.exists():
            return None
        try:
            return FeatureState.load(path)
        except Exception:
            return None

    def save_feature_state(self, mission_id: str, state: FeatureState) -> None:
        path = self._feature_path(mission_id, state.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        state.save(path)

    def mark_feature_started(self, mission_id: str, feature_id: str, depends_on: list[str]) -> FeatureState:
        fs = self.load_feature_state(mission_id, feature_id) or FeatureState(
            id=feature_id,
            mission_id=mission_id,
            depends_on=depends_on,
        )
        fs.status = "in_progress"
        fs.started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.save_feature_state(mission_id, fs)
        return fs

    def mark_feature_done(
        self,
        mission_id: str,
        feature_id: str,
        success: bool,
        last_backend: str | None = None,
        retry_count: int = 0,
    ) -> FeatureState:
        fs = self.load_feature_state(mission_id, feature_id) or FeatureState(
            id=feature_id, mission_id=mission_id
        )
        fs.status = "completed" if success else "failed"
        fs.completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fs.last_backend = last_backend
        fs.retry_count = retry_count
        self.save_feature_state(mission_id, fs)
        return fs

    def save_checkpoint(self, pipeline_state: "PipelineState", feature_states: dict[str, "FeatureState"]) -> None:
        active_id = self.active_mission_id()
        if not active_id:
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        checkpoint = Checkpoint(
            timestamp=ts,
            mission_id=active_id,
            pipeline_state=pipeline_state,
            feature_states=feature_states,
        )
        path = self._checkpoint_dir(active_id) / f"{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.save(path)

    def complete_mission(self, mission_id: str) -> None:
        mission_path = self._mission_dir(mission_id) / "mission.json"
        if not mission_path.exists():
            return
        m = Mission.load(mission_path)
        m.status = "done"
        m.save(mission_path)


# ─────────────────────────────────────────────────────────────────────────────

_RESULT_PATTERN = re.compile(r"```json autopilot-result\s*\n(.*?)\n```", re.DOTALL)


class AgentOutput(BaseModel):
    status: str                          # "success" | "failure" | "partial"
    summary: str
    artifacts: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    next_hint: str | None = None

    @classmethod
    def parse(cls, raw: str) -> "AgentOutput":
        match = _RESULT_PATTERN.search(raw)
        if not match:
            raise ValueError(
                "autopilot-result JSON block not found in agent output. "
                f"Raw output (first 500 chars): {raw[:500]}"
            )
        return cls.model_validate_json(match.group(1))
