"""v0.9 Handoff data models."""
from __future__ import annotations

from pathlib import Path

import json
from pydantic import BaseModel, Field


class HandoffMission(BaseModel):
    id: str
    title: str
    status: str   # in_progress | paused | done


class HandoffContext(BaseModel):
    current_feature: str | None = None
    completed_features: list[str] = Field(default_factory=list)
    pending_features: list[str] = Field(default_factory=list)
    recent_decisions: list[str] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)


class Handoff(BaseModel):
    handoff_id: str
    from_session: str
    to_session: str = "next"
    type: str = "agent-to-agent"   # agent-to-agent | human-to-agent | agent-to-human
    mission: HandoffMission
    context: HandoffContext = Field(default_factory=HandoffContext)
    constraints: list[str] = Field(default_factory=list)
    knowledge_hints: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)
    approved_by: str = ""
    created_at: str = ""

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Handoff":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def to_prompt_block(self) -> str:
        """Format as a markdown block for injection into agent prompts."""
        lines = [
            f"## Handoff Context (from session: {self.from_session})\n",
            f"**Mission**: {self.mission.title} [{self.mission.status}]",
        ]
        ctx = self.context
        if ctx.current_feature:
            lines.append(f"**Current feature**: {ctx.current_feature}")
        if ctx.completed_features:
            lines.append(f"**Completed**: {', '.join(ctx.completed_features)}")
        if ctx.pending_features:
            lines.append(f"**Pending**: {', '.join(ctx.pending_features)}")
        if ctx.recent_decisions:
            lines.append("\n**Recent decisions**:")
            for d in ctx.recent_decisions:
                lines.append(f"  - {d}")
        if ctx.open_issues:
            lines.append("\n**Open issues**:")
            for i in ctx.open_issues:
                lines.append(f"  - {i}")
        if self.constraints:
            lines.append("\n**Constraints** (do not violate):")
            for c in self.constraints:
                lines.append(f"  - {c}")
        if self.knowledge_hints:
            lines.append("\n**Knowledge hints**:")
            for h in self.knowledge_hints:
                lines.append(f"  - {h}")
        if self.principles:
            lines.append("\n**Active principles**:")
            for p in self.principles:
                lines.append(f"  - {p}")
        return "\n".join(lines)
