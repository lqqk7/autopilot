import pytest
from autopilot.pipeline.phases import PhaseRunner, ExitCondition
from autopilot.pipeline.context import Phase, PipelineState, FeatureList, Feature
from pathlib import Path


def test_next_phase_from_init():
    runner = PhaseRunner()
    assert runner.next_phase(Phase.INIT, passed=True) == Phase.INTERVIEW


def test_next_phase_from_interview():
    runner = PhaseRunner()
    assert runner.next_phase(Phase.INTERVIEW, passed=True) == Phase.DOC_GEN


def test_next_phase_from_doc_gen():
    runner = PhaseRunner()
    assert runner.next_phase(Phase.DOC_GEN, passed=True) == Phase.PLANNING


def test_next_phase_from_planning():
    runner = PhaseRunner()
    assert runner.next_phase(Phase.PLANNING, passed=True) == Phase.DEV_LOOP


def test_next_phase_from_code():
    runner = PhaseRunner()
    assert runner.next_phase(Phase.CODE, passed=True) == Phase.TEST


def test_next_phase_from_test_pass():
    runner = PhaseRunner()
    assert runner.next_phase(Phase.TEST, passed=True) == Phase.REVIEW


def test_next_phase_from_test_fail():
    runner = PhaseRunner()
    assert runner.next_phase(Phase.TEST, passed=False) == Phase.FIX


def test_next_phase_from_review_pass():
    runner = PhaseRunner()
    assert runner.next_phase(Phase.REVIEW, passed=True) == Phase.DEV_LOOP


def test_next_phase_from_review_fail():
    runner = PhaseRunner()
    assert runner.next_phase(Phase.REVIEW, passed=False) == Phase.FIX


def test_exit_condition_doc_gen(tmp_path: Path):
    from autopilot.pipeline.phases import REQUIRED_DOCS

    docs = tmp_path / "docs"
    docs.mkdir()
    condition = ExitCondition()
    assert not condition.doc_gen_complete(docs)

    for rel in REQUIRED_DOCS:
        path = docs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * 200)

    assert condition.doc_gen_complete(docs)


def test_exit_condition_delivery(tmp_path: Path):
    from autopilot.pipeline.phases import DELIVERY_DOCS

    docs = tmp_path / "docs"
    docs.mkdir()
    condition = ExitCondition()
    assert not condition.delivery_complete(docs)

    for rel in DELIVERY_DOCS:
        path = docs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * 200)

    assert condition.delivery_complete(docs)
