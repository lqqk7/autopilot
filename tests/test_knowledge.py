import pytest
from pathlib import Path
from autopilot.knowledge.local import LocalKnowledge


def test_local_knowledge_write_bug(tmp_path: Path):
    kb = LocalKnowledge(knowledge_dir=tmp_path / "knowledge")
    kb.write_bug(
        title="jwt-expiry",
        cause="token not refreshed",
        fix="add refresh logic",
        files=["src/auth.py"],
    )
    bugs = list((tmp_path / "knowledge" / "bugs").glob("*.md"))
    assert len(bugs) == 1
    content = bugs[0].read_text()
    assert "jwt-expiry" in content
    assert "token not refreshed" in content


def test_local_knowledge_write_decision(tmp_path: Path):
    kb = LocalKnowledge(knowledge_dir=tmp_path / "knowledge")
    kb.write_decision(title="chose-prisma", reason="better TypeScript support")
    decisions = list((tmp_path / "knowledge" / "decisions").glob("*.md"))
    assert len(decisions) == 1


def test_local_knowledge_read_all(tmp_path: Path):
    kb = LocalKnowledge(knowledge_dir=tmp_path / "knowledge")
    kb.write_bug("bug1", "cause1", "fix1", [])
    kb.write_decision("dec1", "reason1")
    content = kb.read_all()
    assert "bug1" in content
    assert "dec1" in content


def test_local_knowledge_read_all_excludes_summary(tmp_path: Path):
    kb = LocalKnowledge(knowledge_dir=tmp_path / "knowledge")
    kb.write_bug("real-bug", "cause", "fix", [])
    (tmp_path / "knowledge" / "summary.md").write_text("compacted summary")
    content = kb.read_all()
    assert "real-bug" in content
    assert "compacted summary" not in content
