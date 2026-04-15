<div align="center">

# 🤖 Autopilot

**AI Coding Automation Engine**

*From requirements to production-ready code — fully automated.*

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![uv](https://img.shields.io/badge/managed%20with-uv-purple)](https://github.com/astral-sh/uv)
[![PyPI](https://img.shields.io/pypi/v/autopilot-ai?color=blue)](https://pypi.org/project/autopilot-ai/)

**[English](#english) · [中文](#chinese)**

</div>

---

<a name="english"></a>

## English

### What is Autopilot?

Autopilot is a Python CLI tool that drives AI coding agents (Claude Code, Codex, OpenCode) through a structured, multi-phase software development pipeline. Drop in your requirements, run `ap run`, and watch it interview you, generate architecture docs, decompose features, write code, write tests, review, fix bugs, and produce delivery documentation — all on autopilot.

**Core capabilities:**
- 🗂 **Full pipeline** — INTERVIEW → DOC_GEN → PLANNING → DEV_LOOP → DOC_UPDATE → KNOWLEDGE → DELIVERY
- ⚡ **Parallel workers** — multiple AI backends developing features concurrently via DAG-aware scheduling
- 🔄 **Cross-review** — one backend writes code, another reviews it
- 🧠 **Knowledge base** — auto-accumulates decisions and bug fixes as Markdown, with periodic compaction
- 📬 **Telegram notifications** — get pinged on phase transitions and human pauses
- ↩️ **Resumable** — crash mid-run? `ap resume` picks up exactly where it left off
- 🔍 **Session recording** — every run is logged as a structured event stream; replay and debug with `ap sessions show`
- 🔖 **Auto git commit** — each feature is automatically committed when it passes REVIEW
- ✅ **Pre-flight check** — `ap check` validates config, backend CLIs, and env vars before you run

---

### Architecture

```
Requirements (.autopilot/requirements/)
        │
        ▼
  INTERVIEW        ← AI clarifies ambiguities, asks questions
        │
        ▼
  DOC_GEN          ← generates 9 technical docs (PRD, architecture, API design…)
        │
        ▼
  PLANNING         ← decomposes into Features with dependency graph (DAG)
        │
        ▼
  DEV_LOOP ──────────────────────────────────────────────────────┐
  │  per feature:  CODE → TEST → REVIEW → FIX (retry loop)      │
  │  parallel workers, DAG-aware scheduling                      │
  └───────────────────── all features done ─────────────────────┘
        │
        ▼
  DOC_UPDATE       ← updates architecture docs post-development
        │
        ▼
  KNOWLEDGE        ← compacts knowledge base (decisions + bugs)
        │
        ▼
  DELIVERY         ← generates product overview, quick-start, user manual
        │
        ▼
     DONE ✅
```

**Human pauses** happen automatically when:
- INTERVIEW needs your answers (requirements clarification)
- A feature exceeds `max_fix_retries`
- Consecutive phase failures exceed `max_phase_retries`
- A DAG deadlock is detected (circular or unsatisfiable dependencies)

---

### Installation

**Requirements:** Python 3.12+, and at least one AI backend installed.

#### Option 1 — pip (recommended)

```bash
pip install autopilot-ai
```

#### Option 2 — uv tool

```bash
uv tool install autopilot-ai
```

Installs the `ap` command globally, isolated — no virtualenv management needed.

#### Option 3 — Install from source (for development / hacking)

```bash
git clone https://github.com/lqqk7/autopilot.git
cd autopilot
uv sync
uv pip install -e .
```

#### Updating

```bash
pip install -U autopilot-ai          # pip
uv tool upgrade autopilot-ai         # uv tool
```

#### Backend prerequisites

| Backend | Requirement |
|---------|-------------|
| `claude` | [Claude Code CLI](https://claude.ai/code) installed and authenticated |
| `codex` | [Codex CLI](https://github.com/openai/codex) installed and authenticated |
| `opencode` | [OpenCode CLI](https://opencode.ai) installed and configured |

---

### Quick Start

#### Step 1 — Initialize your project

Navigate to your project directory (can be empty — Autopilot will build everything from scratch) and run:

```bash
mkdir my-project && cd my-project
ap init --backend claude
```

This automatically creates the `.autopilot/` directory with all required subdirectories, a pre-filled `config.toml`, and initial pipeline state. Nothing else is needed — your project is ready to go.

```
my-project/
└── .autopilot/
    ├── config.toml          ← edit this to configure backends, timeouts, etc.
    ├── requirements/        ← put your requirement files here  ← YOU START HERE
    ├── docs/                ← auto-generated technical docs
    └── knowledge/           ← auto-accumulated decisions and bug fixes
```

---

#### Step 2 — Write your requirements

Drop one or more files into `.autopilot/requirements/`. Autopilot reads **all files** in that directory — split requirements however makes sense for your project.

**Format:** any format AI can read — plain text, Markdown, even bullet points. There is no template to follow.

**What to write:** describe what you want to build in natural language. You don't need to know technical jargon. The more detail the better, but even a rough description is enough to get started.

> 💡 **Not a developer? That's fine.** Just describe what you want your software to do, as if you were explaining it to a friend. Autopilot's INTERVIEW phase will clarify any ambiguities before writing a single line of code.

> 🔧 **Are a developer?** The more precise you are — stack preferences, API design, constraints, performance requirements — the better the output. Write as much as you want, across as many files as needed.

**Examples of valid requirements:**

```
.autopilot/requirements/
├── main.md          ← core feature description
├── auth.md          ← authentication details
└── api-notes.txt    ← additional API constraints
```

A simple `main.md` might look like:

```markdown
I want to build a task management web app.

Features:
- Users can register and log in
- Users can create, edit, delete and complete tasks
- Tasks have title, description, due date, and priority (high/medium/low)
- Users can filter tasks by status and priority
- Each user only sees their own tasks

Tech preferences: Python backend, REST API, any database is fine.
```

That's all. Autopilot will ask clarifying questions in the INTERVIEW phase if anything is unclear.

---

#### Step 3 — Run the pipeline

**Option A — Full-screen TUI (recommended, v0.3+)**

```bash
autopilot
```

Opens a full-screen interactive terminal dashboard. Type `/run` to start the pipeline, `/help` to see all commands.

```
┌─ autopilot v0.3.6  │  ~/my-project  │  2026-04-16  04:35:22 ─────────────────┐
│ DEV_LOOP  via claude  │  features 3/10  │  workers 2/2  │  01:42              │
│ model: default  │  review: self  │  log: INFO  │  max-workers: 2              │
├─ feat-001 ─────────────────────────────────────────────────────────────────────┤
│  ⏳  feat-001  Auth module            CODE      claude   –                    │
│  🔄  feat-002  Payment gateway        TEST      claude   –                    │
│  ✅  feat-003  User profile           done      claude   –                    │
├─ log ──────────────────────────────────────────────────────────────────────────┤
│ 04:35  [feat-002]  Starting phase TEST (backend: claude)                       │
│ 04:35  [feat-001]  Agent reported status=success                               │
└> /run_────────────────────────────────────────────────────────────────────────┘
```

**The INTERVIEW pause**

When you type `/run`, Autopilot starts with the INTERVIEW phase — the AI reads your requirements and generates clarifying questions. Once INTERVIEW completes, the TUI displays a clear prompt directly in the dashboard:

```
📋  INTERVIEW complete — fill in your answers to continue

  File:   .autopilot/requirements/INTERVIEW.md

  Steps:
    1. Open the file above in your editor
    2. Fill in the answers to each question
    3. Type /resume here to continue

```

No need to hunt through terminal stdout — the full guidance is right in front of you. Fill in `.autopilot/requirements/INTERVIEW.md`, then type `/resume`. The pipeline continues: **DOC_GEN → PLANNING → DEV_LOOP**.

**Slash commands:**

| Command | Description |
|---------|-------------|
| `/init [--backend claude\|codex\|opencode]` | Initialize autopilot in the current directory |
| `/run` | Start pipeline from scratch |
| `/resume` | Resume from last checkpoint |
| `/check` | Pre-flight validation |
| `/add TITLE [--phase X] [--depends-on IDs]` | Add a new feature to the backlog |
| `/redo [ID\|--failed]` | Re-run specific feature(s) |
| `/status` | Show pipeline state |
| `/sessions [show SESSION_ID]` | List or inspect recorded sessions |
| `/knowledge [list\|search QUERY]` | List or search the knowledge base |
| `/set KEY VALUE` | Modify a config value (see below) |
| `/config` | Open config file in system editor |
| `/reload` | Reload config file from disk |
| `/lang [en\|zh]` | Switch display language |
| `/help` | Show all commands |
| `/quit` | Exit |

**`/set` keys:**

| Key | Example | Description |
|-----|---------|-------------|
| `backend` | `/set backend codex` | Primary backend |
| `workers` | `/set workers 4` | Max parallel feature workers |
| `parallel-backends` | `/set parallel-backends claude,codex` | Parallel worker pool |
| `fallback-backends` | `/set fallback-backends codex` | Fallback on rate-limit |
| `log-level` | `/set log-level DEBUG` | Log verbosity (DEBUG/INFO/WARNING/ERROR) |
| `model` | `/set model claude claude-opus-4-6` | Model for a backend |
| `review-mode` | `/set review-mode cross` | Review strategy (self/cross/backend) |
| `review-backend` | `/set review-backend codex` | Dedicated review backend |

> 💡 Changes made via `/set` are written to `config.toml` immediately — the header updates on screen right away. The new values take effect on the next `/run` or `/resume`.

**Option B — Classic CLI**

```bash
ap run
```

Autopilot starts the full pipeline. When it needs your input (INTERVIEW phase — clarifying questions about your requirements), it pauses and prints the questions to stdout. Answer them in `.autopilot/requirements/INTERVIEW.md`, then:

```bash
ap resume
```

From that point on, the pipeline runs fully autonomously until all features are developed and delivery docs are generated.

> 💡 **TUI vs CLI — INTERVIEW handling:** In TUI mode, the guidance (file path + 3-step instructions) is shown directly in the dashboard when INTERVIEW finishes — no need to scroll through terminal output. In CLI mode, the same instructions are printed to stdout.

---

### CLI Reference

#### `ap init`

Initialize autopilot in the current directory. Creates `.autopilot/` with all subdirectories, `config.toml`, and initial state.

```
ap init [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--backend` | `claude\|codex\|opencode` | `claude` | Primary AI backend |

---

#### `ap run`

Start the full pipeline from the beginning (or from the current state if already initialized).

```
ap run [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--backend` | `claude\|codex\|opencode` | *(from config)* | Override primary backend |
| `--model` | `str` | *(from config)* | Model override (e.g. `claude-opus-4-6`, `o3`) |
| `--log-level` | `DEBUG\|INFO\|WARNING\|ERROR` | `INFO` | Log verbosity |

---

#### `ap resume`

Resume pipeline from the last checkpoint. If paused at HUMAN_PAUSE, automatically advances to the appropriate next phase.

```
ap resume
```

---

#### `ap status`

Show current pipeline status, phase, feature progress, and run result.

```
ap status
```

---

#### `ap add`

Add a new feature to the backlog.

```
ap add TITLE_OR_REQFILE [OPTIONS]
```

| Argument/Option | Type | Default | Description |
|-----------------|------|---------|-------------|
| `TITLE_OR_REQFILE` | `str` | *(required)* | Feature title, or requirements filename when `--from-requirements` |
| `--phase` | `backend\|frontend\|fullstack\|infra` | `backend` | Feature phase category |
| `--depends-on` | `str` | *(none)* | Comma-separated feature IDs this feature depends on |
| `--test-file` | `str` | auto-generated | Path to the test file for this feature |
| `--from-requirements` | flag | `false` | Treat argument as a requirements file; re-runs INTERVIEW → PLANNING |

**Examples:**
```bash
# Add a single feature directly
ap add "Payment gateway integration" --phase backend --depends-on feat-003,feat-007

# Add from a new requirements file (triggers INTERVIEW → PLANNING re-run)
echo "Add Stripe payment support" > .autopilot/requirements/payment.md
ap add payment.md --from-requirements
ap resume
```

---

#### `ap redo`

Reset a feature (and optionally its dependents) back to `pending`, then resume development.
Pass `--failed` to batch-reset every failed feature at once.

```
ap redo [FEATURE_ID] [OPTIONS]
```

| Argument/Option | Type | Default | Description |
|-----------------|------|---------|-------------|
| `FEATURE_ID` | `str` | *(optional)* | Feature ID to re-run (e.g. `feat-005`) |
| `--and-dependents` | flag | `false` | Also reset all features that (transitively) depend on this one |
| `--failed` | flag | `false` | Reset **all** features with status `failed` to `pending` |

**Examples:**
```bash
ap redo feat-005
ap redo feat-003 --and-dependents   # also resets feat-004, feat-007 if they depend on feat-003
ap redo --failed                    # batch-reset every failed feature
```

---

#### `ap check`

Pre-flight validation — run this before `ap run` to catch configuration and environment issues early.

```
ap check
```

Checks:
1. `.autopilot/` directory structure and required files
2. `config.toml` parses and all values are in range
3. Configured backend CLI (`claude` / `codex` / `opencode`) is in PATH
4. Telegram env vars (`AUTOPILOT_TELEGRAM_TOKEN`, `AUTOPILOT_TELEGRAM_CHAT_ID`) when notifications are enabled
5. Git repo presence vs `auto_commit` setting

Exits `0` on pass, `1` on any failure with clear per-check diagnostics.

---

#### `ap sessions list`

List all recorded pipeline sessions with status, phase, elapsed time, and feature progress.

```
ap sessions list
```

Example output:
```
SESSION ID                    STARTED              STATUS        PHASE           ELAPSED  FEATURES
--------------------------------------------------------------------------------------------
20260413T100000-a1b2c3d4      2026-04-13 10:00:00  done          DONE             45m30s  8/10
20260412T153000-e5f6a7b8      2026-04-12 15:30:00  paused        DEV_LOOP         12m15s  3/10
```

---

#### `ap sessions show`

Show the full event timeline for a session — phases, agent calls, per-feature results, errors, and backend switches.

```
ap sessions show SESSION_ID [OPTIONS]
```

| Argument/Option | Type | Default | Description |
|-----------------|------|---------|-------------|
| `SESSION_ID` | `str` | *(required)* | Session ID or prefix. Use `latest` for the most recent session. |
| `--feature` | `str` | *(all)* | Filter the timeline to a specific feature ID |
| `--output` | flag | `false` | Include agent output tails (last 2000 chars of each call) |

**Examples:**
```bash
# Show the most recent session
ap sessions show latest

# Inspect a specific session (prefix matching supported)
ap sessions show 20260413T10

# Debug a failing feature
ap sessions show latest --feature feat-005

# Show full agent output for a session
ap sessions show latest --output
```

Example output:
```
━━━ Session 20260413T100000-a1b2c3d4 ━━━
Started:  2026-04-13 10:00:00 UTC
Backend:  claude  (parallel: 2)
Status:   done — DONE
Elapsed:  45m30s
Features: 8/10

── INTERVIEW ─────────────────────── 50s ✓
  10:00:05  interviewer    claude         50s  ✓  2341chars

── DOC_GEN ──────────────────────── 240s ✓
  10:01:00  doc_gen        claude        238s  ✓  18420chars

── DEV_LOOP ─────────────────────────────
  feat-001  ✓  69s  auth module
    10:15:21  coder    claude     32s  ✓  9821chars
    10:15:55  tester   claude     28s  ✓  4102chars
    10:16:24  reviewer claude     15s  ✓  1873chars

  feat-002  ✗  180s  2 fix retries  payment integration
    10:15:22  coder    claude     45s  ✗  [parse_error]
    10:16:10  fixer    claude     38s  ✓  7234chars
    10:16:48  coder    claude     41s  ✓  9102chars
    ...
```

Sessions are stored as append-only JSONL files in `.autopilot/sessions/` — safe to read at any time, even mid-run.

---

#### `ap knowledge list`

List all knowledge base entries (bugs and decisions).

```
ap knowledge list
```

---

#### `ap knowledge search`

Full-text search across the local knowledge base.

```
ap knowledge search QUERY
```

---

### Configuration Reference

Running `ap init` creates `.autopilot/config.toml` with all options and inline documentation.

#### `[autopilot]` — Core Settings

```toml
[autopilot]
# Primary backend: claude | codex | opencode
backend = "claude"

# Max concurrent feature workers
max_parallel = 2

# Additional backends for parallel workers (round-robin).
# Leave empty [] to reuse the primary backend for all workers.
parallel_backends = ["claude", "codex"]

# Fallback backends tried in order on rate-limit / quota exhaustion
fallback_backends = []

# Log level: DEBUG | INFO | WARNING | ERROR
log_level = "INFO"

# Model override. Leave empty to use the backend's default.
# claude:    "claude-opus-4-6" | "claude-sonnet-4-6" | "opus" | "sonnet"
# codex:     "o3" | "o4-mini" | "gpt-4o"
# opencode:  "anthropic/claude-opus-4-6" | "openai/o3"
model = ""

# TUI display language: "en" (default) or "zh" (Chinese).
# Can also be changed at runtime with /lang inside the TUI.
language = "en"
```

#### `[autopilot.review]` — Review Mode

```toml
[autopilot.review]
# self    — the backend that wrote the code also reviews it (default)
# cross   — a different backend from the parallel pool reviews it
#           (falls back to "self" if pool has only one backend)
# backend — a specific named backend always handles review
#           (falls back to "self" if unavailable)
mode = "self"

# Only used when mode = "backend"
# backend = "codex"
```

#### `[autopilot.retries]` — Retry Limits

```toml
[autopilot.retries]
# Max FIX-phase attempts per feature before marking it failed
max_fix_retries = 5

# Max consecutive phase failures before pausing for human review
max_phase_retries = 3
```

#### `[autopilot.timeouts]` — Per-Phase Timeouts

```toml
[autopilot.timeouts]
# All values in seconds
interview  = 300    #  5 min
doc_gen    = 600    # 10 min
doc_update = 600    # 10 min
planning   = 600    # 10 min
delivery   = 600    # 10 min
code       = 1800   # 30 min  ← increase for large features
test       = 900    # 15 min
review     = 600    # 10 min
fix        = 900    # 15 min
knowledge  = 600    # 10 min
```

#### `[autopilot.permissions]` — Safety

```toml
[autopilot.permissions]
# Allow backends to skip approval prompts and run without sandbox.
# true  — uninterrupted dev loop (recommended for local development)
# false — requires manual confirmation for each tool call (safer for CI/prod)
allow_dangerous_permissions = true
```

#### `[autopilot.notifications]` — Telegram

```toml
[autopilot.notifications]
# Set to true to enable Telegram notifications.
# Required env vars when enabled:
#   AUTOPILOT_TELEGRAM_TOKEN   — Bot token from @BotFather
#   AUTOPILOT_TELEGRAM_CHAT_ID — Target chat or group ID
enabled = false
```

**Setting environment variables:**

Since `ap` is a global CLI tool, it does **not** load a project-level `.env` file. Set the variables in your shell profile so they are available in every session:

- **macOS / Linux** — add to `~/.zshrc` (or `~/.bashrc`):
  ```bash
  export AUTOPILOT_TELEGRAM_TOKEN="<your-bot-token>"
  export AUTOPILOT_TELEGRAM_CHAT_ID="<your-chat-id>"
  ```
  Then reload: `source ~/.zshrc`

- **Windows** — set via System Properties → Environment Variables, or in your PowerShell profile.

> 💡 Get your bot token from [@BotFather](https://t.me/BotFather). To find your chat ID, send a message to your bot then check `https://api.telegram.org/bot<TOKEN>/getUpdates`.

---

### Project Structure

After `ap init`, your project gets a `.autopilot/` directory:

```
.autopilot/
├── config.toml                   ← all configuration
├── state.json                    ← current pipeline state (auto-managed)
├── feature_list.json             ← feature backlog (auto-managed)
├── run_result.json               ← last run summary
├── answers.json                  ← preset decisions injected into all agent prompts (manually filled)
├── requirements/                 ← put your requirement files here
│   └── main.md
├── docs/
│   ├── 00-overview/              ← project overview
│   ├── 01-requirements/          ← PRD
│   ├── 02-research/
│   ├── 03-design/                ← architecture, data model
│   ├── 04-development/           ← tech stack, backend/frontend spec
│   ├── 05-testing/               ← test cases
│   ├── 06-api/                   ← API design
│   ├── 07-deployment/
│   ├── 08-operations/
│   ├── 09-product/               ← delivery docs (quick-start, user manual)
│   └── archive/
├── sessions/
│   └── 20260413T100000-a1b2c3d4.jsonl  ← per-run event log (auto-managed)
└── knowledge/
    ├── bugs/                     ← auto-captured bug root causes
    └── decisions/                ← auto-captured architectural decisions
```

---

### Supported Backends

| Backend | CLI Tool | Strengths |
|---------|----------|-----------|
| `claude` | [Claude Code](https://claude.ai/code) | Best for complex reasoning, large codebases |
| `codex` | [OpenAI Codex CLI](https://github.com/openai/codex) | Fast, cost-effective |
| `opencode` | [OpenCode](https://opencode.ai) | Multi-provider, flexible routing |

You can mix backends freely. For example, use Claude for CODE and Codex for REVIEW (`mode = "cross"` or `mode = "backend"`).

---

### Tips & Advanced Usage

**Use cross-review for better quality:**
```toml
[autopilot.review]
mode = "cross"
```

**Use a fast model for parallel workers, expensive model for review:**
```toml
[autopilot]
backend = "claude"
parallel_backends = ["codex", "codex"]  # cheap workers

[autopilot.review]
mode = "backend"
backend = "claude"                       # expensive reviewer
```

**Resume after a crash:**
```bash
ap resume   # reads state.json and continues from exact checkpoint
```

**Re-develop a failed feature:**
```bash
ap status                      # see which features failed
ap redo feat-012               # reset and re-run one feature
ap redo --failed               # or: reset ALL failed features at once
ap resume
```

**Check the knowledge base after a run:**
```bash
ap knowledge list
ap knowledge search "authentication"
```

**Debug a failed run:**
```bash
ap sessions list                              # find the session
ap sessions show latest                       # full timeline
ap sessions show latest --feature feat-012    # zoom in on the failing feature
ap sessions show latest --output              # show raw agent output
```

---

### License

MIT License — see [LICENSE](LICENSE).

---
---

<a name="chinese"></a>

## 中文

### 什么是 Autopilot？

Autopilot 是一个 Python CLI 工具，驱动 AI 编码智能体（Claude Code、Codex、OpenCode）按结构化、多阶段软件开发流水线工作。写好需求文档，运行 `ap run`，它会自动完成需求访谈、架构文档生成、功能拆解、代码编写、测试、审查、Bug 修复，直到产出交付文档——全程自动驾驶。

**核心能力：**
- 🗂 **完整流水线** — INTERVIEW → DOC_GEN → PLANNING → DEV_LOOP → DOC_UPDATE → KNOWLEDGE → DELIVERY
- ⚡ **并行 Worker** — 多个 AI 后端基于 DAG 调度并发开发 Feature
- 🔄 **交叉 Review** — 一个后端写代码，另一个后端 Review
- 🧠 **知识库** — 自动积累决策记录和 Bug 根因（Markdown 格式），定期压缩
- 📬 **Telegram 通知** — 阶段切换、人工暂停时推送通知
- ↩️ **可断点续跑** — 中途崩溃？`ap resume` 从断点精准恢复
- 🔍 **Session 记录** — 每次运行自动记录完整事件流，用 `ap sessions show` 随时回溯调试
- 🔖 **自动 Git 提交** — 每个 Feature 通过 REVIEW 后自动 commit
- ✅ **运行前检测** — `ap check` 在运行前验证配置、Backend CLI 和环境变量

---

### 系统架构

```
需求文件 (.autopilot/requirements/)
        │
        ▼
  INTERVIEW        ← AI 澄清需求模糊点，向你提问
        │
        ▼
  DOC_GEN          ← 生成 9 份技术文档（PRD、架构、API 设计等）
        │
        ▼
  PLANNING         ← 拆解为带依赖关系（DAG）的 Feature 列表
        │
        ▼
  DEV_LOOP ──────────────────────────────────────────────────────┐
  │  每个 Feature：CODE → TEST → REVIEW → FIX（重试循环）       │
  │  并行 Worker，DAG 感知调度                                    │
  └───────────────────── 全部 Feature 完成 ─────────────────────┘
        │
        ▼
  DOC_UPDATE       ← 开发完成后更新架构文档
        │
        ▼
  KNOWLEDGE        ← 压缩知识库（决策 + Bug 记录）
        │
        ▼
  DELIVERY         ← 生成产品概述、快速上手、用户手册
        │
        ▼
     DONE ✅
```

**以下情况会自动触发人工暂停：**
- INTERVIEW 需要你回答问题（需求澄清）
- 某个 Feature 超过 `max_fix_retries` 重试上限
- 连续阶段失败超过 `max_phase_retries` 上限
- 检测到 DAG 死锁（循环依赖或无法满足的依赖）

---

### 安装

**前置要求：** Python 3.12+，以及至少一个 AI 后端工具。

#### 方式一 — pip（推荐）

```bash
pip install autopilot-ai
```

#### 方式二 — uv tool

```bash
uv tool install autopilot-ai
```

一条命令装好 `ap` 命令，全局可用，无需手动管理虚拟环境。

#### 方式三 — 从源码安装（用于二次开发）

```bash
git clone https://github.com/lqqk7/autopilot.git
cd autopilot
uv sync
uv pip install -e .
```

#### 更新

```bash
pip install -U autopilot-ai          # pip
uv tool upgrade autopilot-ai         # uv tool
```

#### 后端前置条件

| 后端 | 要求 |
|------|------|
| `claude` | 安装并登录 [Claude Code CLI](https://claude.ai/code) |
| `codex` | 安装并配置 [Codex CLI](https://github.com/openai/codex) |
| `opencode` | 安装并配置 [OpenCode CLI](https://opencode.ai) |

---

### 快速开始

#### 第一步 — 初始化项目

进入你的项目目录（可以是空目录，Autopilot 会从零开始构建一切），运行：

```bash
mkdir my-project && cd my-project
ap init --backend claude
```

这会自动创建 `.autopilot/` 目录，包含所有子目录、预填好的 `config.toml` 和初始流水线状态。无需任何其他操作，项目就绪。

```
my-project/
└── .autopilot/
    ├── config.toml          ← 在此配置后端、超时时间等参数
    ├── requirements/        ← 把你的需求文件放在这里  ← 你从这里开始
    ├── docs/                ← 自动生成的技术文档
    └── knowledge/           ← 自动积累的决策记录和 Bug 修复记录
```

---

#### 第二步 — 写需求文档

将一个或多个文件放入 `.autopilot/requirements/` 目录。Autopilot 会**读取该目录下的所有文件**——你可以按任何方式拆分需求。

**格式不限：** 纯文本、Markdown、甚至随手写的要点列表都行，没有固定模板。

**写什么：** 用自然语言描述你想构建的东西。不需要懂技术术语，写得越详细越好，但即使只是粗略描述也能跑起来。

> 💡 **不懂开发？没关系。** 就像跟朋友解释一样，说清楚你想要软件做什么就够了。流水线的 INTERVIEW 阶段会在写代码之前主动向你提问、澄清模糊点。

> 🔧 **懂开发？** 越精确越好——技术栈偏好、API 设计、性能要求、约束条件，全都可以写进去。想写多少文件都行，按模块拆分也完全没问题。

**合法的需求文件示例：**

```
.autopilot/requirements/
├── main.md          ← 核心功能描述
├── auth.md          ← 鉴权相关细节
└── api-notes.txt    ← 额外的 API 约束说明
```

一份最简单的 `main.md` 可以长这样：

```markdown
我想做一个任务管理 Web 应用。

功能需求：
- 用户可以注册和登录
- 用户可以创建、编辑、删除、完成任务
- 任务有标题、描述、截止日期和优先级（高/中/低）
- 用户可以按状态和优先级筛选任务
- 每个用户只能看到自己的任务

技术偏好：Python 后端，REST API，数据库随意。
```

就这些。如果有什么不清楚的地方，Autopilot 在 INTERVIEW 阶段会主动来问你。

---

#### 第三步 — 启动流水线

**方式 A — 全屏 TUI（推荐，v0.3+）**

```bash
autopilot
```

打开全屏交互式终端面板，输入 `/run` 启动流水线，输入 `/help` 查看所有命令。

```
┌─ autopilot v0.3.6  │  ~/my-project  │  2026-04-16  04:35:22 ─────────────────┐
│ DEV_LOOP  via claude  │  features 3/10  │  workers 2/2  │  01:42              │
│ model: default  │  review: self  │  log: INFO  │  max-workers: 2              │
├─ feat-001 ─────────────────────────────────────────────────────────────────────┤
│  ⏳  feat-001  Auth module            CODE      claude   –                    │
│  🔄  feat-002  Payment gateway        TEST      claude   –                    │
│  ✅  feat-003  User profile           done      claude   –                    │
├─ log ──────────────────────────────────────────────────────────────────────────┤
│ 04:35  [feat-002]  Starting phase TEST (backend: claude)                       │
│ 04:35  [feat-001]  Agent reported status=success                               │
└> /run_────────────────────────────────────────────────────────────────────────┘
```

**INTERVIEW 暂停说明**

输入 `/run` 后，Autopilot 从 INTERVIEW 阶段开始——AI 读取你的需求文件并生成一批澄清问题。INTERVIEW 完成后，TUI 会直接在面板中显示清晰的操作提示：

```
📋  INTERVIEW complete — fill in your answers to continue

  File:   .autopilot/requirements/INTERVIEW.md

  Steps:
    1. Open the file above in your editor
    2. Fill in the answers to each question
    3. Type /resume here to continue

```

无需翻找终端输出——操作指引直接显示在面板里。用编辑器打开 `.autopilot/requirements/INTERVIEW.md`，填写好回答，再输入 `/resume`，流水线继续：**DOC_GEN → PLANNING → DEV_LOOP**。

**斜杠命令：**

| 命令 | 说明 |
|------|------|
| `/init [--backend claude\|codex\|opencode]` | 在当前目录初始化 autopilot |
| `/run` | 从头启动流水线 |
| `/resume` | 从上次断点继续 |
| `/check` | 运行前环境检测 |
| `/add TITLE [--phase X] [--depends-on IDs]` | 向 Backlog 添加新 Feature |
| `/redo [ID\|--failed]` | 重跑指定 Feature |
| `/status` | 显示当前流水线状态 |
| `/sessions [show SESSION_ID]` | 列出或查看 Session 记录 |
| `/knowledge [list\|search QUERY]` | 列出或搜索知识库 |
| `/set KEY VALUE` | 修改配置项（见下表） |
| `/config` | 用系统编辑器打开配置文件 |
| `/reload` | 重载配置文件 |
| `/lang [en\|zh]` | 切换显示语言 |
| `/help` | 显示所有命令 |
| `/quit` | 退出 |

**`/set` 可用 Key：**

| Key | 示例 | 说明 |
|-----|------|------|
| `backend` | `/set backend codex` | 主后端 |
| `workers` | `/set workers 4` | 最大并发 Worker 数 |
| `parallel-backends` | `/set parallel-backends claude,codex` | 并行 Worker 后端池 |
| `fallback-backends` | `/set fallback-backends codex` | 限速/配额耗尽时的备用后端 |
| `log-level` | `/set log-level DEBUG` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `model` | `/set model claude claude-opus-4-6` | 指定后端使用的模型 |
| `review-mode` | `/set review-mode cross` | 代码审查策略（self/cross/backend） |
| `review-backend` | `/set review-backend codex` | 专用审查后端 |

> 💡 `/set` 修改的配置会立即写入 `config.toml`，顶部 Header 也会即时刷新。新值在下一次 `/run` 或 `/resume` 时生效。

**方式 B — 经典 CLI**

```bash
ap run
```

Autopilot 启动完整流水线。当需要你介入时（INTERVIEW 阶段——澄清需求问题），流水线会暂停并将操作指引打印到 stdout。在 `.autopilot/requirements/INTERVIEW.md` 中回答完问题后执行：

```bash
ap resume
```

之后流水线全自动运行，直到所有 Feature 开发完成、交付文档生成为止。

> 💡 **TUI 与 CLI 的 INTERVIEW 处理差异：** TUI 模式下，INTERVIEW 完成后操作提示（文件路径 + 三步说明）会直接显示在面板中，无需翻看终端输出。CLI 模式下，同样的提示信息打印到 stdout。

---

### CLI 命令参考

#### `ap init`

在当前目录初始化 autopilot。创建 `.autopilot/` 及所有子目录、`config.toml`、初始状态文件。

```
ap init [OPTIONS]
```

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--backend` | `claude\|codex\|opencode` | `claude` | 主 AI 后端 |

---

#### `ap run`

从头启动完整流水线（若已初始化则从当前状态继续）。

```
ap run [OPTIONS]
```

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--backend` | `claude\|codex\|opencode` | *(从配置读取)* | 覆盖主后端 |
| `--model` | `str` | *(从配置读取)* | 模型覆盖（如 `claude-opus-4-6`、`o3`） |
| `--log-level` | `DEBUG\|INFO\|WARNING\|ERROR` | `INFO` | 日志级别 |

---

#### `ap resume`

从上一个检查点恢复流水线。如果处于 HUMAN_PAUSE 状态，自动推进到对应的下一阶段。

```
ap resume
```

---

#### `ap status`

显示当前流水线状态、阶段、Feature 进度和运行结果。

```
ap status
```

---

#### `ap add`

向 Backlog 添加新 Feature。

```
ap add TITLE_OR_REQFILE [OPTIONS]
```

| 参数/选项 | 类型 | 默认值 | 说明 |
|-----------|------|--------|------|
| `TITLE_OR_REQFILE` | `str` | *(必填)* | Feature 标题；或 `--from-requirements` 时为需求文件名 |
| `--phase` | `backend\|frontend\|fullstack\|infra` | `backend` | Feature 类别 |
| `--depends-on` | `str` | *(无)* | 逗号分隔的依赖 Feature ID 列表 |
| `--test-file` | `str` | 自动生成 | 该 Feature 对应的测试文件路径 |
| `--from-requirements` | 标志 | `false` | 将参数视为需求文件，重新触发 INTERVIEW → PLANNING |

**示例：**
```bash
# 直接添加单个 Feature
ap add "支付宝支付接口" --phase backend --depends-on feat-003,feat-007

# 从新需求文件添加（触发 INTERVIEW → PLANNING 重新执行）
echo "接入 Stripe 支付" > .autopilot/requirements/payment.md
ap add payment.md --from-requirements
ap resume
```

---

#### `ap redo`

将某个 Feature（及其依赖项）重置为 `pending`，重新开发。
使用 `--failed` 可一键批量重置所有失败的 Feature。

```
ap redo [FEATURE_ID] [OPTIONS]
```

| 参数/选项 | 类型 | 默认值 | 说明 |
|-----------|------|--------|------|
| `FEATURE_ID` | `str` | *(可选)* | 要重跑的 Feature ID（如 `feat-005`） |
| `--and-dependents` | 标志 | `false` | 同时重置所有（传递）依赖此 Feature 的 Feature |
| `--failed` | 标志 | `false` | 批量重置所有 `status: failed` 的 Feature |

**示例：**
```bash
ap redo feat-005
ap redo feat-003 --and-dependents   # 同时重置依赖 feat-003 的所有 Feature
ap redo --failed                    # 批量重置所有失败的 Feature
```

---

#### `ap check`

运行前环境检测——在 `ap run` 之前执行，提前发现配置和环境问题。

```
ap check
```

检测项：
1. `.autopilot/` 目录结构完整性及必要文件
2. `config.toml` 可解析，且所有参数值合法
3. 已配置的 Backend CLI（`claude` / `codex` / `opencode`）在 PATH 中
4. Telegram 推送所需的环境变量（若已开启通知）
5. Git 仓库状态与 `auto_commit` 配置是否匹配

全部通过退出码 `0`；有任何问题退出码 `1`，并逐项标出具体原因。

---

#### `ap sessions list`

列出所有 Session 记录，展示状态、阶段、耗时和 Feature 进度。

```
ap sessions list
```

---

#### `ap sessions show`

展示某次 Session 的完整事件时间线——阶段切换、每次 Agent 调用、各 Feature 结果、报错信息、后端切换记录。

```
ap sessions show SESSION_ID [OPTIONS]
```

| 参数/选项 | 类型 | 默认值 | 说明 |
|-----------|------|--------|------|
| `SESSION_ID` | `str` | *(必填)* | Session ID 或前缀。用 `latest` 查看最近一次 Session。 |
| `--feature` | `str` | *(全部)* | 只展示指定 Feature ID 的相关事件 |
| `--output` | 标志 | `false` | 显示每次 Agent 调用的输出 tail（最后 2000 字符） |

**示例：**
```bash
# 查看最近一次 Session
ap sessions show latest

# 查看指定 Session（支持前缀匹配）
ap sessions show 20260413T10

# 排查某个失败的 Feature
ap sessions show latest --feature feat-005

# 查看完整 Agent 输出
ap sessions show latest --output
```

Session 以 append-only JSONL 格式存储在 `.autopilot/sessions/` 下，运行过程中也可随时读取。

---

#### `ap knowledge list`

列出所有知识库条目（Bug 记录和决策记录）。

```
ap knowledge list
```

---

#### `ap knowledge search`

在本地知识库中全文搜索。

```
ap knowledge search QUERY
```

---

### 配置文件参考

执行 `ap init` 后生成 `.autopilot/config.toml`，含所有选项的内联注释。

#### `[autopilot]` — 核心配置

```toml
[autopilot]
# 主后端：claude | codex | opencode
backend = "claude"

# 最大并发 Feature Worker 数量
max_parallel = 2

# 并行 Worker 使用的后端列表（轮询分配）
# 留空 [] 则全部 Worker 使用主后端
parallel_backends = ["claude", "codex"]

# 备用后端（按顺序在限流/配额耗尽时尝试）
fallback_backends = []

# 日志级别：DEBUG | INFO | WARNING | ERROR
log_level = "INFO"

# 模型覆盖。留空则使用后端默认值。
# claude:    "claude-opus-4-6" | "claude-sonnet-4-6" | "opus" | "sonnet"
# codex:     "o3" | "o4-mini" | "gpt-4o"
# opencode:  "anthropic/claude-opus-4-6" | "openai/o3"
model = ""

# TUI 显示语言："en"（默认）或 "zh"（中文）。
# 也可在 TUI 运行时通过 /lang 命令切换。
language = "en"
```

#### `[autopilot.review]` — Review 模式

```toml
[autopilot.review]
# self    — 写代码的后端同时做 Review（默认）
# cross   — 并行池中的另一个后端做 Review
#           （池中只有一个后端时退回 "self"）
# backend — 始终由指定后端做 Review
#           （指定后端不可用时退回 "self"）
mode = "self"

# 仅在 mode = "backend" 时生效
# backend = "codex"
```

#### `[autopilot.retries]` — 重试限制

```toml
[autopilot.retries]
# Feature FIX 阶段最大重试次数，超出后标记为失败
max_fix_retries = 5

# 连续阶段失败最大次数，超出后暂停等待人工介入
max_phase_retries = 3
```

#### `[autopilot.timeouts]` — 各阶段超时

```toml
[autopilot.timeouts]
# 单位：秒
interview  = 300    #  5 分钟
doc_gen    = 600    # 10 分钟
doc_update = 600    # 10 分钟
planning   = 600    # 10 分钟
delivery   = 600    # 10 分钟
code       = 1800   # 30 分钟 ← 大型 Feature 可适当调大
test       = 900    # 15 分钟
review     = 600    # 10 分钟
fix        = 900    # 15 分钟
knowledge  = 600    # 10 分钟
```

#### `[autopilot.permissions]` — 安全权限

```toml
[autopilot.permissions]
# 允许后端跳过审批提示、无沙箱运行
# true  — 开发循环不被打断（本地开发推荐）
# false — 每次工具调用需手动确认（CI/生产环境更安全）
allow_dangerous_permissions = true
```

#### `[autopilot.notifications]` — Telegram 通知

```toml
[autopilot.notifications]
# 设为 true 开启 Telegram 通知
# 开启后必须配置以下环境变量：
#   AUTOPILOT_TELEGRAM_TOKEN   — 从 @BotFather 获取的 Bot Token
#   AUTOPILOT_TELEGRAM_CHAT_ID — 目标聊天或群组 ID
enabled = false
```

**配置环境变量：**

`ap` 是全局 CLI 工具，**不会**自动加载项目级 `.env` 文件。需要将变量写入 Shell 配置文件，确保每次终端会话都可用：

- **macOS / Linux** — 添加到 `~/.zshrc`（或 `~/.bashrc`）：
  ```bash
  export AUTOPILOT_TELEGRAM_TOKEN="<your-bot-token>"
  export AUTOPILOT_TELEGRAM_CHAT_ID="<your-chat-id>"
  ```
  然后重新加载：`source ~/.zshrc`

- **Windows** — 通过「系统属性 → 环境变量」设置，或写入 PowerShell 配置文件。

> 💡 Bot Token 从 [@BotFather](https://t.me/BotFather) 获取。Chat ID 的查找方式：先给 Bot 发一条消息，再访问 `https://api.telegram.org/bot<TOKEN>/getUpdates` 查看返回结果。

---

### 项目目录结构

`ap init` 后，项目中会生成 `.autopilot/` 目录：

```
.autopilot/
├── config.toml                   ← 所有配置项
├── state.json                    ← 流水线当前状态（自动管理）
├── feature_list.json             ← Feature Backlog（自动管理）
├── run_result.json               ← 上次运行摘要
├── answers.json                  ← 预设技术决策（注入所有 Agent prompt，需手动填写）
├── requirements/                 ← 在此放置需求文件
│   └── main.md
├── docs/
│   ├── 00-overview/              ← 项目概述
│   ├── 01-requirements/          ← PRD
│   ├── 02-research/
│   ├── 03-design/                ← 架构、数据模型
│   ├── 04-development/           ← 技术栈、前后端规格
│   ├── 05-testing/               ← 测试用例
│   ├── 06-api/                   ← API 设计
│   ├── 07-deployment/
│   ├── 08-operations/
│   ├── 09-product/               ← 交付文档（快速上手、用户手册）
│   └── archive/
├── sessions/
│   └── 20260413T100000-a1b2c3d4.jsonl  ← 每次运行的事件日志（自动管理）
└── knowledge/
    ├── bugs/                     ← 自动记录的 Bug 根因
    └── decisions/                ← 自动记录的架构决策
```

---

### 支持的后端

| 后端 | 工具 | 特点 |
|------|------|------|
| `claude` | [Claude Code](https://claude.ai/code) | 复杂推理能力强，适合大型代码库 |
| `codex` | [OpenAI Codex CLI](https://github.com/openai/codex) | 快速，成本低 |
| `opencode` | [OpenCode](https://opencode.ai) | 多模型路由，灵活配置 |

可以自由混搭后端。例如用 Claude 写代码，用 Codex 做 Review（设置 `mode = "cross"` 或 `mode = "backend"`）。

---

### 进阶使用技巧

**开启交叉 Review 提升代码质量：**
```toml
[autopilot.review]
mode = "cross"
```

**并行 Worker 用廉价模型，Review 用高端模型：**
```toml
[autopilot]
backend = "claude"
parallel_backends = ["codex", "codex"]  # 廉价 Worker

[autopilot.review]
mode = "backend"
backend = "claude"                       # 高质量 Review
```

**崩溃后恢复：**
```bash
ap resume   # 读取 state.json，从断点精准继续
```

**重跑失败的 Feature：**
```bash
ap status                      # 查看哪些 Feature 失败了
ap redo feat-012               # 重置并重跑单个 Feature
ap redo --failed               # 或：一键批量重置所有失败的 Feature
ap resume
```

**查看知识库：**
```bash
ap knowledge list
ap knowledge search "鉴权"
```

**排查失败运行：**
```bash
ap sessions list                              # 找到对应 Session
ap sessions show latest                       # 查看完整时间线
ap sessions show latest --feature feat-012    # 聚焦失败的 Feature
ap sessions show latest --output              # 查看原始 Agent 输出
```

---

### 开源协议

MIT License — 详见 [LICENSE](LICENSE)。
