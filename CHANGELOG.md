# Changelog

All notable changes to Autopilot are documented here.

---

## [0.9.0] — 2026-04-27

### v0.4 — State Model Refactoring

**Problem:** A single `state.json` tracked all state. Feature-level progress had no independent representation, making debugging and recovery fragile.

**Changes:**
- Added `Mission`, `FeatureState`, `Checkpoint` Pydantic models to `pipeline/context.py`
- New `MissionStore` class manages `.autopilot/missions/<mission-id>/` directory hierarchy
- Engine auto-creates a Mission at DEV_LOOP start, writes per-feature state files (`features/<feat-id>.json`)
- Checkpoints are saved after every feature completes — full pipeline snapshot at each step
- Mission is marked `done` when all features succeed
- Backward compatible: `state.json` and `feature_list.json` unchanged

**New directory structure:**
```
.autopilot/missions/<mission-id>/
├── mission.json
├── features/
│   └── feat-xxx.json   # phase, status, retries, last_backend, timestamps
└── checkpoints/
    └── <ts>.json       # full pipeline+feature state snapshot
```

---

### v0.5 — System-level Persistent Memory

**Problem:** Knowledge accumulated during a project was lost after each project. There was no mechanism to reuse bug fixes or decisions across projects.

**Changes:**
- New `autopilot/knowledge/global_knowledge.py` — `GlobalKnowledge` class
- Global knowledge stored at `~/.autopilot/knowledge/{bugs,decisions,patterns,learnings}/`
- Keyword-based search: `GlobalKnowledge.search(keywords, top_n=5)`
- Engine injects relevant global memories into `run_phase` prompts on every call
- `FeatureWorker` receives and injects global knowledge per feature (`global_knowledge_md` parameter)
- `GlobalKnowledge.write_bug/write_decision/write_pattern/write_learning()` all support optional `tags`

---

### v0.6 — Engine-level Skill Runtime

**Problem:** Best-practice guidelines for specific problem domains (REST APIs, auth, database migrations) had to be baked into individual backend prompts — no reuse, no centralization.

**Changes:**
- New `autopilot/skills/` package: `SkillDef`, `SkillTrigger`, `SkillRegistry`, `SkillRunner`
- 6 built-in skills: `git-pr-workflow`, `api-endpoint-design`, `database-migration`, `security-hardening`, `test-coverage`, `async-concurrency`
- Skills match features by keyword + optional phase filter
- `SkillRunner.build_hints()` generates a formatted prompt block injected before each backend call
- User-defined skills loaded from `~/.autopilot/skills/*.json` (single skill or array)
- `FeatureWorker` instantiates `SkillRunner` and appends hints to every phase prompt

---

### v0.7 — Principles Injection Layer

**Problem:** There was no way to enforce consistent behavioral rules (security mandates, coding standards, coverage requirements) across all agent calls without manually editing prompts.

**Changes:**
- New `autopilot/principles/loader.py` — `PrinciplesLoader` + `Principle` model
- Rules defined in `principles.jsonl` (one JSON object per line)
- Three severity levels: `error` (must follow), `warn` (should follow), `info` (context)
- Phase filter: rules target specific phases or `"*"` for all phases
- Priority order: `principles.local.jsonl` > `principles.jsonl` > `~/.autopilot/principles.jsonl`
- Rules deduplicated across sources; sorted errors-first
- `PrinciplesLoader.build_injection(phase)` formats a markdown block appended to prompts
- Both `PipelineEngine.run_phase()` and `FeatureWorker._run_single_phase()` inject principles

---

### v0.8 — Cross-project Knowledge Network

**Problem:** Global knowledge entries existed as flat Markdown files with no relationships. Finding "what decision fixed this bug" or "what pattern applies here" required manual search.

**Changes:**
- New `autopilot/knowledge/graph.py` — `KnowledgeGraph`, `KnowledgeNode`, `KnowledgeEdge`
- Nodes: knowledge entries (bugs, decisions, patterns, learnings)
- Edges: typed relations — `caused_by`, `fixed_by`, `applies_to`, `decided_in`, `pattern`
- Graph persisted to `~/.autopilot/knowledge/relations.json`
- `KnowledgeGraph.search_nodes(query, top_n)` — keyword search (default) or vector search (optional)
- `KnowledgeGraph.build_context(node_ids)` — formats a markdown context block with relation traversal
- **Optional vector search:** set `AUTOPILOT_EMBED_API_KEY` env var; embeddings cached under `.embeddings/`
- `GlobalKnowledge.write()` auto-registers each entry as a `KnowledgeNode` in the graph
- `_cosine_sim()` utility for vector similarity (no external dependencies)

---

### v0.9 — Handoff Protocol

**Problem:** When a pipeline session ended (paused or completed), the next session started cold — no memory of what had been built, what decisions were made, or what was left to do.

**Changes:**
- New `autopilot/handoff/` package: `Handoff`, `HandoffContext`, `HandoffMission`, `HandoffWriter`, `HandoffLoader`
- `HandoffWriter.write()` creates a structured JSON packet capturing: mission state, completed/pending features, recent decisions, open issues, constraints, knowledge hints, principles
- Handoffs persisted to `.autopilot/handoffs/<handoff-id>.json` (one per session exit)
- `HandoffLoader.latest()` reads the most recent handoff
- `HandoffLoader.inject_into_prompt(prompt)` prepends handoff context to any prompt
- `Handoff.to_prompt_block()` formats the packet as a readable markdown block
- `PipelineEngine` writes a handoff on every exit (HUMAN_PAUSE or DONE)
- `PipelineEngine.run_phase()` calls `HandoffLoader.inject_into_prompt()` before every backend call

---

### Other changes

- `pyproject.toml`: version bumped `0.3.6 → 0.9.0`
- Test suite: 173 → 246 tests (73 new tests across 6 new test files)
- All existing tests continue to pass — no breaking changes to existing APIs

---

## [0.3.6] — 2026-04-16

- TUI: show INTERVIEW guidance in log panel after `HUMAN_PAUSE` event
- Engine: emit `human_pause` event via EventBus after INTERVIEW completes

## [0.3.5] — 2026-04-14

- Fix: backend subprocesses now killed on `/quit` — pipeline no longer survives TUI exit
- Switched `subprocess.run()` → `Popen + communicate()` in `BackendBase`
- Added `BackendBase.stop()` and `_stopped` flag for clean teardown
- `ErrorType.stopped` returned when killed mid-run

## [0.3.4] — 2026-04-13

- TUI: AppHeader 3rd row showing config snapshot (model/review/log/max-workers/parallel/fallback)
- New `/set KEY VALUE` command — writes config.toml and updates header immediately
- New `/config` command — opens config file in system editor
- New `/reload` command — reloads config from disk
- `_load_config()` replaces `_load_language_from_config()` in `app.py`

## [0.3.3] — 2026-04-12

- TUI: `/init`, `/add`, `/knowledge`, `/sessions show` commands implemented
- All TUI commands now have test coverage

## [0.3.2] — 2026-04-10

- Session recorder: structured JSONL event stream
- `ap sessions list` and `ap sessions show` commands

## [0.3.1] — 2026-04-08

- Fallback backend support: `fallback_backends` in config
- Backend switch events emitted to EventBus

## [0.3.0] — 2026-04-05

- Full-screen Textual TUI launched (`autopilot` command)
- EventBus bridging pipeline threads → TUI main loop
- AppHeader with 2-row layout (identity + runtime)
- FeatureTable, LogPanel, OptionList autocomplete

## [0.2.x]

- DAG-aware parallel feature scheduling
- Cross-review mode (`mode = "cross"` / `mode = "backend"`)
- Auto git commit after REVIEW passes
- Telegram notifications

## [0.1.x]

- Initial release
- Single-backend serial pipeline: INTERVIEW → DOC_GEN → PLANNING → DEV_LOOP → DELIVERY
- `ap run`, `ap resume`, `ap status`, `ap check`
