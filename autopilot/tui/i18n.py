"""Internationalization for the Autopilot TUI.

Usage:
    from autopilot.tui.i18n import t, set_language, get_language

    t("welcome")          # → "Autopilot ready. Type /help or /run to start."
    set_language("zh")
    t("welcome")          # → "Autopilot 就绪。输入 /help 或 /run 开始。"
"""
from __future__ import annotations

_LANG: str = "en"

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # startup
        "welcome": "Autopilot ready. Type /help or /run to start.",
        # commands
        "cmd_init":      "Initialize autopilot in the current directory",
        "cmd_run":       "Start the full pipeline from scratch",
        "cmd_resume":    "Resume from the last checkpoint",
        "cmd_check":     "Pre-flight validation (config, backends, env vars)",
        "cmd_add":       "Add a new feature to the backlog",
        "cmd_redo":      "Re-run a specific feature, or all failed features",
        "cmd_status":    "Show current pipeline state and feature list",
        "cmd_sessions":  "List or inspect recorded sessions",
        "cmd_knowledge": "List or search the knowledge base",
        "cmd_help":      "Show all available commands",
        "cmd_quit":      "Exit Autopilot",
        "cmd_lang":      "Switch display language  (en / zh)",
        # header labels
        "lbl_phase":    "Phase",
        "lbl_backend":  "via",
        "lbl_features": "features",
        "lbl_workers":  "workers",
        "lbl_elapsed":  "",
        # table columns
        "col_id":       "ID",
        "col_title":    "Title",
        "col_phase":    "Phase / Status",
        "col_backend":  "Backend",
        "col_retries":  "Retries",
        "col_note":     "Note",
        # lang command feedback
        "lang_switched": "Language switched to English.",
        "lang_unknown":  "Unknown language {lang!r}. Supported: en, zh",
        "lang_current":  "Current language: {lang}",
        # misc
        "pipeline_already_running": "Pipeline already running.",
        "no_state_found": "No state found — run /run first",
        "no_sessions":    "No sessions recorded yet.",
        "no_feature_list": "No feature_list.json — run /run first",
        "redo_not_found":  "Feature {fid!r} not found",
        "redo_usage":      "Usage: /redo FEATURE_ID  or  /redo --failed",
        "redo_reset":      "↩ reset {fid}",
        "redo_done":       "Reset {n} feature(s). Run /resume to continue.",
        "state_not_found": "state.json not found — run /run first",
        "preflight_done":  "Pre-flight done.",
        "starting":        "Starting pipeline…",
        "resuming":        "Resuming pipeline…",
        "lang_restart_note": "(column headers update on restart)",
        "quit_warning":    "Pipeline is running — background threads will be stopped. Run /quit again to confirm.",
        "pipeline_finished": "Pipeline finished → {phase}  ({elapsed})",
    },
    "zh": {
        # startup
        "welcome": "Autopilot 就绪。输入 /help 或 /run 开始。",
        # commands
        "cmd_init":      "在当前目录初始化 autopilot",
        "cmd_run":       "从头开始运行完整流水线",
        "cmd_resume":    "从上次断点继续",
        "cmd_check":     "运行前检测（配置、后端、环境变量）",
        "cmd_add":       "向 Backlog 添加新 Feature",
        "cmd_redo":      "重跑指定 Feature 或所有失败的 Feature",
        "cmd_status":    "显示当前流水线状态和 Feature 列表",
        "cmd_sessions":  "列出或查看 Session 记录",
        "cmd_knowledge": "列出或搜索知识库",
        "cmd_help":      "显示所有可用命令",
        "cmd_quit":      "退出 Autopilot",
        "cmd_lang":      "切换显示语言（en / zh）",
        # header labels
        "lbl_phase":    "阶段",
        "lbl_backend":  "后端",
        "lbl_features": "Feature",
        "lbl_workers":  "Worker",
        "lbl_elapsed":  "",
        # table columns
        "col_id":       "编号",
        "col_title":    "标题",
        "col_phase":    "阶段 / 状态",
        "col_backend":  "后端",
        "col_retries":  "重试",
        "col_note":     "备注",
        # lang command feedback
        "lang_switched": "语言已切换为中文。",
        "lang_unknown":  "未知语言 {lang!r}，支持：en、zh",
        "lang_current":  "当前语言：{lang}",
        # misc
        "pipeline_already_running": "流水线正在运行。",
        "no_state_found": "未找到状态文件 — 请先执行 /run",
        "no_sessions":    "暂无 Session 记录。",
        "no_feature_list": "未找到 feature_list.json — 请先执行 /run",
        "redo_not_found":  "Feature {fid!r} 不存在",
        "redo_usage":      "用法：/redo FEATURE_ID  或  /redo --failed",
        "redo_reset":      "↩ 已重置 {fid}",
        "redo_done":       "已重置 {n} 个 Feature，执行 /resume 继续。",
        "state_not_found": "未找到 state.json — 请先执行 /run",
        "preflight_done":  "预检完成。",
        "starting":        "正在启动流水线…",
        "resuming":        "正在恢复流水线…",
        "lang_restart_note": "（列标题将在重启后更新）",
        "quit_warning":    "流水线正在运行，后台线程将被终止。再次执行 /quit 确认退出。",
        "pipeline_finished": "流水线完成 → {phase}  ({elapsed})",
    },
}


def set_language(lang: str) -> None:
    """Set the active UI language. Supported: 'en', 'zh'."""
    global _LANG
    if lang in _STRINGS:
        _LANG = lang


def get_language() -> str:
    """Return the active language code."""
    return _LANG


def t(key: str, **kwargs: object) -> str:
    """Return translated string for *key* in the active language.

    Supports format substitution: t("redo_done", n=3) → "Reset 3 feature(s)…"
    Falls back to English if key is missing in the active language.
    """
    text = _STRINGS.get(_LANG, {}).get(key) or _STRINGS["en"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
