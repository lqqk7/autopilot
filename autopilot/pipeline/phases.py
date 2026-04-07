from __future__ import annotations

from pathlib import Path

from autopilot.pipeline.context import Phase

MIN_DOC_CHARS = 200

REQUIRED_DOCS = [
    "PRD.md",
    "tech-stack.md",
    "architecture.md",
    "data-model.md",
    "api-design.md",
    "frontend-spec.md",
    "backend-spec.md",
    "test-cases.md",
]

TRANSITIONS: dict[tuple[Phase, bool], Phase] = {
    (Phase.INIT, True): Phase.DOC_GEN,
    (Phase.DOC_GEN, True): Phase.PLANNING,
    (Phase.PLANNING, True): Phase.DEV_LOOP,
    (Phase.CODE, True): Phase.TEST,
    (Phase.TEST, True): Phase.REVIEW,
    (Phase.TEST, False): Phase.FIX,
    (Phase.REVIEW, True): Phase.DEV_LOOP,
    (Phase.REVIEW, False): Phase.FIX,
    (Phase.FIX, True): Phase.CODE,
    (Phase.FIX, False): Phase.CODE,
    (Phase.DOC_UPDATE, True): Phase.KNOWLEDGE,
    (Phase.KNOWLEDGE, True): Phase.DONE,
}


class PhaseRunner:
    def next_phase(self, current: Phase, passed: bool) -> Phase:
        key = (current, passed)
        if key not in TRANSITIONS:
            raise ValueError(f"No transition defined for {current} passed={passed}")
        return TRANSITIONS[key]


class ExitCondition:
    def doc_gen_complete(self, docs_path: Path) -> bool:
        for name in REQUIRED_DOCS:
            f = docs_path / name
            if not f.exists() or len(f.read_text(encoding="utf-8")) < MIN_DOC_CHARS:
                return False
        return True

    def planning_complete(self, feature_list_path: Path) -> bool:
        if not feature_list_path.exists():
            return False
        try:
            from autopilot.pipeline.context import FeatureList
            fl = FeatureList.load(feature_list_path)
            return len(fl.features) > 0
        except Exception:
            return False
