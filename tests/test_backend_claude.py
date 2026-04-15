from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopilot.backends.base import ErrorType
from autopilot.backends.claude_code import ClaudeCodeBackend
from autopilot.backends.base import RunContext


def _make_mock_popen(returncode=0, stdout="", stderr=""):
    """Return a Popen mock whose communicate() yields (stdout, stderr)."""
    mock = MagicMock()
    mock.returncode = returncode
    mock.communicate.return_value = (stdout, stderr)
    return mock


@pytest.fixture
def backend():
    return ClaudeCodeBackend()


@pytest.fixture
def ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        project_path=tmp_path,
        docs_path=tmp_path,
        feature=None,
        knowledge_md="",
    )


class TestClassifyError:
    def test_rate_limit_keyword(self, backend):
        assert backend._classify_error(1, "Error: rate_limit exceeded") == ErrorType.rate_limit

    def test_rate_limit_space(self, backend):
        assert backend._classify_error(1, "Hit rate limit, try again") == ErrorType.rate_limit

    def test_rate_limit_429(self, backend):
        assert backend._classify_error(1, "HTTP 429 Too Many Requests") == ErrorType.rate_limit

    def test_quota_exhausted(self, backend):
        assert backend._classify_error(1, "quota exceeded for this month") == ErrorType.quota_exhausted

    def test_billing(self, backend):
        assert backend._classify_error(1, "billing issue detected") == ErrorType.quota_exhausted

    def test_context_overflow_window(self, backend):
        assert backend._classify_error(1, "context window too long") == ErrorType.context_overflow

    def test_context_overflow_length(self, backend):
        assert backend._classify_error(1, "context_length exceeded") == ErrorType.context_overflow

    def test_server_error_500(self, backend):
        assert backend._classify_error(1, "HTTP 500 error") == ErrorType.server_error

    def test_server_error_internal(self, backend):
        assert backend._classify_error(1, "Internal Server Error 500") == ErrorType.server_error

    def test_unknown_fallback(self, backend):
        assert backend._classify_error(1, "something completely unknown happened") == ErrorType.unknown


class TestRunIntegration:
    def test_rate_limit_from_run(self, backend, ctx):
        with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=1, stderr="rate_limit hit")):
            result = backend.run("agent", "prompt", ctx)
        assert not result.success
        assert result.error_type == ErrorType.rate_limit

    def test_quota_from_run(self, backend, ctx):
        with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=1, stderr="quota exceeded")):
            result = backend.run("agent", "prompt", ctx)
        assert result.error_type == ErrorType.quota_exhausted

    def test_context_overflow_from_run(self, backend, ctx):
        with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=1, stderr="context window too long")):
            result = backend.run("agent", "prompt", ctx)
        assert result.error_type == ErrorType.context_overflow

    def test_server_error_from_run(self, backend, ctx):
        with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=1, stderr="Internal Server Error 500")):
            result = backend.run("agent", "prompt", ctx)
        assert result.error_type == ErrorType.server_error

    def test_timeout_from_run(self, backend, ctx):
        mock = _make_mock_popen()
        # First communicate() times out; second (after kill) returns normally
        mock.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="claude", timeout=300),
            ("", ""),
        ]
        with patch("subprocess.Popen", return_value=mock):
            result = backend.run("agent", "prompt", ctx)
        assert not result.success
        assert result.error_type == ErrorType.timeout

    def test_unknown_from_run(self, backend, ctx):
        with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=1, stderr="some weird error")):
            result = backend.run("agent", "prompt", ctx)
        assert result.error_type == ErrorType.unknown

    def test_success_no_error_type(self, backend, ctx):
        with patch("subprocess.Popen", return_value=_make_mock_popen(returncode=0, stdout="done")):
            result = backend.run("agent", "prompt", ctx)
        assert result.success
        assert result.error_type is None

    def test_stop_kills_process(self, backend, ctx):
        mock_proc = _make_mock_popen(returncode=0, stdout="done")
        with patch("subprocess.Popen", return_value=mock_proc):
            backend.stop()  # stop before run — should return stopped result
            result = backend.run("agent", "prompt", ctx)
        assert not result.success
        assert result.error_type == ErrorType.stopped

    def test_oserror_launch_failure(self, backend, ctx):
        with patch("subprocess.Popen", side_effect=OSError("not found")):
            result = backend.run("agent", "prompt", ctx)
        assert not result.success
        assert result.error_type == ErrorType.unknown
