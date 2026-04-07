import pytest
from autopilot.utils.toposort import topological_sort
from autopilot.pipeline.context import Feature


def test_toposort_no_deps():
    features = [
        Feature(id="feat-001", title="A", phase="backend"),
        Feature(id="feat-002", title="B", phase="backend"),
    ]
    result = topological_sort(features)
    ids = [f.id for f in result]
    assert set(ids) == {"feat-001", "feat-002"}


def test_toposort_with_deps():
    features = [
        Feature(id="feat-002", title="B", phase="backend", depends_on=["feat-001"]),
        Feature(id="feat-001", title="A", phase="backend"),
    ]
    result = topological_sort(features)
    ids = [f.id for f in result]
    assert ids.index("feat-001") < ids.index("feat-002")


def test_toposort_circular_raises():
    features = [
        Feature(id="feat-001", title="A", phase="backend", depends_on=["feat-002"]),
        Feature(id="feat-002", title="B", phase="backend", depends_on=["feat-001"]),
    ]
    with pytest.raises(ValueError, match="circular"):
        topological_sort(features)
