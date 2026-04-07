"""Tests for PipelineEngine context compaction integration (Task 3, v0.3)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopilot.backends.base import BackendBase, BackendResult, ErrorType, RunContext
from autopilot.pipeline.context import Phase, PipelineState
from autopilot.pipeline.engine import PipelineEngine

_SUCCESS_OUTPUT = (
    '```json autopilot-result\n'
    '{"status":"success","summary":"done","artifacts":[],"issues":[],"next_hint":null}\n'
    '```'
)


def _make_dirs(tmp_path: Path) -> Path:
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "requirements").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()
    (autopilot_dir / "knowledge" / "bugs").mkdir(parents=True)
    (autopilot_dir / "knowledge" / "decisions").mkdir()
    (tmp_path / "logs").mkdir()
    return autopilot_dir


def _make_engine(tmp_path: Path, backend: MagicMock) -> PipelineEngine:
    _make_dirs(tmp_path)
    return PipelineEngine(project_path=tmp_path, backend=backend)


# ─── 测试1: 主动压缩（knowledge_md 超过阈值） ─────────────────────────────────

def test_proactive_compaction_triggered(tmp_path: Path) -> None:
    """needs_compaction=True 时，run_phase 在进入循环前主动压缩，backend 收到的是压缩后内容。"""
    mock_backend = MagicMock(spec=BackendBase)
    mock_backend.run.return_value = BackendResult(
        success=True, output=_SUCCESS_OUTPUT, duration_seconds=1.0
    )
    engine = _make_engine(tmp_path, mock_backend)

    state = PipelineState(phase=Phase.DOC_GEN)

    with patch("autopilot.knowledge.compactor.KnowledgeCompactor") as mock_cls:
        mock_compactor = MagicMock()
        mock_cls.return_value = mock_compactor
        mock_compactor.needs_compaction.return_value = True
        mock_compactor.compact.return_value = "compressed"

        result = engine.run_phase(state)

    assert result is True
    # compact 被调用了一次（主动压缩）
    mock_compactor.compact.assert_called_once()
    # engine 计数增加
    assert engine._compaction_count == 1
    # backend.run 被调用时，ctx.knowledge_md 是 compressed
    call_args = mock_backend.run.call_args
    ctx_arg: RunContext = call_args[0][2]
    assert ctx_arg.knowledge_md == "compressed"


# ─── 测试2: 不触发主动压缩 ────────────────────────────────────────────────────

def test_proactive_compaction_not_triggered(tmp_path: Path) -> None:
    """needs_compaction=False 时，compact 不被调用，compaction_count 保持 0。"""
    mock_backend = MagicMock(spec=BackendBase)
    mock_backend.run.return_value = BackendResult(
        success=True, output=_SUCCESS_OUTPUT, duration_seconds=1.0
    )
    engine = _make_engine(tmp_path, mock_backend)

    state = PipelineState(phase=Phase.DOC_GEN)

    with patch("autopilot.knowledge.compactor.KnowledgeCompactor") as mock_cls:
        mock_compactor = MagicMock()
        mock_cls.return_value = mock_compactor
        mock_compactor.needs_compaction.return_value = False

        result = engine.run_phase(state)

    assert result is True
    mock_compactor.compact.assert_not_called()
    assert engine._compaction_count == 0


# ─── 测试3: context_overflow 触发强制压缩并重试 ───────────────────────────────

def test_context_overflow_forces_compaction_and_retries(tmp_path: Path) -> None:
    """第一次 backend.run 返回 context_overflow，压缩后第二次成功，不计入 phase_retries。"""
    overflow_result = BackendResult(
        success=False,
        output="",
        duration_seconds=1.0,
        error="context overflow",
        error_type=ErrorType.context_overflow,
    )
    success_result = BackendResult(
        success=True, output=_SUCCESS_OUTPUT, duration_seconds=1.0
    )
    mock_backend = MagicMock(spec=BackendBase)
    mock_backend.run.side_effect = [overflow_result, success_result]

    engine = _make_engine(tmp_path, mock_backend)
    state = PipelineState(phase=Phase.DOC_GEN)

    with patch("autopilot.knowledge.compactor.KnowledgeCompactor") as mock_cls:
        mock_compactor = MagicMock()
        mock_cls.return_value = mock_compactor
        mock_compactor.needs_compaction.return_value = False
        mock_compactor.compact.return_value = "compressed"

        result = engine.run_phase(state)

    assert result is True
    assert mock_backend.run.call_count == 2
    assert engine._compaction_count == 1
    # context_overflow 不计入 phase_retries
    assert state.phase_retries == 0


# ─── 测试4: run() 后 run_result.json 的 compactions 字段正确 ──────────────────

def test_run_result_compactions_field(tmp_path: Path) -> None:
    """run() 完成后，run_result.json 中 compactions 字段等于实际压缩次数。"""
    autopilot_dir = _make_dirs(tmp_path)

    # 直接从 DONE 状态启动，循环立即退出
    state = PipelineState(phase=Phase.DONE)
    state.save(autopilot_dir / "state.json")

    mock_backend = MagicMock(spec=BackendBase)
    engine = PipelineEngine(project_path=tmp_path, backend=mock_backend)
    # 手动设置 compaction count
    engine._compaction_count = 3

    engine.run()

    data = json.loads((autopilot_dir / "run_result.json").read_text())
    # run() 内部会重置为 0，因为从 DONE 状态进入时不会执行任何 run_phase
    # 所以这里应该是 0（reset 在 run() 开头）
    assert data["compactions"] == 0


def test_run_result_compactions_nonzero_after_actual_compaction(tmp_path: Path) -> None:
    """经过真实压缩的 run()，run_result.json 的 compactions 非零。"""
    autopilot_dir = _make_dirs(tmp_path)

    # 从 DOC_GEN 开始，单次成功后进入 PLANNING（但 planning_complete 返回 False 继续循环）
    # 简单起见：模拟一次 DOC_GEN 成功后直接结束（通过 mock advance 到 DONE）
    state = PipelineState(phase=Phase.DOC_GEN)
    state.save(autopilot_dir / "state.json")

    mock_backend = MagicMock(spec=BackendBase)
    mock_backend.run.return_value = BackendResult(
        success=True, output=_SUCCESS_OUTPUT, duration_seconds=1.0
    )
    engine = PipelineEngine(project_path=tmp_path, backend=mock_backend)

    with (
        patch("autopilot.knowledge.compactor.KnowledgeCompactor") as mock_cls,
        patch.object(engine, "advance", return_value=Phase.DONE),
    ):
        mock_compactor = MagicMock()
        mock_cls.return_value = mock_compactor
        mock_compactor.needs_compaction.return_value = True
        mock_compactor.compact.return_value = "compressed"

        engine.run()

    data = json.loads((autopilot_dir / "run_result.json").read_text())
    assert data["compactions"] == 1
