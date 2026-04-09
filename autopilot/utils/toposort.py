from __future__ import annotations

from autopilot.pipeline.context import Feature


def topological_sort(features: list[Feature]) -> list[Feature]:
    """Return features in dependency-safe execution order.

    Raises ValueError if a circular dependency is detected.
    """
    by_id = {f.id: f for f in features}
    visited: set[str] = set()
    in_stack: set[str] = set()
    result: list[Feature] = []

    def visit(fid: str) -> None:
        if fid in in_stack:
            raise ValueError(f"circular dependency detected involving {fid}")
        if fid in visited:
            return
        in_stack.add(fid)
        for dep_id in by_id[fid].depends_on:
            if dep_id not in by_id:
                continue  # dependency already completed, skip
            visit(dep_id)
        in_stack.discard(fid)
        visited.add(fid)
        result.append(by_id[fid])

    for fid in by_id:
        visit(fid)

    return result
