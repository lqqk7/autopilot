from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from autopilot.pipeline.context import Feature


@dataclass
class RunContext:
    project_path: Path
    docs_path: Path
    feature: Feature | None
    knowledge_md: str
    extra_files: list[Path] = field(default_factory=list)


@dataclass
class BackendResult:
    success: bool
    output: str
    duration_seconds: float
    error: str | None = None


class BackendBase(ABC):
    TIMEOUT_SECONDS: int = 300

    @abstractmethod
    def _build_cmd(self, agent_name: str, prompt: str, ctx: RunContext) -> list[str]:
        """Build the subprocess command list."""

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
                return BackendResult(
                    success=False,
                    output=proc.stdout + proc.stderr,
                    duration_seconds=duration,
                    error=f"exit code {proc.returncode}",
                )
            return BackendResult(success=True, output=proc.stdout, duration_seconds=duration)
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            return BackendResult(
                success=False,
                output="",
                duration_seconds=duration,
                error=f"timeout after {self.TIMEOUT_SECONDS}s",
            )

    def is_available(self) -> bool:
        import shutil
        return shutil.which(self._cli_name()) is not None

    @abstractmethod
    def _cli_name(self) -> str:
        """Return the CLI executable name."""
