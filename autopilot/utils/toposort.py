from __future__ import annotations

from autopilot.pipeline.context import Feature


def topological_sort(
    features: list[Feature],
    all_feature_ids: set[str] | None = None,
) -> list[Feature]:
    """Return features in dependency-safe execution order.

    Args:
        features: Pending features to sort.
        all_feature_ids: Complete set of valid IDs (pending + completed).
            When provided, a dependency not in this set raises ValueError.
            When None, unknown deps are treated as already-completed (legacy behaviour).

    Raises:
        ValueError: On circular dependency or (when all_feature_ids given) unknown dep.
    """
    by_id = {f.id: f for f in features}
    visited: set[str] = set()
    in_stack: set[str] = set()
    result: list[Feature] = []

    def visit(fid: str) -> None:
        if fid in in_stack:
            raise ValueError(f"circular dependency detected involving {fid!r}")
        if fid in visited:
            return
        in_stack.add(fid)
        for dep_id in by_id[fid].depends_on:
            if dep_id not in by_id:
                if all_feature_ids is not None and dep_id not in all_feature_ids:
                    raise ValueError(
                        f"feature {fid!r} depends on unknown ID {dep_id!r}"
                    )
                continue  # dep is completed (not in pending list) — safe to skip
            visit(dep_id)
        in_stack.discard(fid)
        visited.add(fid)
        result.append(by_id[fid])

    for fid in by_id:
        visit(fid)

    return result
