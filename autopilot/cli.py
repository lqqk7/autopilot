import click
from autopilot import __version__


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Autopilot — AI coding automation engine."""


@main.command()
@click.option("--backend", type=click.Choice(["claude", "codex", "opencode"]), default="claude", show_default=True)
def init(backend: str) -> None:
    """Initialize autopilot in the current project."""
    from pathlib import Path
    from autopilot.init_project import init_project

    project_path = Path.cwd()
    init_project(project_path=project_path, backend=backend)
    click.echo(f"✓ Initialized .autopilot/ in {project_path}")
    click.echo(f"  Backend: {backend}")
    click.echo(f"  Next: add your requirements to .autopilot/requirements/ then run `ap run`")


@main.command()
@click.option("--backend", type=click.Choice(["claude", "codex", "opencode"]), default=None)
@click.option("--model", default=None, help="Model override (if backend supports it)")
@click.option("--phase", default=None, help="Run a specific phase only (debug)")
@click.option("--feature", default=None, help="Run a specific feature only (debug)")
def run(backend: str | None, model: str | None, phase: str | None, feature: str | None) -> None:
    """Start the full pipeline."""
    from pathlib import Path
    import toml
    from autopilot.backends import get_backend
    from autopilot.pipeline.engine import PipelineEngine

    project_path = Path.cwd()
    autopilot_dir = project_path / ".autopilot"

    if not autopilot_dir.exists():
        click.echo("Error: .autopilot/ not found. Run `ap init` first.", err=True)
        raise SystemExit(1)

    config = toml.loads((autopilot_dir / "config.toml").read_text())
    ap_cfg = config.get("autopilot", {})
    chosen_backend = backend or ap_cfg["backend"]
    max_parallel = ap_cfg.get("max_parallel", 1)
    parallel_backends_names: list[str] = ap_cfg.get("parallel_backends", [])
    parallel_backends = [get_backend(n) for n in parallel_backends_names] if parallel_backends_names else []

    click.echo(f"Backend: {chosen_backend}  parallel: {max(max_parallel, len(parallel_backends))}")
    engine = PipelineEngine(
        project_path=project_path,
        backend=get_backend(chosen_backend),
        max_parallel=max_parallel,
        parallel_backends=parallel_backends,
    )
    engine.run()


@main.command()
def resume() -> None:
    """Resume from last checkpoint."""
    from pathlib import Path
    import toml
    from autopilot.backends import get_backend
    from autopilot.pipeline.context import PipelineState, Phase
    from autopilot.pipeline.engine import PipelineEngine

    project_path = Path.cwd()
    autopilot_dir = project_path / ".autopilot"
    state = PipelineState.load(autopilot_dir / "state.json")

    if state.phase == Phase.HUMAN_PAUSE:
        if state.current_feature_id or state.active_feature_ids:
            next_phase = Phase.DEV_LOOP
        elif state.post_interview_phase is not None:
            next_phase = state.post_interview_phase
        elif state.pause_reason and "interview" in (state.pause_reason or "").lower():
            next_phase = Phase.DOC_GEN
        else:
            next_phase = Phase.DOC_GEN
        state.phase = next_phase
        state.phase_retries = 0
        state.pause_reason = None
        state.post_interview_phase = None
        state.save(autopilot_dir / "state.json")

    config = toml.loads((autopilot_dir / "config.toml").read_text())
    ap_cfg = config.get("autopilot", {})
    max_parallel = ap_cfg.get("max_parallel", 1)
    parallel_backends_names: list[str] = ap_cfg.get("parallel_backends", [])
    parallel_backends = [get_backend(n) for n in parallel_backends_names] if parallel_backends_names else []
    engine = PipelineEngine(
        project_path=project_path,
        backend=get_backend(ap_cfg["backend"]),
        max_parallel=max_parallel,
        parallel_backends=parallel_backends,
    )
    click.echo(f"Resuming from phase: {state.phase.value}")
    engine.run()


@main.command()
def status() -> None:
    """Show current pipeline status."""
    from pathlib import Path
    from autopilot.pipeline.context import PipelineState, FeatureList, RunResult

    autopilot_dir = Path.cwd() / ".autopilot"
    if not autopilot_dir.exists():
        click.echo("Not initialized. Run `ap init` first.")
        return

    run_result_path = autopilot_dir / "run_result.json"
    if run_result_path.exists():
        rr = RunResult.load(run_result_path)
        click.echo(f"状态: {rr.status}")
        click.echo(f"Phase: {rr.phase}")
        click.echo(f"耗时: {rr.elapsed_seconds}s")
        click.echo(f"Features: {rr.features_done}/{rr.features_total}")
        click.echo(f"知识条数: {rr.knowledge_count}")
        click.echo(f"时间: {rr.timestamp}")
        if rr.pause_reason:
            click.echo(f"暂停原因: {rr.pause_reason}")
        return

    state = PipelineState.load(autopilot_dir / "state.json")
    click.echo(f"Phase: {state.phase.value}")
    click.echo(f"Retries: {state.phase_retries}")
    if state.current_feature_id:
        click.echo(f"Feature: {state.current_feature_id}")
    if state.pause_reason:
        click.echo(f"Pause reason: {state.pause_reason}")

    fl_path = autopilot_dir / "feature_list.json"
    if fl_path.exists():
        fl = FeatureList.load(fl_path)
        done = sum(1 for f in fl.features if f.status == "completed")
        click.echo(f"Progress: {done}/{len(fl.features)} features")


@main.command()
def pause() -> None:
    """Pause the pipeline."""
    click.echo("Pausing...")


@main.command(name="add")
@click.argument("title_or_reqfile")
@click.option("--phase", default="backend", type=click.Choice(["backend", "frontend", "fullstack", "infra"]), show_default=True)
@click.option("--depends-on", "depends_on", default="", help="Comma-separated feature IDs this depends on")
@click.option("--test-file", "test_file", default="", help="Test file path")
@click.option("--from-requirements", "from_requirements", is_flag=True, default=False,
              help="Treat argument as a requirements file in .autopilot/requirements/ and re-run planning")
def add_feature(title_or_reqfile: str, phase: str, depends_on: str, test_file: str, from_requirements: bool) -> None:
    """Add new feature(s) to the backlog.

    \b
    Simple mode (quick, single feature):
      ap add "支付宝支付接口" --phase backend --depends-on feat-010

    \b
    Requirements mode (complex, re-runs AI planning for new req doc):
      1. Write new requirements to .autopilot/requirements/payment.md
      2. ap add payment.md --from-requirements
      → Triggers PLANNING phase to decompose new requirements into features
    """
    from pathlib import Path
    from autopilot.pipeline.context import FeatureList, Feature, PipelineState, Phase

    autopilot_dir = Path.cwd() / ".autopilot"
    state = PipelineState.load(autopilot_dir / "state.json")

    if from_requirements:
        # Requirements mode: run INTERVIEW first (to clarify new requirements),
        # then go to PLANNING (not DOC_GEN — existing docs stay, we just extend the plan)
        req_file = autopilot_dir / "requirements" / title_or_reqfile
        if not req_file.exists():
            click.echo(f"Error: requirements file not found: {req_file}", err=True)
            raise SystemExit(1)
        state.phase = Phase.INTERVIEW
        state.phase_retries = 0
        state.current_feature_id = None
        state.active_feature_ids = []
        state.post_interview_phase = Phase.PLANNING
        state.save(autopilot_dir / "state.json")
        click.echo(f"✓ Requirements file: {req_file.name}")
        click.echo("  Starting INTERVIEW → PLANNING flow.")
        click.echo("  Run `ap resume` — autopilot will clarify requirements, then decompose into features.")
        return

    # Simple mode: directly add a single feature
    fl_path = autopilot_dir / "feature_list.json"
    if not fl_path.exists():
        click.echo("Error: feature_list.json not found. Run `ap run` first.", err=True)
        raise SystemExit(1)

    fl = FeatureList.load(fl_path)
    existing_nums = []
    for f in fl.features:
        try:
            existing_nums.append(int(f.id.split("-")[1]))
        except (IndexError, ValueError):
            pass
    next_num = max(existing_nums, default=0) + 1
    new_id = f"feat-{next_num:03d}"

    dep_list = [d.strip() for d in depends_on.split(",") if d.strip()]
    new_feature = Feature(
        id=new_id,
        title=title_or_reqfile,
        phase=phase,
        depends_on=dep_list,
        status="pending",
        test_file=test_file or f"tests/test_{new_id.replace('-', '_')}.py",
    )
    fl.features.append(new_feature)
    fl.save(fl_path)

    if state.phase in (Phase.DONE, Phase.DELIVERY, Phase.KNOWLEDGE, Phase.DOC_UPDATE):
        state.phase = Phase.DEV_LOOP
        state.phase_retries = 0
        state.save(autopilot_dir / "state.json")
        click.echo(f"✓ Added {new_id}: {title_or_reqfile}")
        click.echo("  Pipeline reset to DEV_LOOP. Run `ap resume` to start development.")
    else:
        click.echo(f"✓ Added {new_id}: {title_or_reqfile}")
        click.echo("  Feature queued — will be picked up automatically in DEV_LOOP.")


@main.command(name="redo")
@click.argument("feature_id")
@click.option("--and-dependents", "and_dependents", is_flag=True, default=False,
              help="Also reset features that depend on this one")
def redo_feature(feature_id: str, and_dependents: bool) -> None:
    """Re-run a specific feature (reset to pending and resume).

    Example: ap redo feat-005
             ap redo feat-005 --and-dependents
    """
    from pathlib import Path
    from autopilot.pipeline.context import FeatureList, PipelineState, Phase

    autopilot_dir = Path.cwd() / ".autopilot"
    fl_path = autopilot_dir / "feature_list.json"
    if not fl_path.exists():
        click.echo("Error: feature_list.json not found.", err=True)
        raise SystemExit(1)

    fl = FeatureList.load(fl_path)
    target_ids = {feature_id}

    if and_dependents:
        # Find all features that (transitively) depend on this one
        changed = True
        while changed:
            changed = False
            for f in fl.features:
                if f.id not in target_ids and any(d in target_ids for d in f.depends_on):
                    target_ids.add(f.id)
                    changed = True

    reset_count = 0
    for f in fl.features:
        if f.id in target_ids:
            f.status = "pending"
            f.fix_retries = 0
            reset_count += 1

    if reset_count == 0:
        click.echo(f"Error: feature '{feature_id}' not found.", err=True)
        raise SystemExit(1)

    fl.save(fl_path)

    # Reset pipeline state to DEV_LOOP
    state = PipelineState.load(autopilot_dir / "state.json")
    if state.phase in (Phase.DONE, Phase.DOC_UPDATE, Phase.KNOWLEDGE, Phase.DELIVERY):
        state.phase = Phase.DEV_LOOP
    state.phase_retries = 0
    state.current_feature_id = None
    state.active_feature_ids = []
    state.save(autopilot_dir / "state.json")

    for fid in sorted(target_ids):
        click.echo(f"  ↩ Reset: {fid}")
    click.echo(f"✓ {reset_count} feature(s) reset to pending. Run `ap resume` to re-develop.")




@main.group()
def knowledge() -> None:
    """Manage knowledge base."""


@knowledge.command(name="list")
def knowledge_list() -> None:
    """List knowledge entries."""
    from pathlib import Path
    kb_dir = Path.cwd() / ".autopilot" / "knowledge"
    if not kb_dir.exists():
        click.echo("No knowledge base found.")
        return
    for md in sorted(kb_dir.rglob("*.md")):
        click.echo(f"  {md.relative_to(kb_dir)}")


@knowledge.command(name="search")
@click.argument("query")
def knowledge_search(query: str) -> None:
    """Search knowledge base (local + Zep)."""
    import os
    from pathlib import Path
    from autopilot.knowledge.local import LocalKnowledge
    from autopilot.knowledge.zep import ZepKnowledge

    kb = LocalKnowledge(Path.cwd() / ".autopilot" / "knowledge")
    local_content = kb.read_all()

    matches = [line for line in local_content.splitlines() if query.lower() in line.lower()]
    if matches:
        click.echo("=== 本地结果 ===")
        for m in matches[:10]:
            click.echo(f"  {m}")

    api_key = os.environ.get("AUTOPILOT_ZEP_API_KEY", "")
    if api_key:
        project_name = Path.cwd().name
        zep = ZepKnowledge(api_key=api_key, graph_id=f"project.{project_name}.shared")
        zep_result = zep.recall(query)
        if zep_result:
            click.echo("\n=== Zep 结果 ===")
            click.echo(zep_result)
