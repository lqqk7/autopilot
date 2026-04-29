> [!WARNING]
> **⚠️ 该项目已停止维护 / This project is no longer maintained**
>
> Autopilot CLI 正在被重构为带有 GUI 界面的全新版本，本仓库不再接受新功能开发，仅做存档保留。
>
> Autopilot CLI is being rebuilt as a brand new version with a native GUI. This repository is archived and will no longer receive updates.
>
> 👉 **新版本 / New version：[Lumen](https://github.com/lqqk7/Lumen)**

---

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
- 🧠 **Local knowledge base** — auto-accumulates decisions and bug fixes as Markdown, with periodic compaction
- 📬 **Telegram notifications** — get pinged on phase transitions and human pauses
- ↩️ **Resumable** — crash mid-run? `ap resume` picks up exactly where it left off
- 🔍 **Session recording** — every run is logged as a structured event stream; replay and debug with `ap sessions show`
- 🔖 **Auto git commit** — each feature is automatically committed when it passes REVIEW
- ✅ **Pre-flight check** — `ap check` validates config, backend CLIs, and env vars before you run
- 🏗 **Mission tracking** — per-feature state files + checkpoints under `.autopilot/missions/` (v0.4)
- 🌐 **Global memory** — cross-project knowledge at `~/.autopilot/knowledge/` injected into every session (v0.5)
- 🎯 **Skill runtime** — engine-side Skill definitions match features to best-practice prompt injections (v0.6)
- 📋 **Principles injection** — per-phase behavioral rules in `principles.jsonl` keep AI output consistent (v0.7)
- 🕸 **Knowledge graph** — Bug→Decision→Pattern relations, optional vector search (v0.8)
- 🤝 **Handoff protocol** — structured context packets pass state between sessions and agents (v0.9)

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
  │  skill hints + principles injected into every prompt         │
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
     DONE ✅  →  Handoff written to .autopilot/handoffs/
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
┌─ autopilot v0.9.0  │  ~/my-project  │  2026-04-27  04:35:22 ─────────────────┐
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
| `/missions` | Show current mission and per-feature state (v0.4) |
| `/handoff [latest\|ID]` | Show the latest session handoff packet (v0.9) |
| `/principles [list\|add PHASE RULE]` | List or add behavioral rules for this project (v0.7) |
| `/skills [list\|match QUERY]` | List built-in skills or match to a feature description (v0.6) |
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
ap sessions show latest
ap sessions show 20260413T10
ap sessions show latest --feature feat-005
ap sessions show latest --output
```

---

#### `ap knowledge list` / `ap knowledge search`

Manage the local knowledge base (bugs and decisions accumulated during development).

```bash
ap knowledge list
ap knowledge search "authentication"
```

---

### Advanced Features (v0.4–v0.9)

#### Mission Tracking (v0.4)

Every DEV_LOOP run is organized as a **Mission** — a named container holding per-feature state files and automatic checkpoints. This replaces a single monolithic `state.json` with a hierarchical structure:

```
.autopilot/
├── state.json                    ← global phase state (unchanged)
├── feature_list.json             ← DAG topology (unchanged)
└── missions/
    └── <mission-id>/
        ├── mission.json          ← mission metadata + status
        ├── features/
        │   ├── feat-001.json     ← per-feature state (phase, retries, backend, timing)
        │   └── feat-002.json
        └── checkpoints/
            └── 20260427T....json ← full snapshot after each feature completes
```

Each `feat-xxx.json` tracks: current phase, status, retry count, last backend used, timestamps. Checkpoints let you inspect the exact state of the pipeline at any point in time.

---

#### Global Memory (v0.5)

Autopilot maintains a **cross-project knowledge base** at `~/.autopilot/knowledge/`. Bug fixes, architectural decisions, patterns, and learnings from all your projects are captured here and automatically injected as context when starting new sessions.

```
~/.autopilot/
└── knowledge/
    ├── bugs/           ← bug root causes (e.g. "2026-04-27-redis-timeout.md")
    ├── decisions/      ← architecture decisions
    ├── patterns/       ← reusable solution patterns
    └── learnings/      ← general experience summaries
```

Relevant entries are retrieved via keyword search (Top-N) and prepended to every agent prompt. The more projects you run through Autopilot, the smarter it gets.

**Optional vector search (v0.8):** set `AUTOPILOT_EMBED_API_KEY` to enable semantic similarity search on top of keyword matching:

```bash
export AUTOPILOT_EMBED_API_KEY="sk-..."           # OpenAI-compatible embeddings API
export AUTOPILOT_EMBED_BASE_URL="https://..."     # optional: custom base URL
```

---

#### Skill Runtime (v0.6)

The **Skill Runtime** matches features to best-practice guidelines and injects them into agent prompts automatically — no backend-specific configuration needed.

Built-in skills:

| Skill | Triggers on | Injects |
|-------|-------------|---------|
| `git-pr-workflow` | "pr", "pull request", "branch" | Conventional commits, PR structure |
| `api-endpoint-design` | "api", "endpoint", "rest" | RESTful conventions, status codes, pagination |
| `database-migration` | "migration", "schema", "table" | Reversible migrations, index rules |
| `security-hardening` | "auth", "login", "jwt", "token" | Input validation, rate limiting, secrets |
| `test-coverage` | "test", "coverage" | ≥80% coverage, test naming conventions |
| `async-concurrency` | "async", "thread", "queue" | Timeouts, locks, cancellation handling |

**Add custom skills** by creating JSON files in `~/.autopilot/skills/`:

```json
{
  "name": "my-custom-skill",
  "category": "my-domain",
  "trigger": {"keywords": ["widget", "component"], "phases": []},
  "prompt_hint": "Always wrap widgets in an ErrorBoundary component."
}
```

---

#### Principles Injection (v0.7)

Define **behavioral rules** in `principles.jsonl` files. Rules are filtered by phase and injected into every agent prompt. Three severity levels: `error` (must follow), `warn` (should follow), `info` (context).

**Project-level rules** (`.autopilot/principles.jsonl`):
```jsonl
{"phase": "CODE", "rule": "No eval() or exec() anywhere", "severity": "error"}
{"phase": "CODE", "rule": "All external API calls must have timeout settings", "severity": "warn"}
{"phase": "TEST", "rule": "Test coverage must be ≥80% before REVIEW", "severity": "error"}
{"phase": "REVIEW", "rule": "Check for hardcoded credentials", "severity": "error"}
{"phase": "*",    "rule": "Use conventional commit format for all commits", "severity": "warn"}
```

**Local overrides** (`.autopilot/principles.local.jsonl`) have highest priority — use for project-specific rules that override the global set.

**User-level global rules** (`~/.autopilot/principles.jsonl`) apply to all projects.

---

#### Knowledge Graph (v0.8)

The global knowledge base now maintains a **graph of relations** between entries:

```
Bug: "Redis connection pool exhausted"
  └─ fixed_by → Decision: "Set max_connections=10"
  └─ applies_to → Pattern: "Resource pool configuration checklist"

Decision: "Use JWT over session cookies"
  └─ decided_in → Project: "auth-service"
  └─ pattern → Pattern: "Stateless authentication"
```

Nodes and edges are persisted in `~/.autopilot/knowledge/relations.json`. When vector search is enabled, embeddings are cached under `~/.autopilot/knowledge/.embeddings/` — no repeated API calls.

---

#### Handoff Protocol (v0.9)

When the pipeline exits (paused or done), a **Handoff packet** is automatically written to `.autopilot/handoffs/`. The next session reads this packet and prepends the full context to the initial agent prompt — ensuring continuity across sessions, machines, or even between different agents.

```json
{
  "handoff_id": "h-20260427-a3b4c5",
  "from_session": "session-12345",
  "mission": {"id": "mission-abc123", "title": "Auth Module", "status": "paused"},
  "context": {
    "current_feature": "auth-token-refresh",
    "completed_features": ["auth-login", "auth-logout"],
    "pending_features": ["auth-token-refresh", "auth-mfa"],
    "recent_decisions": ["Use JWT over session cookies"],
    "open_issues": ["refresh_token rotation strategy not yet implemented"]
  },
  "constraints": ["Do not modify the completed auth-login implementation"],
  "knowledge_hints": ["See ~/.autopilot/knowledge/decisions/jwt-decision.md"]
}
```

Handoffs are stored in `.autopilot/handoffs/<handoff-id>.json` — inspect them anytime to understand what the AI "remembers" about your project state.

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
# backend — a specific named backend always handles review
mode = "self"

# Only used when mode = "backend"
# backend = "codex"
```

#### `[autopilot.retries]` — Retry Limits

```toml
[autopilot.retries]
max_fix_retries = 5
max_phase_retries = 3
```

#### `[autopilot.timeouts]` — Per-Phase Timeouts

```toml
[autopilot.timeouts]
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
allow_dangerous_permissions = true
```

#### `[autopilot.notifications]` — Telegram

```toml
[autopilot.notifications]
enabled = false
# Required env vars: AUTOPILOT_TELEGRAM_TOKEN, AUTOPILOT_TELEGRAM_CHAT_ID
```

---

### Project Structure

After `ap init` and a first run, your `.autopilot/` directory looks like:

```
.autopilot/
├── config.toml
├── state.json
├── feature_list.json
├── run_result.json
├── answers.json
├── principles.jsonl          ← project behavioral rules (v0.7)
├── principles.local.jsonl    ← local overrides (v0.7)
├── requirements/
│   └── main.md
├── docs/
│   ├── 00-overview/ … 09-product/
│   └── archive/
├── sessions/
│   └── *.jsonl
├── knowledge/
│   ├── bugs/
│   └── decisions/
├── missions/                 ← per-mission state (v0.4)
│   └── <mission-id>/
│       ├── mission.json
│       ├── features/
│       └── checkpoints/
└── handoffs/                 ← session handoff packets (v0.9)
    └── h-*.json
```

**Global directories** (`~/.autopilot/`):

```
~/.autopilot/
├── principles.jsonl          ← user-level principles applied to all projects (v0.7)
├── knowledge/                ← cross-project knowledge base (v0.5)
│   ├── bugs/
│   ├── decisions/
│   ├── patterns/
│   ├── learnings/
│   ├── relations.json        ← knowledge graph edges (v0.8)
│   └── .embeddings/          ← cached vector embeddings (v0.8)
└── skills/                   ← user-defined skill JSON files (v0.6)
    └── my-skill.json
```

---

### Supported Backends

| Backend | CLI Tool | Strengths |
|---------|----------|-----------|
| `claude` | [Claude Code](https://claude.ai/code) | Best for complex reasoning, large codebases |
| `codex` | [OpenAI Codex CLI](https://github.com/openai/codex) | Fast, cost-effective |
| `opencode` | [OpenCode](https://opencode.ai) | Multi-provider, flexible routing |

---

### Tips & Advanced Usage

**Cross-review for better quality:**
```toml
[autopilot.review]
mode = "cross"
```

**Fast workers + expensive reviewer:**
```toml
[autopilot]
parallel_backends = ["codex", "codex"]
[autopilot.review]
mode = "backend"
backend = "claude"
```

**Hard rules for your project:**
```bash
echo '{"phase":"CODE","rule":"No print() statements — use logging","severity":"error"}' >> .autopilot/principles.jsonl
```

**Inspect a handoff after a session ends:**
```bash
cat .autopilot/handoffs/h-*.json | jq .context
```

**Resume after a crash:**
```bash
ap resume
```

**Re-develop a failed feature:**
```bash
ap redo --failed && ap resume
```

**Debug a failed run:**
```bash
ap sessions show latest --feature feat-012 --output
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
- 🧠 **本地知识库** — 自动积累决策记录和 Bug 根因（Markdown 格式），定期压缩
- 📬 **Telegram 通知** — 阶段切换、人工暂停时推送通知
- ↩️ **可断点续跑** — 中途崩溃？`ap resume` 从断点精准恢复
- 🔍 **Session 记录** — 每次运行自动记录完整事件流，用 `ap sessions show` 随时回溯调试
- 🔖 **自动 Git 提交** — 每个 Feature 通过 REVIEW 后自动 commit
- ✅ **运行前检测** — `ap check` 在运行前验证配置、Backend CLI 和环境变量
- 🏗 **Mission 追踪** — Feature 级独立状态文件 + 自动 Checkpoint（v0.4）
- 🌐 **全局记忆** — `~/.autopilot/knowledge/` 跨项目知识库，自动注入到每次会话（v0.5）
- 🎯 **Skill 运行时** — 引擎侧 Skill 定义，自动匹配 Feature 并注入最佳实践提示（v0.6）
- 📋 **Principles 注入** — `principles.jsonl` 定义 Phase 级行为规则，保持 AI 输出一致性（v0.7）
- 🕸 **知识图谱** — Bug→Decision→Pattern 关联关系，可选向量检索（v0.8）
- 🤝 **Handoff 协议** — 结构化上下文交接包，在 Session 间和 Agent 间传递状态（v0.9）

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
  │  每个 prompt 自动注入 Skill 提示 + Principles 规则            │
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
     DONE ✅  →  Handoff 写入 .autopilot/handoffs/
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

#### 方式三 — 从源码安装

```bash
git clone https://github.com/lqqk7/autopilot.git
cd autopilot
uv sync
uv pip install -e .
```

#### 更新

```bash
pip install -U autopilot-ai
uv tool upgrade autopilot-ai
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

```bash
mkdir my-project && cd my-project
ap init --backend claude
```

#### 第二步 — 写需求文档

将需求文件放入 `.autopilot/requirements/`，支持任意格式（纯文本、Markdown 均可）。

#### 第三步 — 启动流水线

**方式 A — 全屏 TUI（推荐）**

```bash
autopilot
```

输入 `/run` 启动。INTERVIEW 完成后，TUI 直接显示操作提示：

```
📋  INTERVIEW complete — fill in your answers to continue

  File:   .autopilot/requirements/INTERVIEW.md

  Steps:
    1. Open the file above in your editor
    2. Fill in the answers to each question
    3. Type /resume here to continue
```

填写完 `INTERVIEW.md` 后输入 `/resume`，流水线继续。

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
| `/missions` | 查看当前 Mission 和 Feature 级状态（v0.4） |
| `/handoff [latest\|ID]` | 查看最新 Session Handoff 内容（v0.9） |
| `/principles [list\|add PHASE RULE]` | 查看或添加项目行为规则（v0.7） |
| `/skills [list\|match QUERY]` | 查看内置 Skills 或匹配 Feature 描述（v0.6） |
| `/help` | 显示所有命令 |
| `/quit` | 退出 |

**`/set` 可用 Key：**

| Key | 示例 | 说明 |
|-----|------|------|
| `backend` | `/set backend codex` | 主后端 |
| `workers` | `/set workers 4` | 最大并发 Worker 数 |
| `parallel-backends` | `/set parallel-backends claude,codex` | 并行 Worker 后端池 |
| `fallback-backends` | `/set fallback-backends codex` | 限速/配额耗尽时的备用后端 |
| `log-level` | `/set log-level DEBUG` | 日志级别 |
| `model` | `/set model claude claude-opus-4-6` | 指定后端使用的模型 |
| `review-mode` | `/set review-mode cross` | 代码审查策略（self/cross/backend） |
| `review-backend` | `/set review-backend codex` | 专用审查后端 |

**方式 B — 经典 CLI**

```bash
ap run
# 填写 INTERVIEW.md 后
ap resume
```

---

### 进阶功能（v0.4–v0.9）

#### Mission 追踪（v0.4）

每次 DEV_LOOP 运行都以 **Mission** 为单位组织——包含 Feature 级独立状态文件和自动 Checkpoint：

```
.autopilot/missions/
└── <mission-id>/
    ├── mission.json        ← Mission 元数据（状态、标题）
    ├── features/
    │   ├── feat-001.json   ← 每个 Feature 的独立状态（阶段、重试次数、后端、时间戳）
    │   └── feat-002.json
    └── checkpoints/
        └── 20260427T....json  ← 每个 Feature 完成后的完整快照
```

---

#### 全局记忆（v0.5）

`~/.autopilot/knowledge/` 跨项目知识库，自动记录 Bug 修复、架构决策、可复用模式和经验总结，并在每次新会话启动时注入相关内容：

```
~/.autopilot/knowledge/
├── bugs/        ← Bug 根因记录
├── decisions/   ← 架构决策
├── patterns/    ← 可复用解决模式
└── learnings/   ← 综合经验教训
```

**可选向量检索（v0.8）：** 配置 `AUTOPILOT_EMBED_API_KEY` 即可启用语义相似度检索：

```bash
export AUTOPILOT_EMBED_API_KEY="sk-..."
export AUTOPILOT_EMBED_BASE_URL="https://..."  # 可选，自定义 API 地址
```

---

#### Skill 运行时（v0.6）

引擎自动将 Feature 描述与 Skill 定义匹配，并将最佳实践提示注入到 Agent prompt 中，无需针对每个后端单独配置。

内置 Skills：

| Skill | 触发关键词 | 注入内容 |
|-------|-----------|----------|
| `git-pr-workflow` | pr、pull request、branch | Conventional Commits、PR 结构规范 |
| `api-endpoint-design` | api、endpoint、rest | RESTful 规范、状态码、分页 |
| `database-migration` | migration、schema、table | 可回滚迁移、索引规则 |
| `security-hardening` | auth、login、jwt、token | 输入校验、限流、密钥管理 |
| `test-coverage` | test、coverage | ≥80% 覆盖率、测试命名规范 |
| `async-concurrency` | async、thread、queue | 超时、锁、取消处理 |

**自定义 Skill：** 在 `~/.autopilot/skills/` 目录下创建 JSON 文件即可：

```json
{
  "name": "my-skill",
  "category": "my-domain",
  "trigger": {"keywords": ["widget"], "phases": []},
  "prompt_hint": "所有 Widget 必须包裹在 ErrorBoundary 组件中。"
}
```

---

#### Principles 注入（v0.7）

在 `principles.jsonl` 中定义**行为规则**，按 Phase 自动过滤并注入到 Agent prompt 中：

```jsonl
{"phase": "CODE",   "rule": "禁止使用 eval() 或 exec()", "severity": "error"}
{"phase": "CODE",   "rule": "所有外部 API 调用必须有超时设置", "severity": "warn"}
{"phase": "TEST",   "rule": "测试覆盖率低于 80% 不得进入 REVIEW", "severity": "error"}
{"phase": "REVIEW", "rule": "必须检查是否有硬编码凭证", "severity": "error"}
{"phase": "*",      "rule": "使用 Conventional Commits 格式提交", "severity": "warn"}
```

规则来源优先级（高→低）：
1. `.autopilot/principles.local.jsonl`（项目本地覆盖）
2. `.autopilot/principles.jsonl`（项目级）
3. `~/.autopilot/principles.jsonl`（用户全局）

---

#### 知识图谱（v0.8）

全局知识库自动维护条目之间的**关联关系**：

```
Bug: "Redis 连接池耗尽"
  └─ fixed_by  → Decision: "设置 max_connections=10"
  └─ applies_to → Pattern: "资源池配置检查清单"
```

节点和边持久化在 `~/.autopilot/knowledge/relations.json`。启用向量检索后，Embedding 缓存在 `~/.autopilot/knowledge/.embeddings/`，不会重复调用 API。

---

#### Handoff 协议（v0.9）

流水线退出（暂停或完成）时，自动将完整上下文写入 `.autopilot/handoffs/` 目录。下次会话启动时读取最新 Handoff，将其前置注入到初始 Agent prompt 中——确保跨会话、跨机器乃至不同 Agent 之间的状态连续性。

```json
{
  "handoff_id": "h-20260427-a3b4c5",
  "mission": {"title": "Auth Module", "status": "paused"},
  "context": {
    "current_feature": "auth-token-refresh",
    "completed_features": ["auth-login", "auth-logout"],
    "open_issues": ["refresh_token 旋转策略尚未实现"]
  },
  "constraints": ["不得修改已完成的 auth-login 实现"]
}
```

---

### 配置文件参考

#### `[autopilot]` — 核心配置

```toml
[autopilot]
backend = "claude"
max_parallel = 2
parallel_backends = []
fallback_backends = []
log_level = "INFO"
model = ""
language = "en"
```

#### `[autopilot.review]`

```toml
[autopilot.review]
mode = "self"   # self | cross | backend
# backend = "codex"
```

#### `[autopilot.retries]`

```toml
[autopilot.retries]
max_fix_retries = 5
max_phase_retries = 3
```

#### `[autopilot.timeouts]`

```toml
[autopilot.timeouts]
code = 1800   # 30 分钟，大型 Feature 可调大
test = 900
review = 600
# ... 其他阶段
```

---

### 项目目录结构

```
.autopilot/
├── config.toml
├── state.json
├── feature_list.json
├── principles.jsonl          ← 项目行为规则（v0.7）
├── principles.local.jsonl    ← 本地覆盖规则（v0.7）
├── requirements/
├── docs/
├── sessions/
├── knowledge/
│   ├── bugs/
│   └── decisions/
├── missions/                 ← Mission 追踪（v0.4）
│   └── <mission-id>/
│       ├── mission.json
│       ├── features/
│       └── checkpoints/
└── handoffs/                 ← Session 交接包（v0.9）
    └── h-*.json
```

**全局目录** (`~/.autopilot/`)：

```
~/.autopilot/
├── principles.jsonl          ← 用户全局规则（v0.7）
├── knowledge/                ← 跨项目知识库（v0.5）
│   ├── bugs/
│   ├── decisions/
│   ├── patterns/
│   ├── learnings/
│   ├── relations.json        ← 知识图谱边（v0.8）
│   └── .embeddings/          ← 向量缓存（v0.8）
└── skills/                   ← 自定义 Skill 定义（v0.6）
    └── my-skill.json
```

---

### 支持的后端

| 后端 | 工具 | 特点 |
|------|------|------|
| `claude` | [Claude Code](https://claude.ai/code) | 复杂推理能力强，适合大型代码库 |
| `codex` | [OpenAI Codex CLI](https://github.com/openai/codex) | 快速，成本低 |
| `opencode` | [OpenCode](https://opencode.ai) | 多模型路由，灵活配置 |

---

### 进阶使用技巧

**为项目设置强制规则：**
```bash
echo '{"phase":"CODE","rule":"禁止直接使用 print()，必须用 logging","severity":"error"}' >> .autopilot/principles.jsonl
```

**查看 Handoff 上下文：**
```bash
cat .autopilot/handoffs/h-*.json | python3 -m json.tool
```

**崩溃后恢复：**
```bash
ap resume
```

**重跑失败 Feature：**
```bash
ap redo --failed && ap resume
```

**排查失败运行：**
```bash
ap sessions show latest --feature feat-012 --output
```

---

### 开源协议

MIT License — 详见 [LICENSE](LICENSE)。
