from __future__ import annotations

import subprocess
import threading
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
    stopped = "stopped"


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

    def __init__(self, model: str = "", allow_dangerous: bool = True) -> None:
        self.model = model              # empty = use the tool's own default
        self.allow_dangerous = allow_dangerous
        self._current_proc: subprocess.Popen[str] | None = None
        self._proc_lock = threading.Lock()
        self._stopped = False

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

    def run(self, agent_name: str, prompt: str, ctx: RunContext, timeout: int | None = None) -> BackendResult:
        if self._stopped:
            return BackendResult(
                success=False, output="", duration_seconds=0,
                error="backend stopped", error_type=ErrorType.stopped,
            )

        cmd = self._build_cmd(agent_name, prompt, ctx)
        effective_timeout = timeout if timeout is not None else self.TIMEOUT_SECONDS
        start = time.monotonic()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                cwd=ctx.project_path,
            )
            with self._proc_lock:
                self._current_proc = proc

            try:
                stdout, stderr = proc.communicate(timeout=effective_timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                duration = time.monotonic() - start
                return BackendResult(
                    success=False, output="", duration_seconds=duration,
                    error=f"timeout after {effective_timeout}s",
                    error_type=ErrorType.timeout,
                )
            finally:
                with self._proc_lock:
                    self._current_proc = None

            duration = time.monotonic() - start

            # Treat SIGKILL (-9) exit as a stopped result, not a real error
            if proc.returncode == -9 or self._stopped:
                return BackendResult(
                    success=False, output="", duration_seconds=duration,
                    error="backend stopped", error_type=ErrorType.stopped,
                )

            if proc.returncode != 0:
                error_type = self._classify_error(proc.returncode, stderr)
                return BackendResult(
                    success=False,
                    output=stdout + stderr,
                    duration_seconds=duration,
                    error=f"exit code {proc.returncode}",
                    error_type=error_type,
                )
            return BackendResult(success=True, output=stdout, duration_seconds=duration)

        except OSError as exc:
            duration = time.monotonic() - start
            return BackendResult(
                success=False, output="", duration_seconds=duration,
                error=f"failed to launch backend ({cmd[0]}): {exc}",
                error_type=ErrorType.unknown,
            )

    def stop(self) -> None:
        """Kill the running subprocess immediately. Safe to call from any thread."""
        self._stopped = True
        with self._proc_lock:
            proc = self._current_proc
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass

    def reset(self) -> None:
        """Clear the stopped flag so the backend can be reused (e.g. after /resume)."""
        self._stopped = False

    def is_available(self) -> bool:
        import shutil
        return shutil.which(self._cli_name()) is not None

    @abstractmethod
    def _cli_name(self) -> str:
        """Return the CLI executable name."""
