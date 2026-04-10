from __future__ import annotations

import json
import re
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


class AgentOutput(BaseModel):
    status: str                          # "success" | "failure" | "partial"
    summary: str
    artifacts: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    next_hint: str | None = None

    @classmethod
    def parse(cls, raw: str) -> "AgentOutput":
        pattern = r"```json autopilot-result\s*\n(.*?)\n```"
        match = re.search(pattern, raw, re.DOTALL)
        if not match:
            raise ValueError(
                "autopilot-result JSON block not found in agent output. "
                f"Raw output (first 500 chars): {raw[:500]}"
            )
        return cls.model_validate_json(match.group(1))
