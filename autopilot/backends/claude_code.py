from __future__ import annotations

from autopilot.backends.base import BackendBase, RunContext


class ClaudeCodeBackend(BackendBase):
    def _cli_name(self) -> str:
        return "claude"

    def _build_cmd(self, agent_name: str, prompt: str, ctx: RunContext) -> list[str]:
        return [
            "claude",
            "-p",
            "--dangerously-skip-permissions",
            "--agent", agent_name,
            prompt,
        ]
