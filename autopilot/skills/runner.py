"""SkillRunner: matches features to skills and generates prompt injections."""
from __future__ import annotations

from autopilot.skills.registry import SkillDef, SkillRegistry


class SkillRunner:
    """Matches features to applicable skills and generates skill hints for prompts."""

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self._registry = registry or SkillRegistry()

    def find_skills(self, feature_text: str, phase: str | None = None) -> list[SkillDef]:
        return self._registry.match(feature_text, phase)

    def build_hints(self, feature_text: str, phase: str | None = None) -> str:
        """Return a formatted skill-hints block to append to a backend prompt."""
        skills = self.find_skills(feature_text, phase)
        hints = [s.prompt_hint for s in skills if s.prompt_hint]
        if not hints:
            return ""
        lines = ["## Applicable Skill Guidelines\n"]
        for skill, hint in zip(skills, hints):
            lines.append(f"### {skill.name} ({skill.category})")
            lines.append(hint)
            lines.append("")
        return "\n".join(lines)

    def build_verify_commands(self, feature_text: str, phase: str | None = None) -> list[tuple[str, str]]:
        """Return (run_cmd, expected) pairs from all matching skill verify steps."""
        skills = self.find_skills(feature_text, phase)
        steps: list[tuple[str, str]] = []
        for s in skills:
            for step in s.verify:
                steps.append((step.run, step.expect))
        return steps
