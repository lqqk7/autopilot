"""v0.8: Cross-project Knowledge Graph.

Nodes: Bug, Decision, Pattern (stored in ~/.autopilot/knowledge/)
Edges: caused_by, fixed_by, applies_to, decided_in, pattern (relations.json)

Vector search is optional — requires AUTOPILOT_EMBED_API_KEY env var and
a base URL. Falls back to keyword search when not configured.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_RELATIONS_FILE = "relations.json"


class KnowledgeNode(BaseModel):
    id: str
    category: str   # bugs | decisions | patterns | learnings
    title: str
    file_path: str  # relative to knowledge base dir
    tags: list[str] = Field(default_factory=list)
    created_at: str = ""


class KnowledgeEdge(BaseModel):
    from_id: str
    to_id: str
    relation: str   # caused_by | fixed_by | applies_to | decided_in | pattern


class KnowledgeGraph:
    """Maintains a graph of knowledge nodes and their relations."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._relations_path = base_dir / _RELATIONS_FILE
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: list[KnowledgeEdge] = []
        self._load()
        self._embed_client = _EmbedClient.from_env()

    def _load(self) -> None:
        if not self._relations_path.exists():
            return
        try:
            data = json.loads(self._relations_path.read_text(encoding="utf-8"))
            for n in data.get("nodes", []):
                node = KnowledgeNode.model_validate(n)
                self._nodes[node.id] = node
            for e in data.get("edges", []):
                self._edges.append(KnowledgeEdge.model_validate(e))
        except Exception as exc:
            logger.warning("Failed to load knowledge graph: %s", exc)

    def _save(self) -> None:
        data = {
            "nodes": [n.model_dump() for n in self._nodes.values()],
            "edges": [e.model_dump() for e in self._edges],
        }
        self._relations_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_node(self, node: KnowledgeNode) -> None:
        self._nodes[node.id] = node
        self._save()

    def add_edge(self, from_id: str, to_id: str, relation: str) -> None:
        edge = KnowledgeEdge(from_id=from_id, to_id=to_id, relation=relation)
        # Avoid duplicates
        if not any(e.from_id == from_id and e.to_id == to_id and e.relation == relation for e in self._edges):
            self._edges.append(edge)
            self._save()

    def get_related(self, node_id: str) -> list[tuple[KnowledgeEdge, KnowledgeNode]]:
        """Return all directly related nodes (outgoing edges)."""
        results = []
        for edge in self._edges:
            if edge.from_id == node_id and edge.to_id in self._nodes:
                results.append((edge, self._nodes[edge.to_id]))
        return results

    def search_nodes(self, query: str, top_n: int = 5) -> list[KnowledgeNode]:
        """Keyword + optional vector search. Returns top-N relevant nodes."""
        if self._embed_client.is_available():
            return self._vector_search(query, top_n)
        return self._keyword_search(query, top_n)

    def _keyword_search(self, query: str, top_n: int) -> list[KnowledgeNode]:
        q = query.lower()
        scored: list[tuple[int, KnowledgeNode]] = []
        for node in self._nodes.values():
            text = f"{node.title} {' '.join(node.tags)}".lower()
            score = sum(text.count(w) for w in q.split())
            if score > 0:
                scored.append((score, node))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in scored[:top_n]]

    def _vector_search(self, query: str, top_n: int) -> list[KnowledgeNode]:
        """Embed query and compare against node embeddings (cached on disk)."""
        try:
            query_vec = self._embed_client.embed(query)
        except Exception as exc:
            logger.warning("Vector embedding failed, falling back to keyword: %s", exc)
            return self._keyword_search(query, top_n)

        scored: list[tuple[float, KnowledgeNode]] = []
        for node in self._nodes.values():
            node_vec = self._get_or_create_embedding(node)
            if node_vec:
                sim = _cosine_sim(query_vec, node_vec)
                scored.append((sim, node))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in scored[:top_n]]

    def _get_or_create_embedding(self, node: KnowledgeNode) -> list[float] | None:
        """Load cached embedding or generate and cache it."""
        cache_path = self.base_dir / ".embeddings" / f"{node.id}.json"
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        try:
            file_path = self.base_dir / node.file_path
            text = node.title
            if file_path.exists():
                text = file_path.read_text(encoding="utf-8")[:1000]
            vec = self._embed_client.embed(text)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(vec), encoding="utf-8")
            return vec
        except Exception as exc:
            logger.debug("Failed to generate embedding for %s: %s", node.id, exc)
            return None

    def build_context(self, node_ids: list[str], depth: int = 1) -> str:
        """Build a markdown context block for the given nodes and their relations."""
        visited: set[str] = set()
        lines: list[str] = ["## Knowledge Graph Context\n"]

        def _expand(nid: str, current_depth: int) -> None:
            if nid in visited or current_depth > depth:
                return
            visited.add(nid)
            node = self._nodes.get(nid)
            if not node:
                return
            lines.append(f"### [{node.category}] {node.title}")
            related = self.get_related(nid)
            if related:
                for edge, related_node in related:
                    lines.append(f"  - **{edge.relation}** → {related_node.title}")
                    _expand(related_node.id, current_depth + 1)
            lines.append("")

        for nid in node_ids:
            _expand(nid, 0)
        return "\n".join(lines) if len(lines) > 1 else ""

    def all_nodes(self) -> list[KnowledgeNode]:
        return list(self._nodes.values())

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)


# ── Embedding Client ──────────────────────────────────────────────────────────

class _EmbedClient:
    """Optional vector embedding client. No-op when API key is not configured."""

    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        self._api_key = api_key
        self._base_url = base_url or "https://api.openai.com/v1"

    @classmethod
    def from_env(cls) -> "_EmbedClient":
        return cls(
            api_key=os.environ.get("AUTOPILOT_EMBED_API_KEY", ""),
            base_url=os.environ.get("AUTOPILOT_EMBED_BASE_URL", ""),
        )

    def is_available(self) -> bool:
        return bool(self._api_key)

    def embed(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        if not self._api_key:
            raise RuntimeError("No embedding API key configured")
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self._base_url}/embeddings",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"input": text[:8000], "model": model},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
