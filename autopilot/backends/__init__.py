from autopilot.backends.base import BackendBase, BackendResult, RunContext
from autopilot.backends.claude_code import ClaudeCodeBackend
from autopilot.backends.codex import CodexBackend
from autopilot.backends.opencode import OpenCodeBackend


def get_backend(name: str) -> BackendBase:
    backends = {
        "claude": ClaudeCodeBackend,
        "codex": CodexBackend,
        "opencode": OpenCodeBackend,
    }
    if name not in backends:
        raise ValueError(f"Unknown backend: {name!r}. Choose from {list(backends)}")
    return backends[name]()


__all__ = [
    "BackendBase",
    "BackendResult",
    "RunContext",
    "ClaudeCodeBackend",
    "CodexBackend",
    "OpenCodeBackend",
    "get_backend",
]
