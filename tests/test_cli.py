from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from autopilot.cli import main


# ─── ap init ──────────────────────────────────────────────────────────────────

def test_init_creates_autopilot_dir(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert ".autopilot/" in result.output or "Initialized" in result.output


def test_init_with_backend_option(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "--backend", "codex"])
        assert result.exit_code == 0
        assert "codex" in result.output


# ─── ap status ────────────────────────────────────────────────────────────────

def test_status_no_autopilot_dir(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "Not initialized" in result.output


def test_status_reads_state_json(tmp_path: Path) -> None:
    from autopilot.pipeline.context import Phase, PipelineState

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        autopilot_dir = Path.cwd() / ".autopilot"
        autopilot_dir.mkdir()
        PipelineState(phase=Phase.DOC_GEN).save(autopilot_dir / "state.json")

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "DOC_GEN" in result.output


def test_status_reads_run_result_json(tmp_path: Path) -> None:
    from autopilot.pipeline.context import RunResult

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        autopilot_dir = Path.cwd() / ".autopilot"
        autopilot_dir.mkdir()
        rr = RunResult(status="done", phase="DONE", elapsed_seconds=99.0,
                       features_total=3, features_done=3, knowledge_count=2)
        rr.save(autopilot_dir / "run_result.json")

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "done" in result.output
        assert "99.0" in result.output


def test_status_shows_feature_progress(tmp_path: Path) -> None:
    from autopilot.pipeline.context import Feature, FeatureList, Phase, PipelineState

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        autopilot_dir = Path.cwd() / ".autopilot"
        autopilot_dir.mkdir()
        PipelineState(phase=Phase.DEV_LOOP).save(autopilot_dir / "state.json")
        fl = FeatureList(features=[
            Feature(id="f1", title="A", phase="backend", status="completed"),
            Feature(id="f2", title="B", phase="backend", status="pending"),
        ])
        fl.save(autopilot_dir / "feature_list.json")

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "1/2" in result.output


# ─── ap resume ────────────────────────────────────────────────────────────────

def test_resume_no_autopilot_dir(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["resume"])
        assert result.exit_code != 0 or "not found" in result.output.lower()


# ─── ap pause ─────────────────────────────────────────────────────────────────

def test_pause_command_runs(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["pause"])
        assert result.exit_code == 0


# ─── ap knowledge list / search ───────────────────────────────────────────────

def test_knowledge_list_no_autopilot(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["knowledge", "list"])
        assert result.exit_code == 0


def test_knowledge_list_shows_files(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        autopilot_dir = Path.cwd() / ".autopilot"
        (autopilot_dir / "knowledge" / "bugs").mkdir(parents=True)
        (autopilot_dir / "knowledge" / "bugs" / "2026-01-01-test-bug.md").write_text("bug content")

        result = runner.invoke(main, ["knowledge", "list"])
        assert result.exit_code == 0
        assert "test-bug" in result.output or "bug" in result.output


def test_knowledge_search(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        autopilot_dir = Path.cwd() / ".autopilot"
        (autopilot_dir / "knowledge" / "decisions").mkdir(parents=True)
        (autopilot_dir / "knowledge" / "decisions" / "2026-01-01-jwt.md").write_text("JWT is the auth strategy")

        result = runner.invoke(main, ["knowledge", "search", "jwt"])
        assert result.exit_code == 0
