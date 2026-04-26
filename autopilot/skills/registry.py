"""SkillRegistry: loads and manages Skill definitions.

Built-in skills are defined here as Python data.
User-defined skills are loaded from ~/.autopilot/skills/*.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


_USER_SKILLS_DIR = Path.home() / ".autopilot" / "skills"


class SkillTrigger(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)   # Phase values, e.g. ["CODE", "FIX"]


class SkillVerifyStep(BaseModel):
    run: str
    expect: str


class SkillDef(BaseModel):
    name: str
    category: str
    description: str = ""
    trigger: SkillTrigger = Field(default_factory=SkillTrigger)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    verify: list[SkillVerifyStep] = Field(default_factory=list)
    prompt_hint: str = ""  # Extra instruction injected into backend prompt

    def matches(self, text: str, phase: str | None = None) -> bool:
        """Return True if this skill applies to the given feature text and/or phase."""
        text_lower = text.lower()
        keyword_match = any(kw.lower() in text_lower for kw in self.trigger.keywords)
        if not keyword_match:
            return False
        if self.trigger.phases:
            # phase-restricted skill: only match if phase is known and in the list
            return phase is not None and phase in self.trigger.phases
        return True


# ── Built-in Skills ───────────────────────────────────────────────────────────

_BUILTIN_SKILLS: list[dict] = [
    {
        "name": "git-pr-workflow",
        "category": "version-control",
        "description": "Automates PR creation with proper branching and commit messages.",
        "trigger": {"keywords": ["pr", "pull request", "merge request", "branch"], "phases": []},
        "prompt_hint": (
            "When working with git: create a feature branch, make atomic commits, "
            "then open a PR with a clear title and description. "
            "Use conventional commits format (feat/fix/chore/docs)."
        ),
        "verify": [
            {"run": "git log --oneline -5", "expect": "contains recent commits"},
        ],
    },
    {
        "name": "api-endpoint-design",
        "category": "software-development",
        "description": "Ensures REST API endpoints follow RESTful conventions.",
        "trigger": {"keywords": ["api", "endpoint", "rest", "route", "http"], "phases": []},
        "prompt_hint": (
            "Design REST endpoints following these conventions: "
            "use plural nouns for resources, proper HTTP methods (GET/POST/PUT/DELETE/PATCH), "
            "return appropriate status codes, include pagination for list endpoints."
        ),
        "verify": [],
    },
    {
        "name": "database-migration",
        "category": "database",
        "description": "Safe database migration with rollback support.",
        "trigger": {"keywords": ["migration", "schema", "database", "db", "table", "column"], "phases": ["CODE"]},
        "prompt_hint": (
            "For database migrations: always create reversible migrations with up/down methods. "
            "Test migration in isolation. Ensure indexes are created for foreign keys. "
            "Never drop columns in the same migration as data migrations."
        ),
        "verify": [],
    },
    {
        "name": "security-hardening",
        "category": "security",
        "description": "Apply security best practices to the implementation.",
        "trigger": {"keywords": ["auth", "login", "password", "token", "jwt", "session", "permission"], "phases": ["CODE", "REVIEW"]},
        "prompt_hint": (
            "Security requirements: validate all inputs, use parameterized queries, "
            "hash passwords with bcrypt/argon2, implement rate limiting on auth endpoints, "
            "check for hardcoded secrets before committing."
        ),
        "verify": [],
    },
    {
        "name": "test-coverage",
        "category": "testing",
        "description": "Enforce minimum test coverage and test quality.",
        "trigger": {"keywords": ["test", "coverage", "unit test", "integration test"], "phases": ["TEST", "REVIEW"]},
        "prompt_hint": (
            "Testing requirements: achieve ≥80% code coverage. "
            "Write unit tests for all business logic, integration tests for API endpoints. "
            "Use descriptive test names that document behavior (test_<scenario>_<expected_result>)."
        ),
        "verify": [],
    },
    {
        "name": "async-concurrency",
        "category": "software-development",
        "description": "Best practices for async and concurrent code.",
        "trigger": {"keywords": ["async", "await", "concurrent", "thread", "queue", "worker"], "phases": ["CODE"]},
        "prompt_hint": (
            "Async/concurrency guidelines: avoid blocking calls in async contexts, "
            "use connection pools for external services, handle cancellation properly, "
            "add timeouts to all external calls, use locks for shared state."
        ),
        "verify": [],
    },
]


class SkillRegistry:
    """Registry of all available skills (built-in + user-defined)."""

    def __init__(self, user_skills_dir: Path | None = None) -> None:
        self._skills: dict[str, SkillDef] = {}
        self._load_builtins()
        self._load_user_skills(user_skills_dir or _USER_SKILLS_DIR)

    def _load_builtins(self) -> None:
        for data in _BUILTIN_SKILLS:
            skill = SkillDef.model_validate(data)
            self._skills[skill.name] = skill

    def _load_user_skills(self, skills_dir: Path) -> None:
        if not skills_dir.exists():
            return
        for f in sorted(skills_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        skill = SkillDef.model_validate(item)
                        self._skills[skill.name] = skill
                else:
                    skill = SkillDef.model_validate(data)
                    self._skills[skill.name] = skill
            except Exception:
                pass  # skip malformed skill files

    def all_skills(self) -> list[SkillDef]:
        return list(self._skills.values())

    def get(self, name: str) -> SkillDef | None:
        return self._skills.get(name)

    def match(self, text: str, phase: str | None = None) -> list[SkillDef]:
        """Return all skills that match the given feature text and phase."""
        return [s for s in self._skills.values() if s.matches(text, phase)]
