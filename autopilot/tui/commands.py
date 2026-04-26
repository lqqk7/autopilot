"""Slash command registry for the Autopilot TUI.

Commands are plain dataclasses; the App handles execution so this module has
no import dependency on Textual internals and stays easy to test.

Descriptions are fetched from the i18n module at call-time so they update
immediately when the user switches language with /lang.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from autopilot.tui.i18n import t


@dataclass
class Command:
    name: str                       # e.g. "run"
    description_key: str            # i18n key, e.g. "cmd_run"
    usage: str                      # e.g. "/run"
    aliases: list[str] = field(default_factory=list)
    args_hint: str = ""             # displayed after the command in the suggestion list

    @property
    def description(self) -> str:
        """Return translated description (live, respects current language)."""
        return t(self.description_key)


# ── command definitions ───────────────────────────────────────────────────────

COMMANDS: list[Command] = [
    Command(
        name="init",
        description_key="cmd_init",
        usage="/init",
        args_hint="[--backend claude|codex|opencode]",
    ),
    Command(name="run",      description_key="cmd_run",      usage="/run"),
    Command(name="resume",   description_key="cmd_resume",   usage="/resume"),
    Command(name="check",    description_key="cmd_check",    usage="/check"),
    Command(
        name="add",
        description_key="cmd_add",
        usage="/add",
        args_hint='TITLE [--phase backend|frontend|fullstack|infra] [--depends-on IDs]',
    ),
    Command(
        name="redo",
        description_key="cmd_redo",
        usage="/redo",
        args_hint="[FEATURE_ID | --failed]",
    ),
    Command(name="status",   description_key="cmd_status",   usage="/status"),
    Command(
        name="sessions",
        description_key="cmd_sessions",
        usage="/sessions",
        args_hint="[show SESSION_ID]",
    ),
    Command(
        name="knowledge",
        description_key="cmd_knowledge",
        usage="/knowledge",
        args_hint="[list | search QUERY]",
        aliases=["kb"],
    ),
    Command(
        name="lang",
        description_key="cmd_lang",
        usage="/lang",
        args_hint="[en | zh]",
    ),
    Command(
        name="set",
        description_key="cmd_set",
        usage="/set",
        args_hint="KEY VALUE  (backend|workers|parallel-backends|fallback-backends|log-level|model|review-mode|review-backend)",
    ),
    Command(name="config",   description_key="cmd_config",   usage="/config"),
    Command(name="reload",   description_key="cmd_reload",   usage="/reload"),
    # ── v0.4–v0.9 commands ────────────────────────────────────────────────────
    Command(name="missions",   description_key="cmd_missions",   usage="/missions"),
    Command(
        name="handoff",
        description_key="cmd_handoff",
        usage="/handoff",
        args_hint="[latest | ID]",
    ),
    Command(
        name="principles",
        description_key="cmd_principles",
        usage="/principles",
        args_hint="[list | add PHASE RULE]",
    ),
    Command(
        name="skills",
        description_key="cmd_skills",
        usage="/skills",
        args_hint="[list | match QUERY]",
    ),
    Command(name="help",     description_key="cmd_help",     usage="/help", aliases=["?"]),
    Command(name="quit",     description_key="cmd_quit",     usage="/quit", aliases=["exit", "q"]),
]

# ── lookup helpers ────────────────────────────────────────────────────────────

_BY_NAME: dict[str, Command] = {}
for _cmd in COMMANDS:
    _BY_NAME[_cmd.name] = _cmd
    for _alias in _cmd.aliases:
        _BY_NAME[_alias] = _cmd


def lookup(name: str) -> Command | None:
    """Return Command for a name or alias, or None if not found."""
    return _BY_NAME.get(name.lstrip("/").lower())


def completions_for(prefix: str) -> list[tuple[str, str]]:
    """Return [(slash_usage, description)] matching the given prefix.

    Descriptions are fetched live from i18n so they reflect the current language.
    prefix should be the raw input string, e.g. "/" or "/re".
    """
    clean = prefix.lstrip("/").lower()
    results = []
    seen: set[str] = set()
    for cmd in COMMANDS:
        if cmd.name not in seen and cmd.name.startswith(clean):
            hint = f"  {cmd.args_hint}" if cmd.args_hint else ""
            results.append((f"/{cmd.name}{hint}", cmd.description))
            seen.add(cmd.name)
    return results


def parse(raw: str) -> tuple[str, list[str]]:
    """Split raw input into (command_name, args).

    "/redo feat-005" → ("redo", ["feat-005"])
    "/redo --failed" → ("redo", ["--failed"])
    "/quit"          → ("quit", [])
    """
    parts = raw.strip().lstrip("/").split()
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]
