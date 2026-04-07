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
    click.echo(f"  Next: add your requirements to .autopilot/input/ then run `ap run`")


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
    chosen_backend = backend or config["autopilot"]["backend"]

    click.echo(f"Backend: {chosen_backend}")
    engine = PipelineEngine(project_path=project_path, backend=get_backend(chosen_backend))
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
        state.phase = Phase.DEV_LOOP if state.current_feature_id else Phase.DOC_GEN
        state.phase_retries = 0
        state.pause_reason = None
        state.save(autopilot_dir / "state.json")

    config = toml.loads((autopilot_dir / "config.toml").read_text())
    engine = PipelineEngine(project_path=project_path, backend=get_backend(config["autopilot"]["backend"]))
    click.echo(f"Resuming from phase: {state.phase.value}")
    engine.run()


@main.command()
def status() -> None:
    """Show current pipeline status."""
    from pathlib import Path
    from autopilot.pipeline.context import PipelineState, FeatureList

    autopilot_dir = Path.cwd() / ".autopilot"
    if not autopilot_dir.exists():
        click.echo("Not initialized. Run `ap init` first.")
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


@main.group()
def knowledge() -> None:
    """Manage knowledge base."""


@knowledge.command(name="list")
def knowledge_list() -> None:
    """List knowledge entries."""
    click.echo("Knowledge entries...")


@knowledge.command(name="search")
@click.argument("query")
def knowledge_search(query: str) -> None:
    """Search knowledge base."""
    click.echo(f"Searching: {query}")
