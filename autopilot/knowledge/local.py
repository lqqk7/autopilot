from __future__ import annotations

from datetime import date
from pathlib import Path


class LocalKnowledge:
    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        (self.knowledge_dir / "bugs").mkdir(parents=True, exist_ok=True)
        (self.knowledge_dir / "decisions").mkdir(parents=True, exist_ok=True)

    def write_bug(self, title: str, cause: str, fix: str, files: list[str]) -> None:
        today = date.today().isoformat()
        slug = title.lower().replace(" ", "-")[:50]
        path = self.knowledge_dir / "bugs" / f"{today}-{slug}.md"
        content = f"# {title}\n\n**日期**：{today}\n\n**原因**：{cause}\n\n**修复**：{fix}\n\n**涉及文件**：{', '.join(files) or '无'}\n"
        path.write_text(content, encoding="utf-8")

    def write_decision(self, title: str, reason: str) -> None:
        today = date.today().isoformat()
        slug = title.lower().replace(" ", "-")[:50]
        path = self.knowledge_dir / "decisions" / f"{today}-{slug}.md"
        content = f"# {title}\n\n**日期**：{today}\n\n**原因**：{reason}\n"
        path.write_text(content, encoding="utf-8")

    def read_all(self) -> str:
        parts: list[str] = ["## 历史经验\n"]
        for md in sorted(self.knowledge_dir.rglob("*.md")):
            parts.append(md.read_text(encoding="utf-8"))
        return "\n---\n".join(parts)
