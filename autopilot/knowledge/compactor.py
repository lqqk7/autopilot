from __future__ import annotations

import logging
from pathlib import Path

from autopilot.backends.base import BackendBase, RunContext

logger = logging.getLogger(__name__)

KNOWLEDGE_TOKEN_THRESHOLD = 20_000
COMPACTION_RESERVE_TOKENS = 4_000
RECORDS_TO_KEEP = 10


def estimate_tokens(text: str) -> int:
    """保守估算：~4 chars per token（混合中英文）。"""
    return len(text) // 4


_PROMPT_TEMPLATE = (
    "你是知识库压缩助手。以下是项目开发过程中积累的历史经验记录（较早部分）。\n\n"
    "请压缩为不超过 500 字的摘要，重点保留：\n"
    "- 验证过的 bug 原因和修复方案\n"
    "- 重要的技术决策及原因\n"
    "- 可复用的解决模式\n\n"
    "直接输出摘要内容，不需要任何额外格式或说明。\n\n---\n\n{old_content}"
)


def _build_compaction_prompt(old_content: str) -> str:
    return _PROMPT_TEMPLATE.format(old_content=old_content)


class KnowledgeCompactor:
    def needs_compaction(self, knowledge_md: str) -> bool:
        return estimate_tokens(knowledge_md) >= KNOWLEDGE_TOKEN_THRESHOLD

    def get_summary_path(self, knowledge_dir: Path) -> Path:
        return knowledge_dir / "summary.md"

    def compact(
        self,
        knowledge_md: str,
        backend: BackendBase,
        autopilot_dir: Path,
    ) -> str:
        try:
            records = [r.strip() for r in knowledge_md.split("---") if r.strip()]

            if len(records) <= RECORDS_TO_KEEP:
                self.get_summary_path(autopilot_dir / "knowledge").write_text(
                    knowledge_md, encoding="utf-8"
                )
                return knowledge_md

            old_records = records[:-RECORDS_TO_KEEP]
            recent_records = records[-RECORDS_TO_KEEP:]
            old_content = "\n---\n".join(old_records)

            prompt = _build_compaction_prompt(old_content)
            ctx = RunContext(
                project_path=autopilot_dir.parent,
                docs_path=autopilot_dir / "docs",
                feature=None,
                knowledge_md="",
                answers_md="",
            )
            result = backend.run("compact_knowledge", prompt, ctx)
            if result.success:
                summary_text = result.output.strip()
            else:
                logger.warning("知识压缩 LLM 调用失败: %s", result.error)
                summary_text = "[压缩失败，跳过摘要]"

            compressed = (
                "## 历史经验（已压缩）\n\n"
                f"### 摘要\n\n{summary_text}\n\n---\n\n"
                + "\n---\n".join(recent_records)
            )
            summary_path = self.get_summary_path(autopilot_dir / "knowledge")
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(compressed, encoding="utf-8")
            return compressed

        except Exception as exc:
            logger.warning("知识压缩异常，返回原始内容: %s", exc)
            return knowledge_md
