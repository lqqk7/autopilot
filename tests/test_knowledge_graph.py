"""Tests for v0.8 KnowledgeGraph."""
from __future__ import annotations

from pathlib import Path

import pytest

from autopilot.knowledge.graph import KnowledgeGraph, KnowledgeNode, _cosine_sim


@pytest.fixture()
def graph(tmp_path: Path) -> KnowledgeGraph:
    return KnowledgeGraph(tmp_path / "knowledge")


def _make_node(id: str, category: str = "bugs", title: str = "Test Node") -> KnowledgeNode:
    return KnowledgeNode(id=id, category=category, title=title, file_path=f"{category}/{id}.md")


def test_empty_graph(graph: KnowledgeGraph) -> None:
    assert graph.node_count() == 0
    assert graph.edge_count() == 0


def test_add_node(graph: KnowledgeGraph) -> None:
    node = _make_node("bug-001", "bugs", "Redis timeout")
    graph.add_node(node)
    assert graph.node_count() == 1
    assert graph.all_nodes()[0].id == "bug-001"


def test_add_edge(graph: KnowledgeGraph) -> None:
    graph.add_node(_make_node("bug-001", "bugs", "Redis timeout"))
    graph.add_node(_make_node("dec-001", "decisions", "Configure connection pool"))
    graph.add_edge("bug-001", "dec-001", "fixed_by")
    assert graph.edge_count() == 1


def test_no_duplicate_edges(graph: KnowledgeGraph) -> None:
    graph.add_node(_make_node("a"))
    graph.add_node(_make_node("b"))
    graph.add_edge("a", "b", "fixed_by")
    graph.add_edge("a", "b", "fixed_by")  # duplicate
    assert graph.edge_count() == 1


def test_get_related(graph: KnowledgeGraph) -> None:
    graph.add_node(_make_node("bug-001", "bugs", "Timeout"))
    graph.add_node(_make_node("dec-001", "decisions", "Set timeout=30"))
    graph.add_node(_make_node("pat-001", "patterns", "Timeout config"))
    graph.add_edge("bug-001", "dec-001", "fixed_by")
    graph.add_edge("bug-001", "pat-001", "applies_to")
    related = graph.get_related("bug-001")
    assert len(related) == 2
    relations = {edge.relation for edge, _ in related}
    assert "fixed_by" in relations
    assert "applies_to" in relations


def test_keyword_search(graph: KnowledgeGraph) -> None:
    graph.add_node(_make_node("bug-redis", "bugs", "Redis connection pool exhausted"))
    graph.add_node(_make_node("dec-postgres", "decisions", "Use PostgreSQL for ACID"))
    results = graph.search_nodes("redis connection")
    assert len(results) == 1
    assert results[0].id == "bug-redis"


def test_keyword_search_top_n(graph: KnowledgeGraph) -> None:
    for i in range(10):
        graph.add_node(_make_node(f"node-{i}", "bugs", f"Bug {i} with common keyword"))
    results = graph.search_nodes("common keyword", top_n=3)
    assert len(results) <= 3


def test_build_context_single_node(graph: KnowledgeGraph) -> None:
    graph.add_node(_make_node("bug-001", "bugs", "Timeout issue"))
    ctx = graph.build_context(["bug-001"])
    assert "Knowledge Graph Context" in ctx
    assert "Timeout issue" in ctx


def test_build_context_with_relations(graph: KnowledgeGraph) -> None:
    graph.add_node(_make_node("bug-001", "bugs", "Auth failure"))
    graph.add_node(_make_node("dec-001", "decisions", "Use JWT"))
    graph.add_edge("bug-001", "dec-001", "fixed_by")
    ctx = graph.build_context(["bug-001"])
    assert "fixed_by" in ctx
    assert "Use JWT" in ctx


def test_persistence(tmp_path: Path) -> None:
    base = tmp_path / "knowledge"
    g1 = KnowledgeGraph(base)
    g1.add_node(_make_node("x-001", "patterns", "Retry logic"))
    g1.add_node(_make_node("x-002", "decisions", "Exponential backoff"))
    g1.add_edge("x-001", "x-002", "decided_in")

    g2 = KnowledgeGraph(base)
    assert g2.node_count() == 2
    assert g2.edge_count() == 1


def test_cosine_sim_identical() -> None:
    v = [1.0, 0.0, 0.0]
    assert abs(_cosine_sim(v, v) - 1.0) < 1e-6


def test_cosine_sim_orthogonal() -> None:
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_sim(a, b)) < 1e-6


def test_cosine_sim_empty() -> None:
    assert _cosine_sim([], []) == 0.0


def test_global_knowledge_registers_in_graph(tmp_path: Path) -> None:
    from autopilot.knowledge.global_knowledge import GlobalKnowledge
    gk = GlobalKnowledge(base_dir=tmp_path / "knowledge")
    gk.write_bug("Test bug", cause="missing check", fix="add guard", tags=["python", "null"])
    graph = KnowledgeGraph(tmp_path / "knowledge")
    assert graph.node_count() == 1
    nodes = graph.all_nodes()
    assert nodes[0].category == "bugs"
    assert "python" in nodes[0].tags
