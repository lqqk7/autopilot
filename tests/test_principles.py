"""Tests for v0.7 PrinciplesLoader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autopilot.principles.loader import Principle, PrinciplesLoader


@pytest.fixture()
def loader(tmp_path: Path) -> PrinciplesLoader:
    return PrinciplesLoader(autopilot_dir=tmp_path)


def _write_jsonl(path: Path, rules: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rules), encoding="utf-8")


def test_empty_when_no_files(loader: PrinciplesLoader) -> None:
    assert loader.load_for_phase("CODE") == []
    assert loader.build_injection("CODE") == ""


def test_load_project_principles(loader: PrinciplesLoader, tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "principles.jsonl", [
        {"phase": "CODE", "rule": "No eval()", "severity": "error"},
        {"phase": "TEST", "rule": "Coverage >= 80%", "severity": "error"},
    ])
    rules = loader.load_for_phase("CODE")
    assert len(rules) == 1
    assert rules[0].rule == "No eval()"


def test_load_local_principles_override(loader: PrinciplesLoader, tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "principles.jsonl", [
        {"phase": "CODE", "rule": "No eval()", "severity": "warn"},
    ])
    _write_jsonl(tmp_path / "principles.local.jsonl", [
        {"phase": "CODE", "rule": "No eval()", "severity": "error"},
        {"phase": "CODE", "rule": "Local-only rule", "severity": "error"},
    ])
    rules = loader.load_for_phase("CODE")
    rule_texts = [r.rule for r in rules]
    # Deduplication: "No eval()" appears once (local overrides global via dedup)
    assert rule_texts.count("No eval()") == 1
    assert "Local-only rule" in rule_texts


def test_wildcard_phase(loader: PrinciplesLoader, tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "principles.jsonl", [
        {"phase": "*", "rule": "All API calls must have timeouts", "severity": "warn"},
    ])
    for phase in ("CODE", "TEST", "REVIEW", "FIX"):
        rules = loader.load_for_phase(phase)
        assert any(r.rule == "All API calls must have timeouts" for r in rules)


def test_severity_ordering(loader: PrinciplesLoader, tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "principles.jsonl", [
        {"phase": "CODE", "rule": "Info rule", "severity": "info"},
        {"phase": "CODE", "rule": "Warn rule", "severity": "warn"},
        {"phase": "CODE", "rule": "Error rule", "severity": "error"},
    ])
    rules = loader.load_for_phase("CODE")
    severities = [r.severity for r in rules]
    assert severities == ["error", "warn", "info"]


def test_build_injection_contains_sections(loader: PrinciplesLoader, tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "principles.jsonl", [
        {"phase": "CODE", "rule": "No hardcoded secrets", "severity": "error"},
        {"phase": "CODE", "rule": "Add timeouts to API calls", "severity": "warn"},
    ])
    injection = loader.build_injection("CODE")
    assert "## Behavioral Principles" in injection
    assert "Must Follow" in injection
    assert "Should Follow" in injection
    assert "No hardcoded secrets" in injection
    assert "Add timeouts to API calls" in injection


def test_malformed_line_skipped(loader: PrinciplesLoader, tmp_path: Path) -> None:
    (tmp_path / "principles.jsonl").write_text(
        '{"phase": "CODE", "rule": "Valid rule", "severity": "error"}\n'
        'INVALID JSON LINE\n'
        '{"phase": "CODE", "rule": "Another valid", "severity": "warn"}\n',
        encoding="utf-8",
    )
    rules = loader.load_for_phase("CODE")
    assert len(rules) == 2


def test_comment_lines_skipped(loader: PrinciplesLoader, tmp_path: Path) -> None:
    (tmp_path / "principles.jsonl").write_text(
        '// This is a comment\n'
        '{"phase": "CODE", "rule": "Real rule", "severity": "warn"}\n',
        encoding="utf-8",
    )
    rules = loader.load_for_phase("CODE")
    assert len(rules) == 1


def test_principle_applies_to() -> None:
    p_all = Principle(phase="*", rule="test", severity="warn")
    p_code = Principle(phase="CODE", rule="test", severity="warn")
    p_test = Principle(phase="TEST", rule="test", severity="warn")

    assert p_all.applies_to("CODE")
    assert p_all.applies_to("TEST")
    assert p_code.applies_to("CODE")
    assert not p_code.applies_to("TEST")
    assert p_test.applies_to("TEST")
    assert not p_test.applies_to("CODE")
