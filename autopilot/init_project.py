from __future__ import annotations

from pathlib import Path

import toml

from autopilot.pipeline.context import Phase, PipelineState


def init_project(project_path: Path, backend: str) -> None:
    autopilot_dir = project_path / ".autopilot"

    for subdir in [
        "requirements",
        "docs/00-overview",
        "docs/01-requirements",
        "docs/02-research",
        "docs/03-design",
        "docs/04-development",
        "docs/05-testing",
        "docs/06-api",
        "docs/07-deployment",
        "docs/08-operations",
        "docs/09-product",
        "docs/archive",
        "knowledge/bugs",
        "knowledge/decisions",
    ]:
        (autopilot_dir / subdir).mkdir(parents=True, exist_ok=True)

    config_path = autopilot_dir / "config.toml"
    if not config_path.exists():
        config = {
            "autopilot": {
                "backend": backend,
                "max_parallel": 1,
                "parallel_backends": [],
                "fallback_backends": [],
            }
        }
        config_path.write_text(toml.dumps(config), encoding="utf-8")

    state_path = autopilot_dir / "state.json"
    if not state_path.exists():
        PipelineState(phase=Phase.INIT).save(state_path)

    answers_path = autopilot_dir / "answers.json"
    if not answers_path.exists():
        answers_path.write_text("{}", encoding="utf-8")

    (project_path / "logs").mkdir(exist_ok=True)

    req_readme = autopilot_dir / "requirements" / "README.md"
    if not req_readme.exists():
        req_readme.write_text(
            "# Requirements\n\n在此目录放置你的需求描述文件（任意格式均可）。\n"
            "建议至少包含：功能描述、目标用户、技术偏好。\n",
            encoding="utf-8",
        )
