"""PrinciplesLoader: loads and injects per-phase behavioral rules into prompts.

Rule sources (in priority order — local overrides global):
  1. .autopilot/principles.local.jsonl  (project-specific)
  2. .autopilot/principles.jsonl        (project-level global)
  3. ~/.autopilot/principles.jsonl      (user-level global)

Rule format (one JSON object per line):
  {"phase": "CODE", "rule": "No eval() or exec()", "severity": "error"}
  {"phase": "*",    "rule": "All API calls must have timeouts", "severity": "warn"}

Phases: CODE, TEST, REVIEW, FIX, DOC_GEN, PLANNING, INTERVIEW, DELIVERY, or "*" for all.
Severity: "error" (must follow) | "warn" (should follow) | "info" (context only)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_GLOBAL_PRINCIPLES_PATH = Path.home() / ".autopilot" / "principles.jsonl"

_SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


class Principle(BaseModel):
    phase: str          # Phase value or "*" for all phases
    rule: str
    severity: str = "warn"   # error | warn | info

    def applies_to(self, phase: str) -> bool:
        return self.phase == "*" or self.phase.upper() == phase.upper()


class PrinciplesLoader:
    """Loads behavioral rules from jsonl files and generates prompt injections."""

    def __init__(self, autopilot_dir: Path | None = None) -> None:
        self._autopilot_dir = autopilot_dir
        self._global_path = _GLOBAL_PRINCIPLES_PATH

    def _load_file(self, path: Path) -> list[Principle]:
        if not path.exists():
            return []
        principles: list[Principle] = []
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                data = json.loads(line)
                principles.append(Principle.model_validate(data))
            except Exception as e:
                logger.debug("Skipping malformed principle at %s line %d: %s", path, i, e)
        return principles

    def load_for_phase(self, phase: str) -> list[Principle]:
        """Load all principles that apply to the given phase, deduplicated, sorted by severity."""
        all_principles: list[Principle] = []

        # Load global (lowest priority)
        all_principles.extend(self._load_file(self._global_path))

        # Load project-level (overrides global)
        if self._autopilot_dir:
            all_principles.extend(self._load_file(self._autopilot_dir / "principles.jsonl"))
            # Load local (highest priority)
            all_principles.extend(self._load_file(self._autopilot_dir / "principles.local.jsonl"))

        # Filter to phase and deduplicate by rule text
        seen: set[str] = set()
        filtered: list[Principle] = []
        for p in all_principles:
            if p.applies_to(phase) and p.rule not in seen:
                seen.add(p.rule)
                filtered.append(p)

        # Sort: errors first, then warns, then info
        filtered.sort(key=lambda p: _SEVERITY_ORDER.get(p.severity, 99))
        return filtered

    def build_injection(self, phase: str) -> str:
        """Return a formatted principles block to inject into prompts, or empty string."""
        principles = self.load_for_phase(phase)
        if not principles:
            return ""

        errors = [p for p in principles if p.severity == "error"]
        warns = [p for p in principles if p.severity == "warn"]
        infos = [p for p in principles if p.severity == "info"]

        lines = ["## Behavioral Principles\n"]
        if errors:
            lines.append("### ❌ Must Follow (errors)")
            for p in errors:
                lines.append(f"- {p.rule}")
            lines.append("")
        if warns:
            lines.append("### ⚠️ Should Follow (warnings)")
            for p in warns:
                lines.append(f"- {p.rule}")
            lines.append("")
        if infos:
            lines.append("### ℹ️ Context")
            for p in infos:
                lines.append(f"- {p.rule}")
            lines.append("")

        return "\n".join(lines)
