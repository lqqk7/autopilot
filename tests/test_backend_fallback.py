from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from autopilot.backends.base import BackendResult, ErrorType
from autopilot.pipeline.context import Phase, PipelineState


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_autopilot_dir(tmp_path: Path, fallback_backends: list[str] | None = None) -> Path:
    import toml

    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "requirements").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()
    (autopilot_dir / "knowledge" / "bugs").mkdir(parents=True)
    (autopilot_dir / "knowledge" / "decisions").mkdir()
    (tmp_path / "logs").mkdir()

    config = {"autopilot": {"backend": "claude", "fallback_backends": fallback_backends or []}}
    (autopilot_dir / "config.toml").write_text(toml.dumps(config), encoding="utf-8")
    return autopilot_dir


def _make_engine(tmp_path: Path, backend: MagicMock, fallback_backends: list[str] | None = None):
    from autopilot.pipeline.engine import PipelineEngine

    _make_autopilot_dir(tmp_path, fallback_backends)
    engine = PipelineEngine(project_path=tmp_path, backend=backend)
    return engine


_SUCCESS_OUTPUT = (
    '```json autopilot-result\n'
    '{"status":"success","summary":"ok","artifacts":[],"issues":[],"next_hint":null}\n'
    '```'
)


# ─── _load_fallback_backends ─────────────────────────────────────────────────

def test_load_fallback_backends_empty_list(tmp_path: Path) -> None:
    mock_backend = MagicMock()
    engine = _make_engine(tmp_path, mock_backend, fallback_backends=[])
    assert engine._fallback_backends == []


def test_load_fallback_backends_no_config(tmp_path: Path) -> None:
    from autopilot.pipeline.engine import PipelineEngine

    (tmp_path / ".autopilot").mkdir()
    (tmp_path / "logs").mkdir()
    mock_backend = MagicMock()
    engine = PipelineEngine(project_path=tmp_path, backend=mock_backend)
    assert engine._fallback_backends == []


def test_load_fallback_backends_with_valid_names(tmp_path: Path) -> None:
    mock_backend = MagicMock()
    engine = _make_engine(tmp_path, mock_backend, fallback_backends=["codex", "opencode"])
    assert len(engine._fallback_backends) == 2


# ─── _try_switch_backend ─────────────────────────────────────────────────────

def test_try_switch_returns_false_when_no_fallbacks(tmp_path: Path) -> None:
    mock_backend = MagicMock()
    engine = _make_engine(tmp_path, mock_backend, fallback_backends=[])
    assert engine._try_switch_backend(ErrorType.rate_limit) is False


def test_try_switch_changes_backend(tmp_path: Path) -> None:
    mock_backend = MagicMock()
    engine = _make_engine(tmp_path, mock_backend, fallback_backends=["codex"])
    original = engine.backend
    switched = engine._try_switch_backend(ErrorType.quota_exhausted)
    assert switched is True
    assert engine.backend is not original
    assert engine._backend_switches == 1


def test_try_switch_exhausted_returns_false(tmp_path: Path) -> None:
    mock_backend = MagicMock()
    engine = _make_engine(tmp_path, mock_backend, fallback_backends=["codex"])
    engine._try_switch_backend(ErrorType.rate_limit)   # switch once → codex
    switched_again = engine._try_switch_backend(ErrorType.rate_limit)  # no more
    assert switched_again is False


def test_try_switch_sends_telegram_notification(tmp_path: Path) -> None:
    mock_backend = MagicMock()
    engine = _make_engine(tmp_path, mock_backend, fallback_backends=["codex"])
    mock_notifier = MagicMock()
    engine.notifier = mock_notifier
    engine._try_switch_backend(ErrorType.quota_exhausted)
    mock_notifier.send_backend_switch.assert_called_once()
    args = mock_notifier.send_backend_switch.call_args[0]
    assert args[2] == "quota_exhausted"


# ─── run_phase fallback integration ──────────────────────────────────────────

def test_run_phase_switches_backend_on_quota_exhausted(tmp_path: Path) -> None:
    """quota_exhausted → switch backend → success on second backend."""
    from autopilot.backends.base import BackendBase
    from autopilot.pipeline.engine import PipelineEngine

    autopilot_dir = _make_autopilot_dir(tmp_path, fallback_backends=["codex"])
    PipelineState(phase=Phase.DOC_GEN).save(autopilot_dir / "state.json")

    primary = MagicMock(spec=BackendBase)
    primary.run.return_value = BackendResult(
        success=False, output="", duration_seconds=1.0,
        error="quota", error_type=ErrorType.quota_exhausted
    )

    fallback = MagicMock(spec=BackendBase)
    fallback.run.return_value = BackendResult(
        success=True, output=_SUCCESS_OUTPUT, duration_seconds=1.0
    )

    engine = PipelineEngine(project_path=tmp_path, backend=primary)
    engine._fallback_backends = [fallback]

    state = PipelineState(phase=Phase.DOC_GEN)
    result = engine.run_phase(state)

    assert result is True
    assert engine._backend_switches == 1
    assert engine.backend is fallback
    fallback.run.assert_called_once()


def test_run_phase_switches_backend_on_rate_limit_after_local_retries(tmp_path: Path) -> None:
    """rate_limit exhausts local retries → switch backend → success."""
    from autopilot.backends.base import BackendBase
    from autopilot.pipeline.engine import PipelineEngine

    autopilot_dir = _make_autopilot_dir(tmp_path, fallback_backends=["opencode"])
    PipelineState(phase=Phase.DOC_GEN).save(autopilot_dir / "state.json")

    primary = MagicMock(spec=BackendBase)
    primary.run.return_value = BackendResult(
        success=False, output="", duration_seconds=0.1,
        error="rate limit", error_type=ErrorType.rate_limit
    )

    fallback = MagicMock(spec=BackendBase)
    fallback.run.return_value = BackendResult(
        success=True, output=_SUCCESS_OUTPUT, duration_seconds=1.0
    )

    engine = PipelineEngine(project_path=tmp_path, backend=primary)
    engine._fallback_backends = [fallback]

    state = PipelineState(phase=Phase.DOC_GEN)

    with patch("autopilot.pipeline.engine.time.sleep"):
        result = engine.run_phase(state)

    assert result is True
    assert engine._backend_switches == 1


def test_run_phase_no_fallback_available_increments_phase_retries(tmp_path: Path) -> None:
    """quota_exhausted with no fallbacks → phase_retries += 1, return False."""
    from autopilot.backends.base import BackendBase
    from autopilot.pipeline.engine import PipelineEngine

    autopilot_dir = _make_autopilot_dir(tmp_path, fallback_backends=[])
    PipelineState(phase=Phase.DOC_GEN).save(autopilot_dir / "state.json")

    primary = MagicMock(spec=BackendBase)
    primary.run.return_value = BackendResult(
        success=False, output="", duration_seconds=0.1,
        error="quota", error_type=ErrorType.quota_exhausted
    )

    engine = PipelineEngine(project_path=tmp_path, backend=primary)
    state = PipelineState(phase=Phase.DOC_GEN)
    result = engine.run_phase(state)

    assert result is False
    assert state.phase_retries == 1


# ─── run_result backend_switches field ───────────────────────────────────────

def test_run_result_records_backend_switches_zero_on_clean_run(tmp_path: Path) -> None:
    """run_result.json has backend_switches field; zero when no switch occurred."""
    from autopilot.pipeline.engine import PipelineEngine

    autopilot_dir = _make_autopilot_dir(tmp_path, fallback_backends=["codex"])
    PipelineState(phase=Phase.DONE).save(autopilot_dir / "state.json")

    mock_backend = MagicMock()
    engine = PipelineEngine(project_path=tmp_path, backend=mock_backend)
    engine.run()

    data = json.loads((autopilot_dir / "run_result.json").read_text())
    assert "backend_switches" in data
    assert data["backend_switches"] == 0


# ─── init_project config ─────────────────────────────────────────────────────

def test_init_project_includes_fallback_backends_in_config(tmp_path: Path) -> None:
    import toml
    from autopilot.init_project import init_project

    init_project(tmp_path, backend="claude")
    config = toml.loads((tmp_path / ".autopilot" / "config.toml").read_text())
    assert "fallback_backends" in config["autopilot"]
    assert config["autopilot"]["fallback_backends"] == []
