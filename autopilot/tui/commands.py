"""Slash command registry for the Autopilot TUI.

Commands are plain dataclasses; the App handles execution so this module has
no import dependency on Textual internals and stays easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Command:
    name: str                        # e.g. "run"
    description: str
    usage: str                       # e.g. "/run"
    aliases: list[str] = field(default_factory=list)
    args_hint: str = ""              # displayed after the command in the suggestion list


# ── command definitions ───────────────────────────────────────────────────────

COMMANDS: list[Command] = [
    Command(
        name="run",
        description="Start the full pipeline from scratch",
        usage="/run",
    ),
    Command(
        name="resume",
        description="Resume from the last checkpoint",
        usage="/resume",
    ),
    Command(
        name="check",
        description="Pre-flight validation (config, backends, env vars)",
        usage="/check",
    ),
    Command(
        name="redo",
        description="Re-run a specific feature, or all failed features",
        usage="/redo",
        args_hint="[FEATURE_ID | --failed]",
    ),
    Command(
        name="status",
        description="Show current pipeline state and feature list",
        usage="/status",
    ),
    Command(
        name="sessions",
        description="List all recorded sessions",
        usage="/sessions",
    ),
    Command(
        name="help",
        description="Show all available commands",
        usage="/help",
        aliases=["?"],
    ),
    Command(
        name="quit",
        description="Exit Autopilot",
        usage="/quit",
        aliases=["exit", "q"],
    ),
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
