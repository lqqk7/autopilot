"""HandoffWriter: creates handoff packets on phase complete or pause."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from autopilot.handoff.models import Handoff, HandoffContext, HandoffMission

logger = logging.getLogger(__name__)


class HandoffWriter:
    """Creates and persists Handoff packets to .autopilot/handoffs/."""

    def __init__(self, autopilot_dir: Path, session_id: str = "") -> None:
        self._handoffs_dir = autopilot_dir / "handoffs"
        self._session_id = session_id or f"session-{uuid.uuid4().hex[:8]}"

    def write(
        self,
        mission_id: str,
        mission_title: str,
        mission_status: str,
        current_feature: str | None = None,
        completed_features: list[str] | None = None,
        pending_features: list[str] | None = None,
        recent_decisions: list[str] | None = None,
        open_issues: list[str] | None = None,
        constraints: list[str] | None = None,
        knowledge_hints: list[str] | None = None,
        principles: list[str] | None = None,
        handoff_type: str = "agent-to-agent",
    ) -> Handoff:
        """Create and persist a handoff packet. Returns the Handoff."""
        handoff_id = f"h-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        handoff = Handoff(
            handoff_id=handoff_id,
            from_session=self._session_id,
            type=handoff_type,
            mission=HandoffMission(
                id=mission_id,
                title=mission_title,
                status=mission_status,
            ),
            context=HandoffContext(
                current_feature=current_feature,
                completed_features=completed_features or [],
                pending_features=pending_features or [],
                recent_decisions=recent_decisions or [],
                open_issues=open_issues or [],
            ),
            constraints=constraints or [],
            knowledge_hints=knowledge_hints or [],
            principles=principles or [],
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        path = self._handoffs_dir / f"{handoff_id}.json"
        handoff.save(path)
        logger.info("Handoff written: %s", handoff_id)
        return handoff
