from __future__ import annotations

from autopilot.backends.base import BackendBase, ErrorType, RunContext


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

    def _classify_error(self, returncode: int, stderr: str) -> ErrorType:
        text = stderr.lower()
        if "rate limit" in text or "ratelimited" in text or "429" in text:
            return ErrorType.rate_limit
        if "quota exceeded" in text or "insufficient_quota" in text:
            return ErrorType.quota_exhausted
        if "context_length_exceeded" in text or "maximum context" in text:
            return ErrorType.context_overflow
        if "500" in text or "502" in text or "503" in text or "server error" in text:
            return ErrorType.server_error
        return super()._classify_error(returncode, stderr)
