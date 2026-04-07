from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autopilot.backends.base import BackendResult
from autopilot.knowledge.compactor import (
    RECORDS_TO_KEEP,
    KnowledgeCompactor,
    estimate_tokens,
)


# ── estimate_tokens ──────────────────────────────────────────────────────────

def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_estimate_tokens_basic():
    assert estimate_tokens("a" * 400) == 100


# ── needs_compaction ─────────────────────────────────────────────────────────

def test_needs_compaction_false():
    compactor = KnowledgeCompactor()
    assert compactor.needs_compaction("short text") is False


def test_needs_compaction_true():
    compactor = KnowledgeCompactor()
    big_text = "x" * 80_000  # 80_000 // 4 = 20_000 tokens → triggers threshold
    assert compactor.needs_compaction(big_text) is True


# ── compact() helpers ────────────────────────────────────────────────────────

def _make_knowledge_md(n: int) -> str:
    """Generate n records separated by ---."""
    records = [f"记录 {i}\n内容 {i}" for i in range(n)]
    return "\n---\n".join(records)


def _make_backend(success: bool, output: str = "压缩摘要文本") -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = BackendResult(
        success=success,
        output=output,
        duration_seconds=0.1,
        error=None if success else "mock error",
    )
    return backend


# ── compact() with successful backend ────────────────────────────────────────

def test_compact_creates_summary_file(tmp_path: Path):
    compactor = KnowledgeCompactor()
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "knowledge").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()

    knowledge_md = _make_knowledge_md(RECORDS_TO_KEEP + 5)
    backend = _make_backend(success=True, output="这是压缩后的摘要")

    compactor.compact(knowledge_md, backend, autopilot_dir)

    summary_path = autopilot_dir / "knowledge" / "summary.md"
    assert summary_path.exists()


def test_compact_returns_compressed_marker(tmp_path: Path):
    compactor = KnowledgeCompactor()
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "knowledge").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()

    knowledge_md = _make_knowledge_md(RECORDS_TO_KEEP + 5)
    backend = _make_backend(success=True, output="这是压缩后的摘要")

    result = compactor.compact(knowledge_md, backend, autopilot_dir)

    assert "已压缩" in result


def test_compact_calls_backend_once(tmp_path: Path):
    compactor = KnowledgeCompactor()
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "knowledge").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()

    knowledge_md = _make_knowledge_md(RECORDS_TO_KEEP + 5)
    backend = _make_backend(success=True)

    compactor.compact(knowledge_md, backend, autopilot_dir)

    backend.run.assert_called_once()


# ── compact() with failing backend ───────────────────────────────────────────

def test_compact_failure_creates_summary_with_fallback(tmp_path: Path):
    compactor = KnowledgeCompactor()
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "knowledge").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()

    knowledge_md = _make_knowledge_md(RECORDS_TO_KEEP + 5)
    backend = _make_backend(success=False)

    result = compactor.compact(knowledge_md, backend, autopilot_dir)

    summary_path = autopilot_dir / "knowledge" / "summary.md"
    assert summary_path.exists()
    assert isinstance(result, str)  # 不崩溃


def test_compact_failure_contains_fallback_text(tmp_path: Path):
    compactor = KnowledgeCompactor()
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "knowledge").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()

    knowledge_md = _make_knowledge_md(RECORDS_TO_KEEP + 5)
    backend = _make_backend(success=False)

    result = compactor.compact(knowledge_md, backend, autopilot_dir)

    assert "压缩失败" in result


# ── compact() recent records preserved ───────────────────────────────────────

def test_compact_recent_records_in_result(tmp_path: Path):
    compactor = KnowledgeCompactor()
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "knowledge").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()

    total = RECORDS_TO_KEEP + 3
    knowledge_md = _make_knowledge_md(total)
    backend = _make_backend(success=True, output="摘要内容")

    result = compactor.compact(knowledge_md, backend, autopilot_dir)

    # 最近 RECORDS_TO_KEEP 条的最后一条一定在结果中
    last_record = f"记录 {total - 1}"
    assert last_record in result


# ── compact() when records ≤ RECORDS_TO_KEEP ─────────────────────────────────

def test_compact_no_llm_when_few_records(tmp_path: Path):
    compactor = KnowledgeCompactor()
    autopilot_dir = tmp_path / ".autopilot"
    (autopilot_dir / "knowledge").mkdir(parents=True)
    (autopilot_dir / "docs").mkdir()

    knowledge_md = _make_knowledge_md(RECORDS_TO_KEEP)  # 恰好等于阈值
    backend = _make_backend(success=True)

    compactor.compact(knowledge_md, backend, autopilot_dir)

    # 不该调 LLM
    backend.run.assert_not_called()
    # summary.md 仍然应该写入
    assert (autopilot_dir / "knowledge" / "summary.md").exists()
