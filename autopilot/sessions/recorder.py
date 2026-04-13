"""Append-only JSONL event recorder for a single autopilot pipeline run."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from autopilot.backends.base import BackendResult


def new_session_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    uid = uuid4().hex[:8]
    return f"{ts}-{uid}"


class SessionRecorder:
    """Writes pipeline events to .autopilot/sessions/<session_id>.jsonl.

    One JSON object per line (JSONL). Writes are thread-safe — safe to use
    from parallel FeatureWorker threads.
    """

    def __init__(self, sessions_dir: Path, session_id: str | None = None) -> None:
        self.session_id = session_id or new_session_id()
        try:
            sessions_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._path = sessions_dir / f"{self.session_id}.jsonl"
        self._lock = threading.Lock()

    # ── low-level ──────────────────────────────────────────────────────────

    def emit(self, event: str, **data: object) -> None:
        try:
            record = {"event": event, "ts": time.time(), "session_id": self.session_id, **data}
            line = json.dumps(record, ensure_ascii=False)
            with self._lock:
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
                    f.flush()
        except Exception:
            pass  # session recording must never break the pipeline

    # ── typed helpers ──────────────────────────────────────────────────────

    def session_start(self, backend: str, phase: str, max_parallel: int = 1) -> None:
        self.emit(
            "session_start",
            backend=backend,
            phase=phase,
            max_parallel=max_parallel,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    def phase_enter(self, phase: str) -> None:
        self.emit("phase_enter", phase=phase)

    def phase_exit(self, phase: str, passed: bool, duration_s: float) -> None:
        self.emit("phase_exit", phase=phase, passed=passed, duration_s=round(duration_s, 2))

    def agent_call(
        self,
        phase: str,
        agent_name: str,
        backend_name: str,
        result: BackendResult,
        feature_id: str | None = None,
        local_retry: int = 0,
        prompt: str = "",
    ) -> None:
        self.emit(
            "agent_call",
            phase=phase,
            agent=agent_name,
            backend=backend_name,
            feature_id=feature_id,
            success=result.success,
            duration_s=round(result.duration_seconds, 2),
            output_chars=len(result.output),
            # Store the tail — autopilot-result JSON block is always at the end
            output_tail=result.output[-2000:] if result.output else "",
            error=result.error,
            error_type=result.error_type.value if result.error_type else None,
            local_retry=local_retry,
            prompt_chars=len(prompt),
            prompt_hash=hashlib.sha1(prompt.encode()).hexdigest()[:8] if prompt else "",
        )

    def feature_done(
        self,
        feature_id: str,
        title: str,
        success: bool,
        duration_s: float,
        fix_retries: int = 0,
    ) -> None:
        self.emit(
            "feature_done",
            feature_id=feature_id,
            title=title,
            success=success,
            duration_s=round(duration_s, 2),
            fix_retries=fix_retries,
        )

    def backend_switch(self, from_name: str, to_name: str, reason: str) -> None:
        self.emit("backend_switch", from_backend=from_name, to_backend=to_name, reason=reason)

    def session_end(
        self,
        final_phase: str,
        elapsed_s: float,
        features_done: int = 0,
        features_total: int = 0,
    ) -> None:
        self.emit(
            "session_end",
            final_phase=final_phase,
            elapsed_s=round(elapsed_s, 2),
            features_done=features_done,
            features_total=features_total,
            ended_at=datetime.now(timezone.utc).isoformat(),
        )
