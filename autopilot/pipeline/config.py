"""PipelineConfig: all tunable pipeline parameters, loaded from config.toml."""
from __future__ import annotations

from dataclasses import dataclass, field

from autopilot.pipeline.context import Phase

# ── defaults ─────────────────────────────────────────────────────────────────

_DEFAULT_TIMEOUTS: dict[Phase, int] = {
    Phase.INTERVIEW:  300,   #  5 min
    Phase.DOC_GEN:    600,   # 10 min
    Phase.DOC_UPDATE: 600,   # 10 min
    Phase.PLANNING:   600,   # 10 min
    Phase.DELIVERY:   600,   # 10 min
    Phase.CODE:      1800,   # 30 min
    Phase.TEST:       900,   # 15 min
    Phase.REVIEW:     600,   # 10 min
    Phase.FIX:        900,   # 15 min
    Phase.KNOWLEDGE:  600,   # 10 min
}

_DEFAULT_TIMEOUT_FALLBACK = 300

_KEY_TO_PHASE: dict[str, Phase] = {
    "interview":  Phase.INTERVIEW,
    "doc_gen":    Phase.DOC_GEN,
    "doc_update": Phase.DOC_UPDATE,
    "planning":   Phase.PLANNING,
    "delivery":   Phase.DELIVERY,
    "code":       Phase.CODE,
    "test":       Phase.TEST,
    "review":     Phase.REVIEW,
    "fix":        Phase.FIX,
    "knowledge":  Phase.KNOWLEDGE,
}

REVIEW_MODES = ("self", "cross", "backend")


# ── review config ─────────────────────────────────────────────────────────────

@dataclass
class ReviewConfig:
    """Controls which backend performs the REVIEW phase.

    Modes:
      self    — same backend that wrote the code reviews it (default)
      cross   — a different backend from the pool reviews it;
                falls back to "self" when pool has only one backend
      backend — a named backend always handles review;
                falls back to "self" if the named backend is unavailable
    """
    mode: str = "self"
    backend_name: str = ""   # only used when mode = "backend"

    @classmethod
    def from_toml(cls, review_cfg: dict) -> "ReviewConfig":
        mode = review_cfg.get("mode", "self")
        if mode not in REVIEW_MODES:
            mode = "self"
        return cls(
            mode=mode,
            backend_name=review_cfg.get("backend", ""),
        )


# ── pipeline config ───────────────────────────────────────────────────────────

@dataclass
class PipelineConfig:
    """All tunable pipeline parameters. Pass to PipelineEngine and FeatureWorker."""

    model: str = ""
    max_fix_retries: int = 5
    max_phase_retries: int = 3
    phase_timeouts: dict[Phase, int] = field(
        default_factory=lambda: dict(_DEFAULT_TIMEOUTS)
    )
    review: ReviewConfig = field(default_factory=ReviewConfig)
    # Allow backends to bypass approval prompts / sandbox (requires interactive setup).
    # Default: True — keeps the development loop uninterrupted.
    # Set to false in production / security-sensitive environments.
    allow_dangerous_permissions: bool = True
    # Send Telegram notifications on key events (phase done, pause, feature done).
    # Requires env vars: AUTOPILOT_TELEGRAM_TOKEN and AUTOPILOT_TELEGRAM_CHAT_ID.
    telegram_enabled: bool = False

    def timeout_for(self, phase: Phase) -> int:
        return self.phase_timeouts.get(phase, _DEFAULT_TIMEOUT_FALLBACK)

    @classmethod
    def from_toml(cls, ap_cfg: dict, model_override: str = "") -> "PipelineConfig":
        retries = ap_cfg.get("retries", {})
        timeouts_raw = ap_cfg.get("timeouts", {})

        phase_timeouts = dict(_DEFAULT_TIMEOUTS)
        for key, seconds in timeouts_raw.items():
            phase = _KEY_TO_PHASE.get(key)
            if phase is not None:
                phase_timeouts[phase] = int(seconds)

        max_fix_retries = int(retries.get("max_fix_retries", 5))
        max_phase_retries = int(retries.get("max_phase_retries", 3))
        if max_fix_retries < 1:
            raise ValueError(f"max_fix_retries must be >= 1, got {max_fix_retries}")
        if max_phase_retries < 1:
            raise ValueError(f"max_phase_retries must be >= 1, got {max_phase_retries}")
        for key, val in phase_timeouts.items():
            if val < 1:
                raise ValueError(f"timeout for {key.value!r} must be >= 1s, got {val}")

        return cls(
            model=model_override or ap_cfg.get("model", ""),
            max_fix_retries=max_fix_retries,
            max_phase_retries=max_phase_retries,
            phase_timeouts=phase_timeouts,
            review=ReviewConfig.from_toml(ap_cfg.get("review", {})),
            allow_dangerous_permissions=bool(ap_cfg.get("permissions", {}).get("allow_dangerous_permissions", True)),
            telegram_enabled=bool(ap_cfg.get("notifications", {}).get("enabled", False)),
        )
