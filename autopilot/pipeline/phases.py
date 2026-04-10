from __future__ import annotations

from pathlib import Path

from autopilot.pipeline.context import Phase

MIN_DOC_CHARS = 200

# Technical/design docs generated at project kickoff (DOC_GEN phase)
REQUIRED_DOCS = [
    # 00-overview
    "00-overview/project-overview.md",
    # 01-requirements
    "01-requirements/PRD.md",
    # 03-design
    "03-design/architecture.md",
    "03-design/data-model.md",
    # 04-development
    "04-development/tech-stack.md",
    "04-development/backend-spec.md",
    "04-development/frontend-spec.md",
    # 05-testing
    "05-testing/test-cases.md",
    # 06-api
    "06-api/api-design.md",
]

# Delivery docs generated AFTER all development is complete (DELIVERY phase)
DELIVERY_DOCS = [
    "09-product/product-overview.md",
    "09-product/quick-start.md",
    "09-product/user-manual.md",
]

TRANSITIONS: dict[tuple[Phase, bool], Phase] = {
    (Phase.INIT, True): Phase.INTERVIEW,
    (Phase.INTERVIEW, True): Phase.DOC_GEN,
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
    (Phase.KNOWLEDGE, True): Phase.DELIVERY,
    (Phase.DELIVERY, True): Phase.DONE,
}


class PhaseRunner:
    def next_phase(self, current: Phase, passed: bool) -> Phase:
        key = (current, passed)
        if key not in TRANSITIONS:
            raise ValueError(f"No transition defined for {current} passed={passed}")
        return TRANSITIONS[key]


class ExitCondition:
    def _all_docs_present(self, docs_path: Path, doc_list: list[str]) -> bool:
        for name in doc_list:
            f = docs_path / name
            if not f.exists() or len(f.read_text(encoding="utf-8")) < MIN_DOC_CHARS:
                return False
        return True

    def doc_gen_complete(self, docs_path: Path) -> bool:
        return self._all_docs_present(docs_path, REQUIRED_DOCS)

    def delivery_complete(self, docs_path: Path) -> bool:
        return self._all_docs_present(docs_path, DELIVERY_DOCS)

    def planning_complete(self, feature_list_path: Path) -> bool:
        if not feature_list_path.exists():
            return False
        try:
            from autopilot.pipeline.context import FeatureList
            fl = FeatureList.load(feature_list_path)
            return len(fl.features) > 0
        except Exception:
            return False
