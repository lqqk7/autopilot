from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from autopilot.pipeline.context import Feature


class ErrorType(str, Enum):
    rate_limit = "rate_limit"
    quota_exhausted = "quota_exhausted"
    server_error = "server_error"
    context_overflow = "context_overflow"
    timeout = "timeout"
    parse_error = "parse_error"
    unknown = "unknown"


@dataclass
class RunContext:
    project_path: Path
    docs_path: Path
    feature: Feature | None
    knowledge_md: str
    answers_md: str = ""
    extra_files: list[Path] = field(default_factory=list)


@dataclass
class BackendResult:
    success: bool
    output: str
    duration_seconds: float
    error: str | None = None
    error_type: ErrorType | None = None


class BackendBase(ABC):
    TIMEOUT_SECONDS: int = 300

    @abstractmethod
    def _build_cmd(self, agent_name: str, prompt: str, ctx: RunContext) -> list[str]:
        """Build the subprocess command list."""

    def _classify_error(self, returncode: int, stderr: str) -> ErrorType:
        """Map returncode/stderr to ErrorType. Subclasses override for CLI-specific patterns."""
        text = stderr.lower()
        if "rate_limit" in text or "rate limit" in text or "429" in text:
            return ErrorType.rate_limit
        if "quota" in text or "billing" in text or "insufficient_quota" in text:
            return ErrorType.quota_exhausted
        if "context" in text and ("too long" in text or "length" in text or "overflow" in text):
            return ErrorType.context_overflow
        if "maximum context length" in text or "context_length_exceeded" in text:
            return ErrorType.context_overflow
        if "500" in text or "502" in text or "503" in text or "server_error" in text:
            return ErrorType.server_error
        return ErrorType.unknown

    def run(self, agent_name: str, prompt: str, ctx: RunContext) -> BackendResult:
        cmd = self._build_cmd(agent_name, prompt, ctx)
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT_SECONDS,
                cwd=ctx.project_path,
            )
            duration = time.monotonic() - start
            if proc.returncode != 0:
                error_type = self._classify_error(proc.returncode, proc.stderr)
                return BackendResult(
                    success=False,
                    output=proc.stdout + proc.stderr,
                    duration_seconds=duration,
                    error=f"exit code {proc.returncode}",
                    error_type=error_type,
                )
            return BackendResult(success=True, output=proc.stdout, duration_seconds=duration)
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            return BackendResult(
                success=False,
                output="",
                duration_seconds=duration,
                error=f"timeout after {self.TIMEOUT_SECONDS}s",
                error_type=ErrorType.timeout,
            )

    def is_available(self) -> bool:
        import shutil
        return shutil.which(self._cli_name()) is not None

    @abstractmethod
    def _cli_name(self) -> str:
        """Return the CLI executable name."""
