"""Tests for v0.5 GlobalKnowledge."""
from __future__ import annotations

from pathlib import Path

import pytest

from autopilot.knowledge.global_knowledge import GlobalKnowledge


@pytest.fixture()
def gk(tmp_path: Path) -> GlobalKnowledge:
    return GlobalKnowledge(base_dir=tmp_path / "knowledge")


def test_directories_created(gk: GlobalKnowledge) -> None:
    for cat in ("bugs", "decisions", "patterns", "learnings"):
        assert (gk.base_dir / cat).is_dir()


def test_write_bug(gk: GlobalKnowledge) -> None:
    path = gk.write_bug("NullPointerError", cause="missing check", fix="add guard", files=["a.py"])
    assert path.exists()
    text = path.read_text()
    assert "NullPointerError" in text
    assert "missing check" in text
    assert "add guard" in text
    assert "a.py" in text


def test_write_decision(gk: GlobalKnowledge) -> None:
    path = gk.write_decision("Use JWT", reason="stateless auth")
    assert path.exists()
    assert "Use JWT" in path.read_text()


def test_write_pattern(gk: GlobalKnowledge) -> None:
    path = gk.write_pattern("Repository pattern", description="encapsulate data access")
    assert path.exists()
    assert "Repository pattern" in path.read_text()


def test_write_learning(gk: GlobalKnowledge) -> None:
    path = gk.write_learning("Test first", summary="TDD saves time")
    assert path.exists()
    assert "TDD saves time" in path.read_text()


def test_write_invalid_category(gk: GlobalKnowledge) -> None:
    with pytest.raises(ValueError, match="Unknown category"):
        gk.write("invalid", "title", "content")


def test_search_finds_relevant(gk: GlobalKnowledge) -> None:
    gk.write_bug("Redis timeout", cause="max_connections not set", fix="set max_connections=10")
    gk.write_decision("Use PostgreSQL", reason="ACID compliance for payments")
    results = gk.search(["redis", "connection"])
    assert len(results) == 1
    assert "redis" in results[0][0].lower() or "redis" in results[0][1].lower()


def test_search_returns_top_n(gk: GlobalKnowledge) -> None:
    for i in range(10):
        gk.write_bug(f"Bug {i}", cause="foo", fix="bar")
    results = gk.search(["foo"], top_n=3)
    assert len(results) == 3


def test_search_empty_keywords(gk: GlobalKnowledge) -> None:
    gk.write_bug("Some bug", cause="x", fix="y")
    assert gk.search([]) == []


def test_read_relevant_returns_markdown(gk: GlobalKnowledge) -> None:
    gk.write_bug("Timeout in redis", cause="network", fix="retry")
    result = gk.read_relevant(["redis"])
    assert "全局知识库" in result
    assert "redis" in result.lower() or "Timeout" in result


def test_read_relevant_empty_when_no_match(gk: GlobalKnowledge) -> None:
    gk.write_bug("Postgres deadlock", cause="lock order", fix="reorder")
    result = gk.read_relevant(["totally_unrelated_xyz"])
    assert result == ""


def test_read_all_returns_all_entries(gk: GlobalKnowledge) -> None:
    gk.write_bug("Bug A", cause="a", fix="b")
    gk.write_decision("Decision B", reason="c")
    result = gk.read_all()
    assert "Bug A" in result
    assert "Decision B" in result
    assert "全局知识库" in result


def test_read_all_empty_dir(gk: GlobalKnowledge) -> None:
    assert gk.read_all() == ""
