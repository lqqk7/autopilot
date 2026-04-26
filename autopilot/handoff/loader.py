"""HandoffLoader: reads the latest handoff to resume context in a new session."""
from __future__ import annotations

import logging
from pathlib import Path

from autopilot.handoff.models import Handoff

logger = logging.getLogger(__name__)


class HandoffLoader:
    """Loads the most recent handoff from .autopilot/handoffs/."""

    def __init__(self, autopilot_dir: Path) -> None:
        self._handoffs_dir = autopilot_dir / "handoffs"

    def latest(self) -> Handoff | None:
        """Return the most recent handoff, or None if none exist."""
        if not self._handoffs_dir.exists():
            return None
        files = sorted(self._handoffs_dir.glob("*.json"), reverse=True)
        for f in files:
            try:
                return Handoff.load(f)
            except Exception as exc:
                logger.debug("Failed to load handoff %s: %s", f, exc)
        return None

    def load_by_id(self, handoff_id: str) -> Handoff | None:
        path = self._handoffs_dir / f"{handoff_id}.json"
        if not path.exists():
            return None
        try:
            return Handoff.load(path)
        except Exception as exc:
            logger.debug("Failed to load handoff %s: %s", handoff_id, exc)
            return None

    def all(self) -> list[Handoff]:
        """Return all handoffs sorted newest-first."""
        if not self._handoffs_dir.exists():
            return []
        results = []
        for f in sorted(self._handoffs_dir.glob("*.json"), reverse=True):
            try:
                results.append(Handoff.load(f))
            except Exception:
                pass
        return results

    def inject_into_prompt(self, prompt: str) -> str:
        """Prepend the latest handoff context to a prompt, if one exists."""
        handoff = self.latest()
        if not handoff:
            return prompt
        block = handoff.to_prompt_block()
        return block + "\n\n---\n\n" + prompt
