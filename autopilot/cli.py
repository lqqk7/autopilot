import click
from autopilot import __version__


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Autopilot — AI coding automation engine."""


@main.command()
@click.option("--backend", type=click.Choice(["claude", "codex", "opencode"]), default="claude")
def init(backend: str) -> None:
    """Initialize autopilot in the current project."""
    click.echo(f"Initializing with backend: {backend}")


@main.command()
@click.option("--backend", type=click.Choice(["claude", "codex", "opencode"]), default=None)
@click.option("--model", default=None)
@click.option("--phase", default=None)
@click.option("--feature", default=None)
def run(backend: str | None, model: str | None, phase: str | None, feature: str | None) -> None:
    """Start the full pipeline."""
    click.echo("Starting pipeline...")


@main.command()
def resume() -> None:
    """Resume from last checkpoint."""
    click.echo("Resuming...")


@main.command()
def status() -> None:
    """Show current pipeline status."""
    click.echo("Status...")


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
