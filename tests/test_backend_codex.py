from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopilot.backends.base import ErrorType
from autopilot.backends.codex import CodexBackend


def _make_mock_popen(returncode=0, stdout="", stderr=""):
    mock = MagicMock()
    mock.returncode = returncode
    mock.communicate.return_value = (stdout, stderr)
    return mock


@pytest.fixture
def backend() -> CodexBackend:
    return CodexBackend()


@pytest.fixture
def ctx():
    ctx = MagicMock()
    ctx.project_path = Path("/tmp")
    return ctx


# _classify_error 单元测试

def test_classify_rate_limit(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "rate limit exceeded") == ErrorType.rate_limit


def test_classify_rate_limited_camel(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "rateLimited by server") == ErrorType.rate_limit


def test_classify_429(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "HTTP 429 Too Many Requests") == ErrorType.rate_limit


def test_classify_quota_exceeded(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "quota exceeded") == ErrorType.quota_exhausted


def test_classify_insufficient_quota(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "insufficient_quota for this model") == ErrorType.quota_exhausted


def test_classify_context_length_exceeded(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "context_length_exceeded") == ErrorType.context_overflow


def test_classify_maximum_context(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "maximum context reached") == ErrorType.context_overflow


def test_classify_503_server_error(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "503 server error") == ErrorType.server_error


def test_classify_500(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "HTTP 500 Internal Server Error") == ErrorType.server_error


def test_classify_unknown_nonzero(backend: CodexBackend) -> None:
    assert backend._classify_error(1, "something went wrong") == ErrorType.unknown


# run() 集成测试

def test_run_timeout_sets_error_type(backend: CodexBackend, ctx) -> None:
    mock = _make_mock_popen()
    mock.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd="codex", timeout=300),
        ("", ""),
    ]
    with patch("subprocess.Popen", return_value=mock):
        result = backend.run("agent", "prompt", ctx)
    assert result.success is False
    assert result.error_type == ErrorType.timeout


def test_run_success_no_error_type(backend: CodexBackend, ctx) -> None:
    with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=0, stdout="done")):
        result = backend.run("agent", "prompt", ctx)
    assert result.success is True
    assert result.error_type is None


def test_run_nonzero_unknown(backend: CodexBackend, ctx) -> None:
    with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=1, stderr="something went wrong")):
        result = backend.run("agent", "prompt", ctx)
    assert result.success is False
    assert result.error_type == ErrorType.unknown
