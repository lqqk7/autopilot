from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopilot.backends.base import BackendResult, ErrorType
from autopilot.pipeline.context import Phase, PipelineState
from autopilot.pipeline.engine import PipelineEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUCCESS_OUTPUT = (
    '```json autopilot-result\n'
    '{"status":"success","summary":"done","artifacts":[],"issues":[],"next_hint":null}\n'
    '```'
)


def _make_engine(tmp_path: Path, backend: MagicMock) -> PipelineEngine:
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "requirements").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()
    (autopilot_dir / "knowledge" / "bugs").mkdir(parents=True)
    (autopilot_dir / "knowledge" / "decisions").mkdir()
    return PipelineEngine(project_path=tmp_path, backend=backend)


def _fail_result(error_type: ErrorType) -> BackendResult:
    return BackendResult(
        success=False,
        output="",
        duration_seconds=0.1,
        error="simulated error",
        error_type=error_type,
    )


def _success_result() -> BackendResult:
    return BackendResult(success=True, output=_SUCCESS_OUTPUT, duration_seconds=0.1)


# ---------------------------------------------------------------------------
# 1–3: _exponential_backoff
# ---------------------------------------------------------------------------

def test_backoff_attempt_0():
    assert PipelineEngine._exponential_backoff(0) == 10.0


def test_backoff_attempt_1():
    assert PipelineEngine._exponential_backoff(1) == 20.0


def test_backoff_attempt_10_capped():
    assert PipelineEngine._exponential_backoff(10) == 120.0


# ---------------------------------------------------------------------------
# 4–9: _handle_error
# ---------------------------------------------------------------------------

@pytest.fixture
def bare_engine(tmp_path: Path) -> PipelineEngine:
    mock_backend = MagicMock()
    return _make_engine(tmp_path, mock_backend)


def test_handle_error_rate_limit_attempt_0(bare_engine: PipelineEngine):
    result = _fail_result(ErrorType.rate_limit)
    should_retry, wait = bare_engine._handle_error(result, retry_count=0)
    assert should_retry is True
    assert wait == 10.0


def test_handle_error_rate_limit_attempt_3(bare_engine: PipelineEngine):
    result = _fail_result(ErrorType.rate_limit)
    should_retry, wait = bare_engine._handle_error(result, retry_count=3)
    assert should_retry is False
    assert wait == 0.0


def test_handle_error_quota_exhausted(bare_engine: PipelineEngine):
    result = _fail_result(ErrorType.quota_exhausted)
    should_retry, wait = bare_engine._handle_error(result, retry_count=0)
    assert should_retry is False
    assert wait == 0.0


def test_handle_error_context_overflow(bare_engine: PipelineEngine):
    result = _fail_result(ErrorType.context_overflow)
    should_retry, wait = bare_engine._handle_error(result, retry_count=0)
    assert should_retry is False
    assert wait == 0.0


def test_handle_error_parse_error_attempt_2(bare_engine: PipelineEngine):
    result = _fail_result(ErrorType.parse_error)
    should_retry, wait = bare_engine._handle_error(result, retry_count=2)
    assert should_retry is True
    assert wait == 0.0


def test_handle_error_parse_error_attempt_3(bare_engine: PipelineEngine):
    result = _fail_result(ErrorType.parse_error)
    should_retry, wait = bare_engine._handle_error(result, retry_count=3)
    assert should_retry is False
    assert wait == 0.0


# ---------------------------------------------------------------------------
# 10: run_phase with rate_limit ×2 then success → True, sleep called
# ---------------------------------------------------------------------------

def test_run_phase_rate_limit_retry_then_success(tmp_path: Path):
    mock_backend = MagicMock()
    mock_backend.run.side_effect = [
        _fail_result(ErrorType.rate_limit),
        _fail_result(ErrorType.rate_limit),
        _success_result(),
    ]
    engine = _make_engine(tmp_path, mock_backend)
    state = PipelineState(phase=Phase.CODE)

    with patch("autopilot.pipeline.engine.time.sleep") as mock_sleep:
        result = engine.run_phase(state)

    assert result is True
    assert mock_sleep.call_count == 2
    assert mock_backend.run.call_count == 3


# ---------------------------------------------------------------------------
# 11: run_phase with quota_exhausted → False, phase_retries == 1
# ---------------------------------------------------------------------------

def test_run_phase_quota_exhausted(tmp_path: Path):
    mock_backend = MagicMock()
    mock_backend.run.return_value = _fail_result(ErrorType.quota_exhausted)
    engine = _make_engine(tmp_path, mock_backend)
    state = PipelineState(phase=Phase.CODE)

    with patch("autopilot.pipeline.engine.time.sleep"):
        result = engine.run_phase(state)

    assert result is False
    assert state.phase_retries == 1
    assert mock_backend.run.call_count == 1


# ---------------------------------------------------------------------------
# 12: run_phase with parse_error ×3 → False, backend.run called 3 times
# ---------------------------------------------------------------------------

def test_run_phase_parse_error_exhausted(tmp_path: Path):
    mock_backend = MagicMock()
    # local_retry goes 0, 1, 2 → all retry; at 3 _handle_error returns False
    # so backend.run is called 4 times total
    mock_backend.run.side_effect = [
        _fail_result(ErrorType.parse_error),
        _fail_result(ErrorType.parse_error),
        _fail_result(ErrorType.parse_error),
        _fail_result(ErrorType.parse_error),
    ]
    engine = _make_engine(tmp_path, mock_backend)
    state = PipelineState(phase=Phase.CODE)

    with patch("autopilot.pipeline.engine.time.sleep"):
        result = engine.run_phase(state)

    assert result is False
    # initial call + 3 retries = 4 calls
    assert mock_backend.run.call_count == 4
    assert state.phase_retries == 1


# ---------------------------------------------------------------------------
# 13: run_phase with timeout → False, notifier.send_timeout called
# ---------------------------------------------------------------------------

def test_run_phase_timeout_notifier_called(tmp_path: Path):
    mock_backend = MagicMock()
    mock_backend.run.return_value = _fail_result(ErrorType.timeout)
    engine = _make_engine(tmp_path, mock_backend)
    engine.notifier = MagicMock()
    state = PipelineState(phase=Phase.CODE)

    with patch("autopilot.pipeline.engine.time.sleep"):
        result = engine.run_phase(state)

    assert result is False
    engine.notifier.send_timeout.assert_called_once_with(
        phase=Phase.CODE.value, retry=1
    )
