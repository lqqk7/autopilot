from __future__ import annotations

from pathlib import Path

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
        config_path.write_text(
            f"""[autopilot]
# Primary backend: claude | codex | opencode
backend = "{backend}"

# Max parallel feature workers
max_parallel = 2

# Backends for parallel workers (round-robin). Leave empty to reuse the primary backend.
# Example: parallel_backends = ["claude", "codex"]
parallel_backends = []

# Fallback backends on rate-limit / quota exhausted (tried in order)
fallback_backends = []

# Log level: DEBUG | INFO | WARNING | ERROR
log_level = "INFO"

# Model override — leave empty to use the tool's own default (auto).
# Use the model name exactly as the tool accepts it, e.g.:
#   claude  → "claude-opus-4-6" | "claude-sonnet-4-6" | "sonnet" | "opus"
#   codex   → "o3" | "o4-mini" | "gpt-4o"
#   opencode → "anthropic/claude-opus-4-6" | "openai/o3"
model = ""

# Auto-commit each feature to git after it passes REVIEW.
# Commit message: "feat: [feat-xxx] <feature title>"
# Set to false to disable (e.g. if you manage commits manually).
auto_commit = true

# TUI display language: "en" (default) or "zh" (Chinese).
# Can also be changed at runtime with /lang inside the TUI.
language = "en"


[autopilot.review]
# Review mode:
#   self    — the same backend that wrote the code reviews it (default)
#   cross   — a different backend from the parallel pool reviews it;
#             falls back to "self" when the pool has only one backend
#   backend — a specific named backend always handles review;
#             falls back to "self" if the named backend is unavailable
mode = "self"

# Only used when mode = "backend". Use any backend name: claude | codex | opencode
# backend = "codex"


[autopilot.retries]
# Max FIX-phase attempts per feature before marking it as failed
max_fix_retries = 5
# Max consecutive phase failures before pausing the pipeline for human review
max_phase_retries = 3


[autopilot.timeouts]
# Per-phase timeout in seconds. Increase if your model/network is slow.
interview  = 300    #  5 min — requirement clarification questions
doc_gen    = 600    # 10 min — full technical doc suite (9 docs)
doc_update = 600    # 10 min — incremental doc updates after new requirements
planning   = 600    # 10 min — feature decomposition and task list
delivery   = 600    # 10 min — delivery docs (changelog, release notes, deploy guide)
code       = 1800   # 30 min — feature implementation (largest phase)
test       = 900    # 15 min — test writing and execution
review     = 600    # 10 min — code review
fix        = 900    # 15 min — bug fixing based on test/review feedback
knowledge  = 600    # 10 min — knowledge base update


[autopilot.permissions]
# Allow backends to skip approval prompts and run without sandbox restrictions.
# Default: true — keeps the dev loop uninterrupted (no manual confirmations).
# Set to false in production or security-sensitive environments.
allow_dangerous_permissions = true


[autopilot.notifications]
# Telegram notification switch. Default: disabled.
# When enabled = true, the following environment variables must be set:
#   AUTOPILOT_TELEGRAM_TOKEN   — Bot token obtained from @BotFather
#   AUTOPILOT_TELEGRAM_CHAT_ID — Target chat ID or group/channel ID
# Autopilot sends notifications on: phase complete, human pause, feature done.
enabled = false
""",
            encoding="utf-8",
        )

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
