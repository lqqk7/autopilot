from __future__ import annotations

from autopilot.backends.base import BackendBase, ErrorType, RunContext


class OpenCodeBackend(BackendBase):
    def _cli_name(self) -> str:
        return "opencode"

    def _build_cmd(self, agent_name: str, prompt: str, ctx: RunContext) -> list[str]:
        return [
            "opencode", "run",
            "--agent", f"autopilot-{agent_name}",
            prompt,
        ]

    def _classify_error(self, returncode: int, stderr: str) -> ErrorType:
        text = stderr.lower()
        if "rate_limit" in text or "too many requests" in text or "429" in text:
            return ErrorType.rate_limit
        if "insufficient_quota" in text or "quota" in text:
            return ErrorType.quota_exhausted
        if "maximum context length" in text or "context overflow" in text:
            return ErrorType.context_overflow
        if "500" in text or "502" in text or "503" in text or "internal server" in text:
            return ErrorType.server_error
        return super()._classify_error(returncode, stderr)
