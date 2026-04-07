from __future__ import annotations

import json
from pathlib import Path

from autopilot.backends.base import RunContext

AGENTS_DIR = Path(__file__).parent

OUTPUT_PROTOCOL = """
---

## 输出协议

完成工作后，**必须**在输出末尾输出以下 JSON 块，不得省略、不得修改格式：

```json autopilot-result
{
  "status": "success",
  "summary": "一句话描述做了什么",
  "artifacts": [],
  "issues": [],
  "next_hint": null
}
```

status 可选值：`success` | `failure` | `partial`
"""


def get_agent_prompt_path(agent_name: str) -> Path:
    path = AGENTS_DIR / f"{agent_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Agent prompt not found: {path}")
    return path


LABEL_MAP: dict[str, str] = {
    "database": "数据库",
    "orm": "ORM",
    "auth_strategy": "认证方案",
    "deployment_target": "部署目标",
    "testing_framework": "测试框架",
}


class AgentLoader:
    @staticmethod
    def _load_answers_md(autopilot_dir: Path) -> str:
        """读取 answers.json，格式化为 ## 预设决策 markdown 块。"""
        answers_path = autopilot_dir / "answers.json"
        if not answers_path.exists():
            return ""
        try:
            data = json.loads(answers_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ""
        if not data:
            return ""
        lines = ["## 预设决策", "遇到以下技术选型时，直接使用预设值，无需询问："]
        for key, val in data.items():
            if key == "custom" and isinstance(val, dict):
                for k, v in val.items():
                    lines.append(f"- {k}：{v}")
            else:
                label = LABEL_MAP.get(key, key)
                lines.append(f"- {label}：{val}")
        return "\n".join(lines)

    def build_system_prompt(self, agent_name: str, ctx: RunContext) -> str:
        base = get_agent_prompt_path(agent_name).read_text(encoding="utf-8")
        injections: list[str] = []

        if ctx.feature:
            injections.append(
                f"## 当前任务\n**Feature ID:** {ctx.feature.id}\n**Title:** {ctx.feature.title}\n**Phase:** {ctx.feature.phase}"
            )

        summary_path = ctx.project_path / ".autopilot" / "knowledge" / "summary.md"
        if summary_path.exists():
            summary_content = summary_path.read_text(encoding="utf-8")
            if summary_content:
                injections.append(summary_content)
        elif ctx.knowledge_md:
            injections.append(ctx.knowledge_md)

        answers_md = self._load_answers_md(ctx.project_path / ".autopilot")
        if answers_md:
            injections.append(answers_md)

        injections.append(OUTPUT_PROTOCOL)
        return base + "\n\n" + "\n\n".join(injections)
