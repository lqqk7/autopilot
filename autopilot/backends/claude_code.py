from __future__ import annotations

from autopilot.backends.base import BackendBase, ErrorType, RunContext


class ClaudeCodeBackend(BackendBase):
    def _cli_name(self) -> str:
        return "claude"

    def _build_cmd(self, agent_name: str, prompt: str, ctx: RunContext) -> list[str]:
        cmd = ["claude", "-p"]
        if self.allow_dangerous:
            cmd.append("--dangerously-skip-permissions")
        cmd += ["--agent", agent_name]
        if self.model:
            cmd += ["--model", self.model]
        cmd.append(prompt)
        return cmd

    def _classify_error(self, returncode: int, stderr: str) -> ErrorType:
        text = stderr.lower()
        if "rate_limit" in text or "rate limit" in text or "429" in text:
            return ErrorType.rate_limit
        if "quota" in text or "billing" in text:
            return ErrorType.quota_exhausted
        if "context window" in text or "context_length" in text or "too long" in text:
            return ErrorType.context_overflow
        if "500" in text or "502" in text or "503" in text or "internal server error" in text:
            return ErrorType.server_error
        return super()._classify_error(returncode, stderr)
