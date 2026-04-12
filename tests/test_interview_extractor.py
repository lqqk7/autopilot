from __future__ import annotations

import json
from pathlib import Path

import pytest

from autopilot.agents.interview_extractor import extract_decisions, merge_into_answers_json


# ─── extract_decisions ────────────────────────────────────────────────────────

SAMPLE_INTERVIEW_MD = """
# 需求澄清报告

---

## 2. 关键技术决策

### 2.1 数据库选型

**可选方案：**
- PostgreSQL
- MySQL

**推荐：PostgreSQL**

**你的决定：** PostgreSQL

---

### 2.2 认证方案

**你的决定：** JWT + Refresh Token

---

### 2.3 部署目标

**你的决定：** Docker + VPS

---

## 3. 模糊点澄清

### Q1. 是否需要多租户支持？

**背景：** 需求中未提及。

**你的回答：** 暂不需要，单租户即可

---

### Q2. 支付方式？

**你的回答：** 仅支持支付宝

---

## 4. 优先级确认

**你的调整：** 无调整，按推荐顺序来
"""


def test_extract_known_keys() -> None:
    result = extract_decisions(SAMPLE_INTERVIEW_MD)
    assert result.get("database") == "PostgreSQL"
    assert result.get("auth_strategy") == "JWT + Refresh Token"
    assert result.get("deployment_target") == "Docker + VPS"


def test_extract_custom_keys() -> None:
    result = extract_decisions(SAMPLE_INTERVIEW_MD)
    custom = result.get("custom", {})
    assert isinstance(custom, dict)
    assert "是否需要多租户支持？" in custom
    assert custom["是否需要多租户支持？"] == "暂不需要，单租户即可"
    assert "支付方式？" in custom
    assert custom["支付方式？"] == "仅支持支付宝"


def test_skips_unfilled_placeholders() -> None:
    md = """
### 2.1 数据库选型

**你的决定：** （请在这里填写）

### 2.2 认证方案

**你的决定：** JWT
"""
    result = extract_decisions(md)
    assert "database" not in result
    assert result.get("auth_strategy") == "JWT"


def test_empty_md_returns_empty() -> None:
    assert extract_decisions("") == {}


def test_no_filled_answers_returns_empty() -> None:
    md = """
### 2.1 数据库选型

**你的决定：** （请在这里填写）
"""
    assert extract_decisions(md) == {}


def test_answer_on_next_line() -> None:
    """答案另起一行（用户把内容写在下一行）的情况。"""
    md = """
### Q1. 缓存方案？

**你的回答：**
Redis，用于 session 和热点数据缓存
"""
    result = extract_decisions(md)
    custom = result.get("custom", {})
    assert isinstance(custom, dict)
    assert "缓存方案？" in custom
    assert "Redis" in custom["缓存方案？"]


# ─── merge_into_answers_json ──────────────────────────────────────────────────

def test_merge_creates_answers_json(tmp_path: Path) -> None:
    req_dir = tmp_path / "requirements"
    req_dir.mkdir()
    (req_dir / "INTERVIEW.md").write_text(
        "### 2.1 数据库选型\n\n**你的决定：** SQLite\n", encoding="utf-8"
    )

    count = merge_into_answers_json(tmp_path)
    assert count == 1

    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf-8"))
    assert data.get("database") == "SQLite"


def test_merge_preserves_existing_entries(tmp_path: Path) -> None:
    req_dir = tmp_path / "requirements"
    req_dir.mkdir()
    (req_dir / "INTERVIEW.md").write_text(
        "### 2.1 认证方案\n\n**你的决定：** OAuth2\n", encoding="utf-8"
    )
    existing = {"database": "PostgreSQL", "custom": {"ci": "GitHub Actions"}}
    (tmp_path / "answers.json").write_text(
        json.dumps(existing), encoding="utf-8"
    )

    merge_into_answers_json(tmp_path)

    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf-8"))
    assert data["database"] == "PostgreSQL"          # 原有字段保留
    assert data["auth_strategy"] == "OAuth2"         # 新提取字段写入
    assert data["custom"]["ci"] == "GitHub Actions"  # custom 内层保留


def test_merge_custom_inner_merge(tmp_path: Path) -> None:
    req_dir = tmp_path / "requirements"
    req_dir.mkdir()
    (req_dir / "INTERVIEW.md").write_text(
        "### Q1. 缓存方案？\n\n**你的回答：** Redis\n", encoding="utf-8"
    )
    existing = {"custom": {"payment": "Stripe"}}
    (tmp_path / "answers.json").write_text(json.dumps(existing), encoding="utf-8")

    merge_into_answers_json(tmp_path)

    data = json.loads((tmp_path / "answers.json").read_text(encoding="utf-8"))
    assert data["custom"]["payment"] == "Stripe"   # 原 custom 保留
    assert data["custom"]["缓存方案？"] == "Redis"  # 新 custom 追加


def test_merge_returns_zero_when_no_interview_md(tmp_path: Path) -> None:
    (tmp_path / "requirements").mkdir()
    assert merge_into_answers_json(tmp_path) == 0


def test_merge_returns_zero_when_all_placeholders(tmp_path: Path) -> None:
    req_dir = tmp_path / "requirements"
    req_dir.mkdir()
    (req_dir / "INTERVIEW.md").write_text(
        "### 2.1 数据库\n\n**你的决定：** （请在这里填写）\n", encoding="utf-8"
    )
    assert merge_into_answers_json(tmp_path) == 0
