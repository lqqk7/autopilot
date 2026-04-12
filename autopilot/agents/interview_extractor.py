from __future__ import annotations

import json
import re
from pathlib import Path

# 用户未填写的占位符
_PLACEHOLDERS = frozenset({
    "（请在这里填写）",
    "(请在这里填写)",
    "（如有不同意见请在这里填写）",
    "(如有不同意见请在这里填写)",
    "",
})

# 关键词 → answers.json 标准 key 的映射
_KEYWORD_TO_KEY: list[tuple[str, str]] = [
    ("数据库", "database"),
    ("database", "database"),
    ("orm", "orm"),
    ("认证", "auth_strategy"),
    ("鉴权", "auth_strategy"),
    ("auth", "auth_strategy"),
    ("部署", "deployment_target"),
    ("deployment", "deployment_target"),
    ("测试框架", "testing_framework"),
    ("test framework", "testing_framework"),
]


def _match_known_key(title: str) -> str | None:
    title_lower = title.lower()
    for keyword, key in _KEYWORD_TO_KEY:
        if keyword.lower() in title_lower:
            return key
    return None


def _strip_section_prefix(heading: str) -> str:
    """去掉 '### Q1. xxx' 或 '### 2.1 xxx' 里的编号前缀，只保留标题文字。"""
    return re.sub(r"^#+\s+(?:Q\d+[.．]\s+|\d+[.．]\d+\s+)?", "", heading).strip()


def extract_decisions(interview_md: str) -> dict[str, object]:
    """
    解析 INTERVIEW.md，提取用户填写的"你的决定"和"你的回答"。

    返回可直接合并到 answers.json 的 dict：
    - 匹配到已知类型 → 直接作为顶级 key（database / auth_strategy 等）
    - 未知类型 → 放入 custom dict
    """
    lines = interview_md.splitlines()
    current_title = ""
    results: list[tuple[str, str]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 追踪子节标题（### 级别）
        if stripped.startswith("### "):
            current_title = _strip_section_prefix(stripped)
            i += 1
            continue

        # 匹配 "**你的决定：**" 或 "**你的回答：**"
        m = re.match(r"\*\*(?:你的决定|你的回答)[:：]\*\*\s*(.*)", stripped)
        if m and current_title:
            answer = m.group(1).strip()

            # 行内没有内容时，向后查找连续非空行（直到 --- 或 ### 为止）
            if not answer or answer in _PLACEHOLDERS:
                answer_parts: list[str] = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line.startswith("###") or next_line == "---":
                        break
                    if next_line and next_line not in _PLACEHOLDERS:
                        answer_parts.append(next_line)
                    j += 1
                answer = " ".join(answer_parts).strip()

            if answer and answer not in _PLACEHOLDERS:
                results.append((current_title, answer))

        i += 1

    known: dict[str, str] = {}
    custom: dict[str, str] = {}

    for title, answer in results:
        key = _match_known_key(title)
        if key:
            known[key] = answer
        else:
            custom[title] = answer

    result: dict[str, object] = dict(known)
    if custom:
        result["custom"] = custom
    return result


def merge_into_answers_json(autopilot_dir: Path) -> int:
    """
    读取 requirements/INTERVIEW.md，提取技术决策，合并写入 answers.json。
    返回提取到的决策条数（0 表示未提取到任何内容）。
    """
    interview_path = autopilot_dir / "requirements" / "INTERVIEW.md"
    if not interview_path.exists():
        return 0

    extracted = extract_decisions(interview_path.read_text(encoding="utf-8"))
    if not extracted:
        return 0

    answers_path = autopilot_dir / "answers.json"
    existing: dict[str, object] = {}
    if answers_path.exists():
        try:
            existing = json.loads(answers_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    # 合并：顶级 key 直接覆盖；custom 做内层合并
    merged: dict[str, object] = dict(existing)
    for key, val in extracted.items():
        if key == "custom" and isinstance(val, dict):
            existing_custom = merged.get("custom", {})
            if not isinstance(existing_custom, dict):
                existing_custom = {}
            merged["custom"] = {**existing_custom, **val}
        else:
            merged[key] = val

    answers_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return len(extracted)
