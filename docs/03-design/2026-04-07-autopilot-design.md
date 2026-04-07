# Autopilot 设计规格文档

**创建时间**：2026-04-07  
**状态**：已确认  
**项目路径**：`~/Projects/autopilot`

---

## 一、项目定位

Autopilot 是一款面向产品驱动开发者的 AI 编程自动化引擎。用户在 Plan 阶段用 Claude Code / Codex 等工具与 AI 讨论清楚需求，之后执行 `ap run`，引擎全程无人值守地完成：文档生成 → 任务规划 → 编码 → 测试 → 修复 → 文档更新 → 经验沉淀。

**核心设计原则**：流程控制由 Python 代码决定，AI 只负责内容生成，不参与"下一步做什么"的决策。

---

## 二、整体架构

### 分层设计

```
┌─────────────────────────────────────────┐
│           CLI 入口层                     │  ap init / run / resume / status / pause
├─────────────────────────────────────────┤
│           Pipeline 引擎层                │  状态机、Phase 调度、错误恢复、超时守护
├─────────────────────────────────────────┤
│           Agent 层                       │  每个 Phase 对应一个 Agent（.md Prompt）
├─────────────────────────────────────────┤
│           Backend 抽象层                 │  ClaudeCode / Codex / OpenCode 统一接口
├─────────────────────────────────────────┤
│           知识 & 状态层                  │  本地 MD + Zep 双写
└─────────────────────────────────────────┘
```

### 项目目录结构

```
~/Projects/autopilot/
├── autopilot/
│   ├── cli.py                  # CLI 入口（Click）
│   ├── pipeline/
│   │   ├── engine.py           # 状态机主循环
│   │   ├── phases.py           # Phase 定义 & 转换规则
│   │   └── context.py          # 全局执行上下文
│   ├── agents/                 # Agent Prompt 模板（.md）
│   │   ├── doc_gen.md
│   │   ├── planner.md
│   │   ├── coder.md
│   │   ├── tester.md
│   │   ├── reviewer.md
│   │   └── fixer.md
│   ├── backends/
│   │   ├── base.py             # 抽象基类
│   │   ├── claude_code.py
│   │   ├── codex.py
│   │   └── opencode.py
│   └── knowledge/
│       ├── local.py            # 本地 MD 读写
│       └── zep.py              # Zep 接入
├── scripts/                    # run/debug 脚本
├── docs/
├── tests/
└── pyproject.toml
```

### 目标项目运行时目录

每次对一个项目运行 `ap init`，会在该项目根目录创建：

```
your-project/
└── .autopilot/
    ├── input/                  # 用户放需求描述的地方
    ├── docs/                   # 引擎生成的技术文档
    ├── state.json              # 当前流水线状态
    ├── feature_list.json       # 功能任务列表
    ├── config.toml             # 项目级配置
    └── knowledge/              # 本项目经验 MD
        ├── bugs/
        ├── decisions/
        └── summary.md
```

---

## 三、Pipeline 状态机

### 状态流转

```
INIT
  ↓
DOC_GEN          # 根据 input/ 生成全套技术文档
  ↓
PLANNING         # 拆解 feature 任务列表，定义开发顺序
  ↓
DEV_LOOP         # 主循环，逐 feature 执行
  ├─ CODE
  ├─ TEST        # 通过 → FEATURE_DONE
  ├─ REVIEW      # 失败 → FIX → 回 CODE（超限 → HUMAN_PAUSE）
  └─ FIX
  ↓ 所有 feature 完成
DOC_UPDATE       # 更新受影响文档
  ↓
KNOWLEDGE        # 经验写入本地 MD + Zep
  ↓
DONE
```

### 各 Phase 退出条件（代码硬性判断）

| Phase | 退出条件 |
|---|---|
| DOC_GEN | 所有文档文件存在且超过最小字数阈值 |
| PLANNING | `feature_list.json` 解析成功，至少 1 个 feature |
| CODE | git diff 检测到代码文件变更 |
| TEST | `test_report.json` 存在且格式合法 |
| REVIEW | `review_report.json` 存在且格式合法 |
| FIX | 代码文件有变更 |
| DOC_UPDATE | 受影响文档 mtime 更新 |
| KNOWLEDGE | Zep 写入成功 + 本地 MD 文件存在 |

### 失败恢复规则

```python
MAX_FIX_RETRIES = 5       # DEV_LOOP 内 FIX 重试上限
MAX_PHASE_RETRIES = 3     # 任意 Phase 失败重试上限
TIMEOUT_SECONDS = 300     # 单次 AI 调用超时（无输出则 kill）
```

### HUMAN_PAUSE 触发条件

- FIX 超过 `MAX_FIX_RETRIES` 次仍失败
- 任意 Phase 输出格式解析连续失败 3 次
- DOC_GEN 阶段检测到 input/ 信息严重不足
- 用户手动 `ap pause`

暂停后写入 `state.json` 记录中断点，发 Telegram 通知，`ap resume` 续跑。

---

## 四、Backend 抽象层

### 统一接口

```python
# backends/base.py

@dataclass
class RunContext:
    project_path: Path
    docs_path: Path
    feature: Feature | None
    knowledge_md: str        # 注入的历史经验
    extra_files: list[Path]  # 需要 AI 读取的文件列表

@dataclass
class BackendResult:
    success: bool
    output: str
    duration_seconds: float
    error: str | None

class BackendBase:
    def run(self, agent_name: str, prompt: str, context: RunContext) -> BackendResult: ...
    def is_available(self) -> bool: ...
```

### 三个后端调用方式

| | Claude Code | Codex CLI | OpenCode |
|---|---|---|---|
| 命令 | `claude -p --dangerously-skip-permissions` | `codex --approval-mode full-auto` | `opencode run --agent` |
| Agent 注入 | `--agent <md文件路径>` | system prompt 参数 | `--agent <名称>` |
| 权限放开 | `--dangerously-skip-permissions` | `--approval-mode full-auto` | 默认无限制 |

### 后端配置

```toml
# .autopilot/config.toml
[autopilot]
backend = "claude"          # claude | codex | opencode
model = "claude-sonnet-4-6" # 可选
```

运行时覆盖：`ap run --backend codex`

---

## 五、Agent Prompt 设计

### 结构化输出协议

所有 Agent Prompt 末尾统一附加输出协议，引擎只解析此 JSON 块，其余输出存日志：

````markdown
## 输出协议
完成后必须输出以下 JSON 块，不得省略：

```json autopilot-result
{
  "status": "success" | "failure" | "partial",
  "summary": "一句话描述做了什么",
  "artifacts": ["生成/修改的文件路径列表"],
  "issues": ["发现的问题，没有则为空数组"],
  "next_hint": "给下一个阶段的提示（可选）"
}
```
````

### DOC_GEN 生成文档清单

```
.autopilot/docs/
├── PRD.md              # 产品需求文档（功能列表、用户故事）
├── tech-stack.md       # 技术栈选型 & 版本
├── architecture.md     # 系统架构（模块划分、数据流）
├── data-model.md       # 数据结构 & 数据库 Schema
├── api-design.md       # API 接口设计
├── frontend-spec.md    # 前端规范（组件、路由、状态管理）
├── backend-spec.md     # 后端规范（服务边界、中间件、错误处理）
└── test-cases.md       # 测试用例设计（单测 + E2E 关键路径）
```

DOC_GEN 两步走：
1. 引擎检查 `input/` 内容充分性 → 不足则 HUMAN_PAUSE
2. AI 逐文档生成 → 引擎验证每个文件存在且超过最小字数阈值 → 失败重试（最多3次）

### PLANNING Agent 输出格式

```json
{
  "features": [
    {
      "id": "feat-001",
      "title": "用户登录",
      "phase": "backend",
      "depends_on": [],
      "status": "pending",
      "test_file": "tests/test_auth.py"
    }
  ]
}
```

依赖关系由代码做拓扑排序，保证执行顺序正确。

---

## 六、知识层

### 本地 MD 结构

```
.autopilot/knowledge/
├── bugs/
│   └── 2026-04-07-fix-auth-jwt-expiry.md    # 每次 FIX 成功后沉淀
├── decisions/
│   └── 2026-04-07-chose-prisma-over-drizzle.md
└── summary.md                                # 项目整体经验总结
```

### Zep 集成

- **写入 graph**：`project.<项目名>.shared`
- **内容**：bug 原因 + 修复方案 + 涉及文件
- **召回时机**：每个 Agent 执行前，用当前 feature 标题 + 技术栈关键词检索
- **注入位置**：Prompt 的 `## 历史经验` 区块

---

## 七、CLI 命令设计

```bash
ap init [--backend claude|codex|opencode]   # 初始化目标项目
ap run [--backend xxx] [--model xxx]         # 启动完整流水线
ap resume                                    # 从中断点续跑
ap status                                    # 查看当前状态
ap pause                                     # 手动暂停

# 调试用：重跑指定 Phase
ap run --phase doc_gen
ap run --phase dev_loop --feature feat-003

# 经验库
ap knowledge list
ap knowledge search "jwt token"
```

---

## 八、Telegram 通知

复用本机 Telegram Bot（配置见 `~/.claude/` 核心记忆，chat_id 为突突 DM）：

| 事件 | 通知内容 |
|---|---|
| HUMAN_PAUSE | 暂停原因 + 当前 Phase + 建议操作 |
| FEATURE_DONE | feature 名称 + 耗时 + 进度（x/total）|
| DONE | 完成通知 + 总耗时 + 经验条数 |
| 超时 kill | 被 kill 的 Phase + 重试次数 |

---

## 九、技术选型

| 模块 | 选型 |
|---|---|
| 语言 | Python 3.12+ |
| CLI 框架 | Click |
| 依赖管理 | uv |
| 数据验证 | Pydantic（强类型状态对象）|
| 进程管理 | subprocess（list 模式）+ threading 超时守护 |
| 配置文件 | TOML |
| 知识库 | 本地 MD + Zep API |
| 通知 | Telegram Bot API |
