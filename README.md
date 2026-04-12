<div align="center">

# 🤖 Autopilot

**AI Coding Automation Engine**

*From requirements to production-ready code — fully automated.*

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![uv](https://img.shields.io/badge/managed%20with-uv-purple)](https://github.com/astral-sh/uv)

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

**Requirements:** Python 3.12+, [uv](https://github.com/astral-sh/uv), and at least one AI backend installed.

#### Install uv (if you haven't)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Option 1 — Install as a global tool (recommended)

```bash
uv tool install git+https://github.com/lqqk7/autopilot.git
```

This installs the `ap` command globally and keeps it isolated — no virtualenv management needed.

#### Option 2 — Install from source (for development / hacking)

```bash
git clone https://github.com/lqqk7/autopilot.git
cd autopilot
uv sync
uv pip install -e .
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

```bash
ap run
```

Autopilot starts the full pipeline. When it needs your input (INTERVIEW phase — clarifying questions about your requirements), it pauses and prints the questions. Answer them, then:

```bash
ap resume
```

From that point on, the pipeline runs fully autonomously until all features are developed and delivery docs are generated.

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

```
ap redo FEATURE_ID [OPTIONS]
```

| Argument/Option | Type | Default | Description |
|-----------------|------|---------|-------------|
| `FEATURE_ID` | `str` | *(required)* | Feature ID to re-run (e.g. `feat-005`) |
| `--and-dependents` | flag | `false` | Also reset all features that (transitively) depend on this one |

**Examples:**
```bash
ap redo feat-005
ap redo feat-003 --and-dependents   # also resets feat-004, feat-007 if they depend on feat-003
```

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
ap redo feat-012               # reset and re-run
ap resume
```

**Check the knowledge base after a run:**
```bash
ap knowledge list
ap knowledge search "authentication"
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

**前置要求：** Python 3.12+、[uv](https://github.com/astral-sh/uv)，以及至少一个 AI 后端工具。

#### 安装 uv（如果还没装）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 方式一 — 安装为全局工具（推荐）

```bash
uv tool install git+https://github.com/lqqk7/autopilot.git
```

一条命令装好 `ap` 命令，全局可用，无需手动管理虚拟环境。

#### 方式二 — 从源码安装（用于二次开发）

```bash
git clone https://github.com/lqqk7/autopilot.git
cd autopilot
uv sync
uv pip install -e .
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

```bash
ap run
```

Autopilot 启动完整流水线。当需要你介入时（INTERVIEW 阶段——澄清需求问题），流水线会暂停并打印问题。回答完毕后执行：

```bash
ap resume
```

之后流水线全自动运行，直到所有 Feature 开发完成、交付文档生成为止。

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

```
ap redo FEATURE_ID [OPTIONS]
```

| 参数/选项 | 类型 | 默认值 | 说明 |
|-----------|------|--------|------|
| `FEATURE_ID` | `str` | *(必填)* | 要重跑的 Feature ID（如 `feat-005`） |
| `--and-dependents` | 标志 | `false` | 同时重置所有（传递）依赖此 Feature 的 Feature |

**示例：**
```bash
ap redo feat-005
ap redo feat-003 --and-dependents   # 同时重置依赖 feat-003 的所有 Feature
```

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
ap redo feat-012               # 重置并重跑
ap resume
```

**查看知识库：**
```bash
ap knowledge list
ap knowledge search "鉴权"
```

---

### 开源协议

MIT License — 详见 [LICENSE](LICENSE)。
