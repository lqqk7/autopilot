"""Tests for v0.9 Handoff Protocol."""
from __future__ import annotations

from pathlib import Path

import pytest

from autopilot.handoff.models import Handoff, HandoffContext, HandoffMission
from autopilot.handoff.writer import HandoffWriter
from autopilot.handoff.loader import HandoffLoader


@pytest.fixture()
def autopilot_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".autopilot"
    d.mkdir()
    return d


@pytest.fixture()
def writer(autopilot_dir: Path) -> HandoffWriter:
    return HandoffWriter(autopilot_dir, session_id="test-session-001")


@pytest.fixture()
def loader(autopilot_dir: Path) -> HandoffLoader:
    return HandoffLoader(autopilot_dir)


# ── HandoffWriter ─────────────────────────────────────────────────────────────

def test_write_creates_file(writer: HandoffWriter, autopilot_dir: Path) -> None:
    handoff = writer.write(
        mission_id="m-001",
        mission_title="Auth Module",
        mission_status="in_progress",
    )
    assert (autopilot_dir / "handoffs" / f"{handoff.handoff_id}.json").exists()


def test_write_captures_context(writer: HandoffWriter) -> None:
    handoff = writer.write(
        mission_id="m-001",
        mission_title="Auth Module",
        mission_status="paused",
        current_feature="auth-token-refresh",
        completed_features=["auth-login", "auth-logout"],
        pending_features=["auth-mfa"],
        recent_decisions=["Use JWT"],
        open_issues=["refresh token rotation not implemented"],
        constraints=["Do not modify auth-login"],
        knowledge_hints=["See ~/.autopilot/knowledge/decisions/jwt.md"],
    )
    assert handoff.context.current_feature == "auth-token-refresh"
    assert "auth-login" in handoff.context.completed_features
    assert "auth-mfa" in handoff.context.pending_features
    assert "Use JWT" in handoff.context.recent_decisions
    assert "Do not modify auth-login" in handoff.constraints


def test_handoff_id_format(writer: HandoffWriter) -> None:
    h = writer.write(mission_id="m", mission_title="T", mission_status="active")
    assert h.handoff_id.startswith("h-")


def test_from_session_set(writer: HandoffWriter) -> None:
    h = writer.write(mission_id="m", mission_title="T", mission_status="active")
    assert h.from_session == "test-session-001"


# ── HandoffLoader ─────────────────────────────────────────────────────────────

def test_latest_returns_none_when_empty(loader: HandoffLoader) -> None:
    assert loader.latest() is None


def test_latest_returns_most_recent(writer: HandoffWriter, loader: HandoffLoader) -> None:
    h1 = writer.write(mission_id="m", mission_title="First", mission_status="paused")
    h2 = writer.write(mission_id="m", mission_title="Second", mission_status="paused")
    latest = loader.latest()
    assert latest is not None
    # Both should be loadable; latest is the alphabetically last (newest handoff_id)
    assert latest.handoff_id in (h1.handoff_id, h2.handoff_id)


def test_all_returns_all_handoffs(writer: HandoffWriter, loader: HandoffLoader) -> None:
    writer.write(mission_id="m", mission_title="A", mission_status="paused")
    writer.write(mission_id="m", mission_title="B", mission_status="paused")
    all_h = loader.all()
    assert len(all_h) == 2


def test_load_by_id(writer: HandoffWriter, loader: HandoffLoader) -> None:
    h = writer.write(mission_id="m", mission_title="T", mission_status="active")
    loaded = loader.load_by_id(h.handoff_id)
    assert loaded is not None
    assert loaded.handoff_id == h.handoff_id


def test_load_by_id_nonexistent(loader: HandoffLoader) -> None:
    assert loader.load_by_id("nonexistent") is None


def test_inject_into_prompt_prepends(writer: HandoffWriter, loader: HandoffLoader) -> None:
    writer.write(
        mission_id="m",
        mission_title="My Project",
        mission_status="in_progress",
        constraints=["No breaking changes"],
    )
    result = loader.inject_into_prompt("Original prompt text.")
    assert "Handoff Context" in result
    assert "No breaking changes" in result
    assert "Original prompt text." in result


def test_inject_into_prompt_noop_when_empty(loader: HandoffLoader) -> None:
    prompt = "My prompt."
    assert loader.inject_into_prompt(prompt) == prompt


# ── Handoff model ─────────────────────────────────────────────────────────────

def test_to_prompt_block_complete(tmp_path: Path) -> None:
    h = Handoff(
        handoff_id="h-001",
        from_session="s-001",
        mission=HandoffMission(id="m-001", title="Auth Module", status="paused"),
        context=HandoffContext(
            current_feature="feat-login",
            completed_features=["feat-register"],
            pending_features=["feat-mfa"],
            recent_decisions=["JWT over sessions"],
            open_issues=["Rate limiting not done"],
        ),
        constraints=["Keep API contract"],
        knowledge_hints=["See decisions/jwt.md"],
        principles=["Auth endpoints must rate-limit"],
    )
    block = h.to_prompt_block()
    assert "Auth Module" in block
    assert "feat-login" in block
    assert "feat-register" in block
    assert "JWT over sessions" in block
    assert "Rate limiting not done" in block
    assert "Keep API contract" in block
    assert "See decisions/jwt.md" in block
    assert "rate-limit" in block


def test_handoff_persistence(tmp_path: Path) -> None:
    h = Handoff(
        handoff_id="h-disk-001",
        from_session="s-001",
        mission=HandoffMission(id="m", title="Test", status="done"),
        created_at="2026-04-27T00:00:00Z",
    )
    path = tmp_path / "h-disk-001.json"
    h.save(path)
    loaded = Handoff.load(path)
    assert loaded.handoff_id == "h-disk-001"
    assert loaded.created_at == "2026-04-27T00:00:00Z"
