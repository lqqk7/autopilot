import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from autopilot.knowledge.local import LocalKnowledge
from autopilot.knowledge.zep import ZepKnowledge


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


def test_zep_write_calls_api():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        zep = ZepKnowledge(api_key="test-key", graph_id="project.test.shared")
        zep.write("Test memory content")
        assert mock_post.called
        call_url = mock_post.call_args[0][0] if mock_post.call_args[0] else str(mock_post.call_args)
        assert "getzep.com" in call_url


def test_zep_recall_calls_api():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"results": [{"content": "recalled memory"}]},
        )
        zep = ZepKnowledge(api_key="test-key", graph_id="project.test.shared")
        result = zep.recall("jwt token")
        assert "recalled memory" in result
