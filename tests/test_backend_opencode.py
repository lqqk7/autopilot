from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopilot.backends.base import ErrorType
from autopilot.backends.opencode import OpenCodeBackend


def _make_mock_popen(returncode=0, stdout="", stderr=""):
    mock = MagicMock()
    mock.returncode = returncode
    mock.communicate.return_value = (stdout, stderr)
    return mock


@pytest.fixture
def backend() -> OpenCodeBackend:
    return OpenCodeBackend()


@pytest.fixture
def ctx():
    ctx = MagicMock()
    ctx.project_path = Path("/tmp")
    return ctx


# --- _classify_error tests ---

def test_classify_rate_limit(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "rate_limit exceeded") == ErrorType.rate_limit


def test_classify_too_many_requests(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "Too Many Requests") == ErrorType.rate_limit


def test_classify_429(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "HTTP 429 error") == ErrorType.rate_limit


def test_classify_insufficient_quota(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "insufficient_quota") == ErrorType.quota_exhausted


def test_classify_quota(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "Your quota has been exceeded") == ErrorType.quota_exhausted


def test_classify_maximum_context_length(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "maximum context length reached") == ErrorType.context_overflow


def test_classify_context_overflow(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "context overflow detected") == ErrorType.context_overflow


def test_classify_500(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "500 internal server error") == ErrorType.server_error


def test_classify_internal_server(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "Internal Server Error") == ErrorType.server_error


def test_classify_unknown(backend: OpenCodeBackend) -> None:
    assert backend._classify_error(1, "some unrecognized error") == ErrorType.unknown


# --- run() integration tests ---

def test_run_timeout_returns_error_type(backend: OpenCodeBackend, ctx) -> None:
    mock = _make_mock_popen()
    mock.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd="opencode", timeout=300),
        ("", ""),
    ]
    with patch("subprocess.Popen", return_value=mock):
        result = backend.run("coder", "do something", ctx)
    assert result.success is False
    assert result.error_type == ErrorType.timeout


def test_run_nonzero_no_keyword_returns_unknown(backend: OpenCodeBackend, ctx) -> None:
    with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=1, stderr="something went wrong")):
        result = backend.run("coder", "do something", ctx)
    assert result.success is False
    assert result.error_type == ErrorType.unknown


def test_run_success_no_error_type(backend: OpenCodeBackend, ctx) -> None:
    with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=0, stdout="done")):
        result = backend.run("coder", "do something", ctx)
    assert result.success is True
    assert result.error_type is None
