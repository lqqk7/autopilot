import pytest
from pathlib import Path
from autopilot.agents.loader import AgentLoader, get_agent_prompt_path
from autopilot.backends.base import RunContext
from autopilot.pipeline.context import Feature


@pytest.fixture
def ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        project_path=tmp_path,
        docs_path=tmp_path / "docs",
        feature=Feature(id="feat-001", title="用户登录", phase="backend"),
        knowledge_md="## 历史经验\n- JWT token 过期要刷新",
        extra_files=[],
    )


def test_get_agent_prompt_path_exists():
    path = get_agent_prompt_path("coder")
    assert path.exists()
    assert path.suffix == ".md"


def test_get_agent_prompt_path_unknown():
    with pytest.raises(FileNotFoundError):
        get_agent_prompt_path("nonexistent_agent")


def test_loader_build_prompt_injects_knowledge(ctx: RunContext):
    loader = AgentLoader()
    prompt = loader.build_system_prompt("coder", ctx)
    assert "历史经验" in prompt
    assert "JWT token" in prompt


def test_loader_build_prompt_injects_feature(ctx: RunContext):
    loader = AgentLoader()
    prompt = loader.build_system_prompt("coder", ctx)
    assert "用户登录" in prompt


def _make_ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        project_path=tmp_path,
        docs_path=tmp_path / "docs",
        feature=Feature(id="feat-001", title="用户登录", phase="backend"),
        knowledge_md="## 历史经验\n- JWT token 过期要刷新",
        extra_files=[],
    )


def test_summary_md_overrides_knowledge_md(tmp_path: Path):
    summary_dir = tmp_path / ".autopilot" / "knowledge"
    summary_dir.mkdir(parents=True)
    (summary_dir / "summary.md").write_text("## 汇总知识\n- 使用 Redis 缓存", encoding="utf-8")

    ctx = _make_ctx(tmp_path)
    loader = AgentLoader()
    prompt = loader.build_system_prompt("coder", ctx)
    assert "汇总知识" in prompt
    assert "Redis 缓存" in prompt
    assert "JWT token 过期要刷新" not in prompt


def test_no_summary_md_uses_knowledge_md(ctx: RunContext):
    loader = AgentLoader()
    prompt = loader.build_system_prompt("coder", ctx)
    assert "历史经验" in prompt
    assert "JWT token" in prompt


def test_empty_summary_md_not_injected(tmp_path: Path):
    summary_dir = tmp_path / ".autopilot" / "knowledge"
    summary_dir.mkdir(parents=True)
    (summary_dir / "summary.md").write_text("", encoding="utf-8")

    ctx = _make_ctx(tmp_path)
    loader = AgentLoader()
    prompt = loader.build_system_prompt("coder", ctx)
    # summary.md 为空，不注入 summary 内容
    assert "Redis 缓存" not in prompt
    # 也不 fallback 注入 knowledge_md（summary.md 存在即覆盖路径）
    assert "JWT token 过期要刷新" not in prompt
