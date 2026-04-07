# Autopilot v0.2 实施计划

**创建时间**：2026-04-07  
**状态**：待开发  
**基准版本**：v0.1.0（所有 43 条测试通过）  
**参考设计文档**：`docs/03-design/2026-04-07-autopilot-design.md`（v0.2 章节）

---

## 一、版本目标

在 v0.1 核心 Pipeline 可运行的基础上，完成以下三项改进：

| 功能 | 描述 | 设计文档章节 |
|---|---|---|
| **错误分类重试** | `BackendResult` 携带 `error_type`，引擎按类型决定重试策略，告别无差别傻重试 | 第三节 |
| **结构化运行结果** | 每次 Pipeline 结束写出 `run_result.json`，供外部消费和 `ap status` 展示 | 第十节 |
| **预置决策注入** | 读取 `answers.json`，注入 Prompt `## 预设决策` 区块，减少 AI 选择阻塞 | 第五节 |

---

## 二、任务列表

共 **8 个任务**，按依赖顺序执行。Task 1 是其余所有任务的基础，需优先完成。

---

### Task 1 — 数据结构扩展

**文件**：`autopilot/backends/base.py`

**变更内容**：

1. 新增 `ErrorType` 枚举（7 个值）：
   ```python
   class ErrorType(str, Enum):
       rate_limit = "rate_limit"
       quota_exhausted = "quota_exhausted"
       server_error = "server_error"
       context_overflow = "context_overflow"
       timeout = "timeout"
       parse_error = "parse_error"
       unknown = "unknown"
   ```

2. `BackendResult` 新增字段 `error_type: ErrorType | None = None`

3. `RunContext` 新增字段 `answers_md: str = ""`（默认空字符串，不存在 answers.json 时跳过注入）

**测试文件**：`tests/test_base_models.py`（新建）

**测试用例**：
- `ErrorType` 枚举值是否合法
- `BackendResult` 默认 `error_type=None`
- `BackendResult(success=False, error_type=ErrorType.timeout)` 正常构造
- `RunContext` 默认 `answers_md=""`

---

### Task 2 — Claude Code Backend 错误映射

**文件**：`autopilot/backends/claude_code.py`

**变更内容**：在 `run()` 方法的返回路径上，将 subprocess 的 returncode / stderr 内容映射到 `ErrorType`：

| 检测条件 | 映射 ErrorType |
|---|---|
| returncode == 0 | `None`（成功） |
| `"rate_limit"` / `"429"` in stderr | `rate_limit` |
| `"quota"` / `"billing"` in stderr | `quota_exhausted` |
| `"context"` / `"too long"` / `"token"` in stderr | `context_overflow` |
| `"500"` / `"502"` / `"503"` in stderr | `server_error` |
| subprocess `TimeoutExpired` | `timeout` |
| 无法解析 `json autopilot-result` | `parse_error`（由引擎层设置，backend 不感知） |
| 其他 | `unknown` |

**测试文件**：`tests/test_backend_claude.py`（扩展已有文件）

**测试用例**：
- stderr 含 "rate_limit" → `BackendResult.error_type == ErrorType.rate_limit`
- stderr 含 "quota" → `quota_exhausted`
- stderr 含 "context window" → `context_overflow`
- TimeoutExpired → `timeout`
- returncode != 0 无法匹配 → `unknown`

---

### Task 3 — Codex Backend 错误映射

**文件**：`autopilot/backends/codex.py`

**变更内容**：与 Task 2 逻辑相同，针对 Codex CLI 的 stderr 格式调整关键词：

| 检测条件 | 映射 ErrorType |
|---|---|
| `"rate limit"` in stderr | `rate_limit` |
| `"quota exceeded"` in stderr | `quota_exhausted` |
| `"context_length_exceeded"` in stderr | `context_overflow` |
| 5xx HTTP status code in stderr | `server_error` |
| `TimeoutExpired` | `timeout` |
| 其他非零退出 | `unknown` |

**测试文件**：`tests/test_backend_codex.py`（扩展已有文件）

**测试用例**：同 Task 2，针对 Codex 关键词。

---

### Task 4 — OpenCode Backend 错误映射

**文件**：`autopilot/backends/opencode.py`

**变更内容**：同 Task 2/3 模式，针对 OpenCode 的输出格式：

| 检测条件 | 映射 ErrorType |
|---|---|
| `"rate_limit"` in stderr | `rate_limit` |
| `"insufficient_quota"` in stderr | `quota_exhausted` |
| `"maximum context length"` in stderr | `context_overflow` |
| HTTP 5xx in stderr | `server_error` |
| `TimeoutExpired` | `timeout` |
| 其他 | `unknown` |

**测试文件**：`tests/test_backend_opencode.py`（扩展已有文件）

**测试用例**：同 Task 2，针对 OpenCode 关键词。

---

### Task 5 — 引擎错误分类重试逻辑

**文件**：`autopilot/pipeline/engine.py`

**变更内容**：`run_phase()` 方法重构，根据 `BackendResult.error_type` 决定处理策略：

```
成功 → 正常返回
error_type == None 且 success=False → 当作 unknown

rate_limit     → 指数退避（10s → 30s → 60s），最多 3 次，超限 → HUMAN_PAUSE
quota_exhausted → 直接 HUMAN_PAUSE（v0.4 再做 backend fallback）
server_error   → 指数退避（参考 Retry-After），最多 3 次，超限 → HUMAN_PAUSE
context_overflow → HUMAN_PAUSE（v0.3 再做 compaction 自动处理）
timeout        → 计入 phase_retries，发 Telegram 通知，超限 → HUMAN_PAUSE
parse_error    → 直接重试（不等待），最多 3 次，超限 → HUMAN_PAUSE
unknown        → 计入 phase_retries，超限 → HUMAN_PAUSE
```

**新增辅助方法**：
- `_handle_error(result: BackendResult, retry_count: int) -> tuple[bool, float]`：返回 `(should_retry, wait_seconds)`
- `_exponential_backoff(attempt: int, base: float = 10.0) -> float`：计算退避时间

**Telegram 通知**：`timeout` 错误发通知，`rate_limit` 切换时发通知（信息：原 backend + 重试次数）

**测试文件**：`tests/test_engine_retry.py`（新建）

**测试用例**：
- `rate_limit` 第 1 次 → 等待 10s，返回 should_retry=True
- `rate_limit` 第 3 次 → 返回 should_retry=False（触发 HUMAN_PAUSE）
- `quota_exhausted` → 立即 should_retry=False
- `context_overflow` → 立即 should_retry=False
- `parse_error` 第 1 次 → wait=0，should_retry=True
- `parse_error` 第 3 次 → should_retry=False
- `timeout` → 计入 phase_retries，发 Telegram
- `unknown` 超限 → HUMAN_PAUSE

---

### Task 6 — run_result.json 写出

**文件**：`autopilot/pipeline/engine.py`（扩展）+ `autopilot/pipeline/context.py`（新增 RunResult 数据结构）

**context.py 新增**：

```python
@dataclass
class RunResult:
    status: str              # "done" | "paused" | "error"
    phase: str               # 结束时的 Phase 名称
    elapsed_seconds: float
    features_total: int
    features_done: int
    artifacts: list[str]     # 所有已处理 feature 的 artifacts 汇总
    pause_reason: str | None
    backend_used: str
    backend_switches: int
    knowledge_count: int     # 本次写入的知识条数
    compactions: int         # 压缩次数（v0.2 恒为 0）
    timestamp: str           # ISO 8601 UTC

    def save(self, path: Path) -> None: ...

    @classmethod
    def load(cls, path: Path) -> "RunResult": ...
```

**engine.py 变更**：
- `run()` 方法在 DONE 和 HUMAN_PAUSE 时调用 `RunResult.save(autopilot_dir / "run_result.json")`
- 新增 `_run_start_time: float` 属性记录开始时间
- 新增 `_collected_artifacts: list[str]` 累积每个 feature 的 artifacts
- 新增 `_knowledge_count: int` 累积知识写入次数

**cli.py 变更**：
- `ap status` 命令优先读取 `run_result.json`，展示结构化摘要（当前仅读 `state.json`）

**测试文件**：`tests/test_run_result.py`（新建）

**测试用例**：
- `RunResult.save()` 写出合法 JSON
- `RunResult.load()` 反序列化正确
- 引擎 DONE 时 `run_result.json` 存在且 `status == "done"`
- 引擎 HUMAN_PAUSE 时 `status == "paused"` 且 `pause_reason` 非空
- `ap status` 输出包含 `run_result.json` 的数据

---

### Task 7 — answers.json 预置决策注入

**涉及文件**：
- `autopilot/init_project.py`
- `autopilot/agents/loader.py`

**init_project.py 变更**：
- 在 `init_project()` 中创建空的 `answers.json`（只写一次，文件已存在则跳过）
- 空文件内容：`{}`（空 JSON 对象）
- 同时在 `requirements/README.md` 中补充 answers.json 字段说明

**loader.py 变更**：

```python
def _load_answers_md(self, autopilot_dir: Path) -> str:
    """读取 answers.json，格式化为 ## 预设决策 markdown 块。"""
    answers_path = autopilot_dir / "answers.json"
    if not answers_path.exists():
        return ""
    data = json.loads(answers_path.read_text())
    if not data:
        return ""
    lines = ["## 预设决策", "遇到以下技术选型时，直接使用预设值，无需询问："]
    label_map = {
        "database": "数据库",
        "orm": "ORM",
        "auth_strategy": "认证方案",
        "deployment_target": "部署目标",
        "testing_framework": "测试框架",
    }
    for key, val in data.items():
        if key == "custom" and isinstance(val, dict):
            for k, v in val.items():
                lines.append(f"- {k}：{v}")
        else:
            label = label_map.get(key, key)
            lines.append(f"- {label}：{val}")
    return "\n".join(lines)
```

`build_system_prompt()` 调用 `_load_answers_md()`，将结果赋给 `context.answers_md`，并在 prompt 中 knowledge_md 之后插入（`answers_md` 为空时不插入）。

**测试文件**：`tests/test_answers.py`（新建）

**测试用例**：
- `answers.json` 不存在 → `answers_md == ""`
- `answers.json` 为 `{}` → `answers_md == ""`
- 标准 key（database/orm 等）正确格式化为中文标签
- `custom` 嵌套 dict 正确展开
- 注入 prompt 后 `## 预设决策` 区块出现在正确位置
- `init_project()` 创建空 `answers.json`，二次运行不覆盖已有内容

---

### Task 8 — 回归测试 & 覆盖率

**目标**：全量测试通过，覆盖率不低于 80%

**执行步骤**：

```bash
bash scripts/test.sh
```

**检查项**：
- 所有 v0.1 原有测试继续通过（无回归）
- Task 1–7 新增测试全部通过
- `pytest --cov=autopilot --cov-report=term-missing` 覆盖率 ≥ 80%
- 新增文件均符合 200 行以内限制

---

## 三、任务依赖关系

```
Task 1（数据结构）
  ├─→ Task 2（Claude backend 映射）
  ├─→ Task 3（Codex backend 映射）
  ├─→ Task 4（OpenCode backend 映射）
  ├─→ Task 5（引擎重试逻辑）← 依赖 Task 2/3/4 完成
  ├─→ Task 6（run_result 写出）
  └─→ Task 7（answers 注入）

Task 8（回归）← 依赖 Task 2–7 全部完成
```

**并行可行**：Task 2 / Task 3 / Task 4 互相独立，可同时开发。  
Task 6 / Task 7 互相独立，可同时开发（但需 Task 1 先完成）。

---

## 四、文件变更汇总

| 文件 | 操作 |
|---|---|
| `autopilot/backends/base.py` | 新增 `ErrorType` enum，扩展 `BackendResult`/`RunContext` |
| `autopilot/backends/claude_code.py` | 新增 stderr → ErrorType 映射 |
| `autopilot/backends/codex.py` | 新增 stderr → ErrorType 映射 |
| `autopilot/backends/opencode.py` | 新增 stderr → ErrorType 映射 |
| `autopilot/pipeline/engine.py` | 重构 `run_phase()` 重试逻辑，新增 `run_result.json` 写出 |
| `autopilot/pipeline/context.py` | 新增 `RunResult` 数据类 |
| `autopilot/agents/loader.py` | 新增 `_load_answers_md()` + `answers_md` 注入 |
| `autopilot/init_project.py` | 新增创建空 `answers.json` |
| `autopilot/cli.py` | `ap status` 读取 `run_result.json` |
| `tests/test_base_models.py` | 新建 |
| `tests/test_engine_retry.py` | 新建 |
| `tests/test_run_result.py` | 新建 |
| `tests/test_answers.py` | 新建 |
| `tests/test_backend_claude.py` | 扩展 |
| `tests/test_backend_codex.py` | 扩展 |
| `tests/test_backend_opencode.py` | 扩展 |

---

## 五、版本说明

### v0.2 范围（本计划）

- Task 1–8 全部完成后打 `v0.2.0` tag

### v0.3 范围（后续计划）

- **Context Compaction**：`AgentLoader` token 估算 + LLM 压缩 + `summary.md` 写出
- 引擎处理 `context_overflow` 时自动触发 compaction 而非直接 HUMAN_PAUSE

### v0.4 范围（后续计划）

- **Backend 自动 fallback**：读取 `fallback_backends` 配置，`rate_limit` / `quota_exhausted` 时自动切换
- 切换后发 Telegram 通知（原 backend + 新 backend + 原因）
