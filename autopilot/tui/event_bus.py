"""EventBus: thread-safe event queue between the pipeline engine and the TUI.

The engine calls emit() from background threads; the TUI polls drain() on a
timer and updates widgets. emit() is fire-and-forget and never raises.
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TUIEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """One-directional event channel: engine → TUI.

    Thread safety: emit() is safe to call from any thread. drain() and clear()
    should only be called from the TUI thread. Note that drain() returns events
    queued *before* the call; concurrent emit() calls may add new events
    immediately after drain() returns — that is expected and fine.
    """

    def __init__(self) -> None:
        self._q: Queue[TUIEvent] = Queue()

    # ── producer side (called from engine background threads) ────────────────

    def emit(self, event_type: str, **data: Any) -> None:
        """Put a snapshot of data onto the queue. Never raises."""
        try:
            self._q.put_nowait(TUIEvent(type=event_type, data=copy.deepcopy(data)))
        except Exception:
            logger.debug("EventBus.emit failed silently", exc_info=True)

    # ── consumer side (called from TUI main thread) ──────────────────────────

    def drain(self) -> list[TUIEvent]:
        """Return all currently queued events. New events emitted concurrently
        may not be included — callers should tolerate that."""
        events: list[TUIEvent] = []
        try:
            while True:
                events.append(self._q.get_nowait())
        except Empty:
            pass
        return events

    def clear(self) -> None:
        """Discard queued events on a best-effort basis."""
        try:
            while True:
                self._q.get_nowait()
        except Empty:
            pass
