from __future__ import annotations

from autopilot.backends.base import BackendBase, RunContext


class CodexBackend(BackendBase):
    def _cli_name(self) -> str:
        return "codex"

    def _build_cmd(self, agent_name: str, prompt: str, ctx: RunContext) -> list[str]:
        return [
            "codex",
            "--approval-mode", "full-auto",
            "--system-prompt", agent_name,
            prompt,
        ]
