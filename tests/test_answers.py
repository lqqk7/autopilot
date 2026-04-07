from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autopilot.agents.loader import AgentLoader
from autopilot.backends.base import RunContext
from autopilot.pipeline.context import Feature


# ─── _load_answers_md ─────────────────────────────────────────────────────────

def test_answers_missing_returns_empty(tmp_path: Path) -> None:
    assert AgentLoader._load_answers_md(tmp_path) == ""


def test_answers_empty_json_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "answers.json").write_text("{}", encoding="utf-8")
    assert AgentLoader._load_answers_md(tmp_path) == ""


def test_answers_standard_keys_formatted_with_chinese_labels(tmp_path: Path) -> None:
    (tmp_path / "answers.json").write_text(
        json.dumps({"database": "PostgreSQL", "orm": "Prisma"}), encoding="utf-8"
    )
    result = AgentLoader._load_answers_md(tmp_path)
    assert "数据库：PostgreSQL" in result
    assert "ORM：Prisma" in result


def test_answers_all_standard_keys(tmp_path: Path) -> None:
    data = {
        "database": "PostgreSQL",
        "orm": "Prisma",
        "auth_strategy": "JWT",
        "deployment_target": "Vercel",
        "testing_framework": "pytest",
    }
    (tmp_path / "answers.json").write_text(json.dumps(data), encoding="utf-8")
    result = AgentLoader._load_answers_md(tmp_path)
    assert "认证方案：JWT" in result
    assert "部署目标：Vercel" in result
    assert "测试框架：pytest" in result


def test_answers_custom_nested_dict_expanded(tmp_path: Path) -> None:
    data = {"custom": {"payment_provider": "Stripe", "cache_backend": "Redis"}}
    (tmp_path / "answers.json").write_text(json.dumps(data), encoding="utf-8")
    result = AgentLoader._load_answers_md(tmp_path)
    assert "payment_provider：Stripe" in result
    assert "cache_backend：Redis" in result


def test_answers_invalid_json_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "answers.json").write_text("not-json!!!", encoding="utf-8")
    assert AgentLoader._load_answers_md(tmp_path) == ""


def test_answers_unknown_key_uses_raw_key(tmp_path: Path) -> None:
    (tmp_path / "answers.json").write_text(
        json.dumps({"ci_provider": "GitHub Actions"}), encoding="utf-8"
    )
    result = AgentLoader._load_answers_md(tmp_path)
    assert "ci_provider：GitHub Actions" in result


# ─── build_system_prompt 注入 ─────────────────────────────────────────────────

def _make_ctx(project_path: Path) -> RunContext:
    return RunContext(
        project_path=project_path,
        docs_path=project_path / ".autopilot" / "docs",
        feature=None,
        knowledge_md="",
    )


def test_prompt_contains_preset_decisions_when_answers_present(tmp_path: Path) -> None:
    autopilot_dir = tmp_path / ".autopilot"
    autopilot_dir.mkdir()
    (autopilot_dir / "answers.json").write_text(
        json.dumps({"database": "MySQL"}), encoding="utf-8"
    )

    loader = AgentLoader()
    ctx = _make_ctx(tmp_path)

    # doc_gen agent must exist; patch path resolution to avoid FileNotFoundError
    from autopilot.agents import loader as loader_mod
    from unittest.mock import patch

    fake_md = "# Doc Gen Agent\n你是文档生成助手。"
    with patch.object(loader_mod, "get_agent_prompt_path") as mock_path:
        mock_path.return_value = MagicMock(
            read_text=lambda encoding=None: fake_md
        )
        prompt = loader.build_system_prompt("doc_gen", ctx)

    assert "## 预设决策" in prompt
    assert "数据库：MySQL" in prompt


def test_prompt_has_no_preset_block_when_answers_empty(tmp_path: Path) -> None:
    autopilot_dir = tmp_path / ".autopilot"
    autopilot_dir.mkdir()
    (autopilot_dir / "answers.json").write_text("{}", encoding="utf-8")

    loader = AgentLoader()
    ctx = _make_ctx(tmp_path)

    from autopilot.agents import loader as loader_mod
    from unittest.mock import patch

    with patch.object(loader_mod, "get_agent_prompt_path") as mock_path:
        mock_path.return_value = MagicMock(
            read_text=lambda encoding=None: "# Agent"
        )
        prompt = loader.build_system_prompt("doc_gen", ctx)

    assert "## 预设决策" not in prompt


# ─── init_project 创建 answers.json ──────────────────────────────────────────

def test_init_creates_answers_json(tmp_path: Path) -> None:
    from autopilot.init_project import init_project
    init_project(tmp_path, backend="claude")
    answers_path = tmp_path / ".autopilot" / "answers.json"
    assert answers_path.exists()
    data = json.loads(answers_path.read_text())
    assert data == {}


def test_init_does_not_overwrite_existing_answers(tmp_path: Path) -> None:
    from autopilot.init_project import init_project
    autopilot_dir = tmp_path / ".autopilot"
    autopilot_dir.mkdir(parents=True)
    existing = {"database": "SQLite"}
    (autopilot_dir / "answers.json").write_text(json.dumps(existing), encoding="utf-8")

    init_project(tmp_path, backend="claude")

    data = json.loads((autopilot_dir / "answers.json").read_text())
    assert data == existing
