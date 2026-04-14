import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from autopilot.backends.base import BackendResult, RunContext
from autopilot.backends.claude_code import ClaudeCodeBackend
from autopilot.backends.codex import CodexBackend
from autopilot.backends.opencode import OpenCodeBackend


@pytest.fixture
def ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        project_path=tmp_path,
        docs_path=tmp_path / ".autopilot" / "docs",
        feature=None,
        knowledge_md="",
        extra_files=[],
    )


def _make_mock_process(stdout: str, returncode: int = 0, stderr: str = ""):
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = stderr
    mock.returncode = returncode
    return mock


def test_claude_code_run_success(ctx: RunContext):
    with patch("subprocess.run", return_value=_make_mock_process("output text")) as mock_run:
        backend = ClaudeCodeBackend()
        result = backend.run("coder", "do the thing", ctx)
    assert result.success is True
    assert result.output == "output text"
    cmd = mock_run.call_args[0][0]
    assert "claude" in cmd
    assert "--dangerously-skip-permissions" in cmd


def test_codex_run_success(ctx: RunContext):
    with patch("subprocess.run", return_value=_make_mock_process("output")) as mock_run:
        backend = CodexBackend()
        result = backend.run("coder", "do the thing", ctx)
    assert result.success is True
    cmd = mock_run.call_args[0][0]
    assert "codex" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd


def test_opencode_run_success(ctx: RunContext):
    with patch("subprocess.run", return_value=_make_mock_process("output")) as mock_run:
        backend = OpenCodeBackend()
        result = backend.run("coder", "do the thing", ctx)
    assert result.success is True
    cmd = mock_run.call_args[0][0]
    assert "opencode" in cmd


def test_backend_run_failure(ctx: RunContext):
    with patch("subprocess.run", return_value=_make_mock_process("error", returncode=1)):
        backend = ClaudeCodeBackend()
        result = backend.run("coder", "do the thing", ctx)
    assert result.success is False


def test_backend_factory():
    from autopilot.backends import get_backend
    assert isinstance(get_backend("claude"), ClaudeCodeBackend)
    assert isinstance(get_backend("codex"), CodexBackend)
    assert isinstance(get_backend("opencode"), OpenCodeBackend)
    with pytest.raises(ValueError):
        get_backend("unknown")
