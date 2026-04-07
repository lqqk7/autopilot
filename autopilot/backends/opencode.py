from __future__ import annotations

from autopilot.backends.base import BackendBase, RunContext


class OpenCodeBackend(BackendBase):
    def _cli_name(self) -> str:
        return "opencode"

    def _build_cmd(self, agent_name: str, prompt: str, ctx: RunContext) -> list[str]:
        return [
            "opencode", "run",
            "--agent", f"autopilot-{agent_name}",
            prompt,
        ]
