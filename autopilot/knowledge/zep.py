from __future__ import annotations

import httpx

ZEP_BASE = "https://api.getzep.com/api/v2"


class ZepKnowledge:
    def __init__(self, api_key: str, graph_id: str) -> None:
        self.api_key = api_key
        self.graph_id = graph_id
        self._headers = {"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json"}

    def write(self, content: str) -> None:
        httpx.post(
            f"{ZEP_BASE}/graph/{self.graph_id}/memory",
            headers=self._headers,
            json={"content": content},
            timeout=30,
        )

    def recall(self, query: str, limit: int = 5) -> str:
        resp = httpx.post(
            f"{ZEP_BASE}/graph/{self.graph_id}/search",
            headers=self._headers,
            json={"query": query, "limit": limit},
            timeout=30,
        )
        results = resp.json().get("results", [])
        return "\n".join(r["content"] for r in results)
