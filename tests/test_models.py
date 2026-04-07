import pytest
from pathlib import Path
from autopilot.pipeline.context import (
    Feature,
    FeatureList,
    PipelineState,
    Phase,
    AgentOutput,
)


def test_feature_defaults():
    f = Feature(id="feat-001", title="用户登录", phase="backend")
    assert f.status == "pending"
    assert f.depends_on == []
    assert f.fix_retries == 0


def test_feature_list_serialization(tmp_path: Path):
    fl = FeatureList(features=[
        Feature(id="feat-001", title="用户登录", phase="backend"),
        Feature(id="feat-002", title="用户注册", phase="backend", depends_on=["feat-001"]),
    ])
    path = tmp_path / "feature_list.json"
    fl.save(path)
    loaded = FeatureList.load(path)
    assert len(loaded.features) == 2
    assert loaded.features[1].depends_on == ["feat-001"]


def test_pipeline_state_serialization(tmp_path: Path):
    state = PipelineState(
        phase=Phase.DOC_GEN,
        current_feature_id=None,
        phase_retries=0,
    )
    path = tmp_path / "state.json"
    state.save(path)
    loaded = PipelineState.load(path)
    assert loaded.phase == Phase.DOC_GEN


def test_agent_output_parse_success():
    raw = """
Some agent output here...

```json autopilot-result
{
  "status": "success",
  "summary": "Generated PRD.md",
  "artifacts": ["docs/PRD.md"],
  "issues": [],
  "next_hint": null
}
```
"""
    output = AgentOutput.parse(raw)
    assert output.status == "success"
    assert output.artifacts == ["docs/PRD.md"]


def test_agent_output_parse_failure():
    raw = "Some output without the required JSON block"
    with pytest.raises(ValueError, match="autopilot-result"):
        AgentOutput.parse(raw)
