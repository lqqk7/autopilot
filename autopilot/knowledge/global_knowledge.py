"""v0.5: System-level persistent memory across projects.

Knowledge lives at ~/.autopilot/knowledge/{bugs,decisions,patterns,learnings}/.
On new project start, top-N relevant memories are injected into prompts.

v0.8: Each entry is registered in KnowledgeGraph for relation tracking.
"""
from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path


_GLOBAL_DIR = Path.home() / ".autopilot" / "knowledge"

_CATEGORIES = ("bugs", "decisions", "patterns", "learnings")


class GlobalKnowledge:
    """Cross-project knowledge store at ~/.autopilot/knowledge/."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or _GLOBAL_DIR
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for cat in _CATEGORIES:
            (self.base_dir / cat).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slug(title: str) -> str:
        return (re.sub(r"[^a-z0-9_-]+", "-", title.lower()).strip("-") or "entry")[:50]

    def write(self, category: str, title: str, content: str, tags: list[str] | None = None) -> Path:
        """Write a knowledge entry. Returns the path written."""
        if category not in _CATEGORIES:
            raise ValueError(f"Unknown category {category!r}. Use one of {_CATEGORIES}")
        today = date.today().isoformat()
        slug = self._slug(title)
        path = self.base_dir / category / f"{today}-{slug}.md"
        path.write_text(f"# {title}\n\n**日期**: {today}\n\n{content}\n", encoding="utf-8")
        # v0.8: register in knowledge graph
        self._register_graph_node(category, title, path, tags or [])
        return path

    def _register_graph_node(self, category: str, title: str, path: Path, tags: list[str]) -> None:
        try:
            from autopilot.knowledge.graph import KnowledgeGraph, KnowledgeNode
            graph = KnowledgeGraph(self.base_dir)
            node_id = f"{category}-{self._slug(title)}-{uuid.uuid4().hex[:6]}"
            rel_path = str(path.relative_to(self.base_dir))
            node = KnowledgeNode(
                id=node_id,
                category=category,
                title=title,
                file_path=rel_path,
                tags=tags,
                created_at=date.today().isoformat(),
            )
            graph.add_node(node)
        except Exception:
            pass  # graph registration is best-effort

    def write_bug(self, title: str, cause: str, fix: str, files: list[str] | None = None, tags: list[str] | None = None) -> Path:
        content = f"**原因**: {cause}\n\n**修复**: {fix}\n\n**涉及文件**: {', '.join(files or []) or '无'}"
        return self.write("bugs", title, content, tags=tags)

    def write_decision(self, title: str, reason: str, context: str = "", tags: list[str] | None = None) -> Path:
        content = f"**原因**: {reason}" + (f"\n\n**背景**: {context}" if context else "")
        return self.write("decisions", title, content, tags=tags)

    def write_pattern(self, title: str, description: str, example: str = "", tags: list[str] | None = None) -> Path:
        content = f"**描述**: {description}" + (f"\n\n**示例**: {example}" if example else "")
        return self.write("patterns", title, content, tags=tags)

    def write_learning(self, title: str, summary: str, tags: list[str] | None = None) -> Path:
        return self.write("learnings", title, f"**总结**: {summary}", tags=tags)

    def search(self, keywords: list[str], top_n: int = 5) -> list[tuple[str, str]]:
        """Keyword-based search. Returns list of (category/filename, content) sorted by relevance."""
        if not keywords:
            return []
        kw_lower = [k.lower() for k in keywords]
        scored: list[tuple[int, str, str]] = []
        for cat in _CATEGORIES:
            cat_dir = self.base_dir / cat
            for f in sorted(cat_dir.glob("*.md"), reverse=True):  # newest first
                try:
                    text = f.read_text(encoding="utf-8")
                except OSError:
                    continue
                score = sum(text.lower().count(kw) for kw in kw_lower)
                if score > 0:
                    scored.append((score, f"{cat}/{f.name}", text))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(label, text) for _, label, text in scored[:top_n]]

    def read_relevant(self, keywords: list[str], top_n: int = 5) -> str:
        """Return a formatted markdown block of the most relevant memories."""
        results = self.search(keywords, top_n)
        if not results:
            return ""
        parts = ["## 全局知识库（历史经验）\n"]
        for label, text in results:
            parts.append(f"### {label}\n{text}")
        return "\n---\n".join(parts)

    def read_all(self) -> str:
        """Return all global knowledge entries as a formatted markdown string."""
        parts: list[str] = []
        for cat in _CATEGORIES:
            cat_dir = self.base_dir / cat
            for f in sorted(cat_dir.glob("*.md")):
                try:
                    parts.append(f.read_text(encoding="utf-8"))
                except OSError:
                    pass
        if not parts:
            return ""
        return "## 全局知识库\n\n" + "\n---\n".join(parts)
