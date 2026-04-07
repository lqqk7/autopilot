from __future__ import annotations

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


class AgentLoader:
    def build_system_prompt(self, agent_name: str, ctx: RunContext) -> str:
        base = get_agent_prompt_path(agent_name).read_text(encoding="utf-8")
        injections: list[str] = []

        if ctx.feature:
            injections.append(
                f"## 当前任务\n**Feature ID:** {ctx.feature.id}\n**Title:** {ctx.feature.title}\n**Phase:** {ctx.feature.phase}"
            )

        if ctx.knowledge_md:
            injections.append(ctx.knowledge_md)

        injections.append(OUTPUT_PROTOCOL)
        return base + "\n\n" + "\n\n".join(injections)
