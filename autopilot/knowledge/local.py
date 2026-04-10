from __future__ import annotations

import re
from datetime import date
from pathlib import Path


class LocalKnowledge:
    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir
        self._cache_snapshot: list[tuple[str, float]] = []
        self._cache_content: str = ""
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        (self.knowledge_dir / "bugs").mkdir(parents=True, exist_ok=True)
        (self.knowledge_dir / "decisions").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slug(title: str) -> str:
        return (re.sub(r"[^a-z0-9_-]+", "-", title.lower()).strip("-") or "entry")[:50]

    def write_bug(self, title: str, cause: str, fix: str, files: list[str]) -> None:
        today = date.today().isoformat()
        slug = self._slug(title)
        path = self.knowledge_dir / "bugs" / f"{today}-{slug}.md"
        content = f"# {title}\n\n**日期**：{today}\n\n**原因**：{cause}\n\n**修复**：{fix}\n\n**涉及文件**：{', '.join(files) or '无'}\n"
        path.write_text(content, encoding="utf-8")

    def write_decision(self, title: str, reason: str) -> None:
        today = date.today().isoformat()
        slug = self._slug(title)
        path = self.knowledge_dir / "decisions" / f"{today}-{slug}.md"
        content = f"# {title}\n\n**日期**：{today}\n\n**原因**：{reason}\n"
        path.write_text(content, encoding="utf-8")

    def read_all(self) -> str:
        # Exclude summary.md — it's a compacted snapshot, including it would cause
        # the compactor to re-ingest its own output on every pass (content bloat loop).
        files = [f for f in sorted(self.knowledge_dir.rglob("*.md")) if f.name != "summary.md"]
        snapshot = [(str(f), f.stat().st_mtime) for f in files]
        if snapshot == self._cache_snapshot:
            return self._cache_content
        parts: list[str] = ["## 历史经验\n"]
        for f, _ in snapshot:
            parts.append(Path(f).read_text(encoding="utf-8"))
        content = "\n---\n".join(parts)
        self._cache_snapshot = snapshot
        self._cache_content = content
        return content
