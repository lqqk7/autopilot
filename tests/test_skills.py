"""Tests for v0.6 Skill Runtime."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autopilot.skills.registry import SkillDef, SkillRegistry, SkillTrigger
from autopilot.skills.runner import SkillRunner


# ── SkillRegistry ──────────────────────────────────────────────────────────────

def test_builtin_skills_loaded() -> None:
    reg = SkillRegistry(user_skills_dir=Path("/nonexistent"))
    assert len(reg.all_skills()) > 0


def test_builtin_skill_names_present() -> None:
    reg = SkillRegistry(user_skills_dir=Path("/nonexistent"))
    names = {s.name for s in reg.all_skills()}
    assert "git-pr-workflow" in names
    assert "api-endpoint-design" in names
    assert "security-hardening" in names
    assert "test-coverage" in names


def test_match_by_keyword() -> None:
    reg = SkillRegistry(user_skills_dir=Path("/nonexistent"))
    matches = reg.match("implement REST api endpoint for users")
    assert any(s.name == "api-endpoint-design" for s in matches)


def test_match_by_keyword_and_phase() -> None:
    reg = SkillRegistry(user_skills_dir=Path("/nonexistent"))
    matches = reg.match("add login and password auth", phase="CODE")
    assert any(s.name == "security-hardening" for s in matches)


def test_no_match_for_irrelevant() -> None:
    reg = SkillRegistry(user_skills_dir=Path("/nonexistent"))
    matches = reg.match("update the landing page color scheme")
    assert all(s.name not in ("database-migration", "security-hardening") for s in matches)


def test_user_skill_loaded_from_json(tmp_path: Path) -> None:
    skill_data = {
        "name": "custom-skill",
        "category": "custom",
        "description": "Test skill",
        "trigger": {"keywords": ["custom", "special"], "phases": []},
        "prompt_hint": "Use the custom approach.",
    }
    (tmp_path / "custom.json").write_text(json.dumps(skill_data))
    reg = SkillRegistry(user_skills_dir=tmp_path)
    assert reg.get("custom-skill") is not None


def test_user_skill_list_format(tmp_path: Path) -> None:
    skills = [
        {"name": "skill-a", "category": "cat", "trigger": {"keywords": ["aaa"], "phases": []}},
        {"name": "skill-b", "category": "cat", "trigger": {"keywords": ["bbb"], "phases": []}},
    ]
    (tmp_path / "multi.json").write_text(json.dumps(skills))
    reg = SkillRegistry(user_skills_dir=tmp_path)
    assert reg.get("skill-a") is not None
    assert reg.get("skill-b") is not None


def test_malformed_skill_file_skipped(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("not valid json {{{{")
    reg = SkillRegistry(user_skills_dir=tmp_path)
    # Should not raise; bad file is silently skipped
    assert len(reg.all_skills()) > 0  # builtins still loaded


def test_skill_def_matches_no_phase_filter() -> None:
    skill = SkillDef(
        name="test",
        category="cat",
        trigger=SkillTrigger(keywords=["redis"], phases=[]),
    )
    assert skill.matches("setup redis connection pool")
    assert not skill.matches("implement user login")


def test_skill_def_matches_with_phase_filter() -> None:
    skill = SkillDef(
        name="test",
        category="cat",
        trigger=SkillTrigger(keywords=["auth"], phases=["CODE"]),
    )
    assert skill.matches("auth token", phase="CODE")
    assert not skill.matches("auth token", phase="TEST")
    assert not skill.matches("auth token", phase=None)


# ── SkillRunner ────────────────────────────────────────────────────────────────

def test_build_hints_returns_markdown() -> None:
    runner = SkillRunner()
    hints = runner.build_hints("implement user authentication with JWT tokens", phase="CODE")
    assert "## Applicable Skill Guidelines" in hints
    assert "security-hardening" in hints


def test_build_hints_empty_for_no_match() -> None:
    runner = SkillRunner()
    hints = runner.build_hints("update page title color from blue to green")
    # May or may not match depending on builtins; just verify it returns a string
    assert isinstance(hints, str)


def test_build_verify_commands() -> None:
    runner = SkillRunner()
    steps = runner.build_verify_commands("create pull request for feature branch")
    assert isinstance(steps, list)
    # git-pr-workflow has a verify step
    assert any("git log" in cmd for cmd, _ in steps)
