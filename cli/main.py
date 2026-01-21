"""Main CLI entrypoint for Legal Data Factory.

Usage:
    ldf doctor          Check secrets + database connection
    ldf run <job>       Run a specific job
    ldf controller      Start continuous controller loop
    ldf status          Show coverage status summary
    ldf init-db         Initialize database schema
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="ldf",
    help="Legal Data Factory - EU legislation & case law pipeline",
    add_completion=False,
)
console = Console()


@app.command()
def doctor() -> None:
    """Check configuration, secrets, and database connection."""
    import os

    from dotenv import load_dotenv

    load_dotenv(".env.local")

    console.print("\n[bold]Legal Data Factory - System Check[/bold]\n")

    # Check environment variables
    console.print("[bold]Environment Variables:[/bold]")
    env_vars = [
        ("DATABASE_URL", "Neon Postgres connection"),
        ("GITHUB_TOKEN", "GitHub API access"),
        ("EURLEX_API_KEY", "EUR-Lex API (optional)"),
    ]

    for var, description in env_vars:
        value = os.getenv(var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            console.print(f"  ✓ {var}: {masked} ({description})")
        else:
            console.print(f"  ✗ {var}: [red]not set[/red] ({description})")

    # Check database connection
    console.print("\n[bold]Database Connection:[/bold]")
    try:
        from core.storage.database import Database

        db = Database()
        result = db.check_connection()
        if result["status"] == "ok":
            console.print(f"  ✓ Connected to {result['database']}")
            console.print(f"    Version: {result['version'][:50]}...")
        else:
            console.print(f"  ✗ [red]Connection failed: {result['message']}[/red]")
    except Exception as e:
        console.print(f"  ✗ [red]Error: {e}[/red]")

    # Check configs
    console.print("\n[bold]Jurisdiction Configs:[/bold]")
    configs_dir = Path("configs/jurisdictions")
    if configs_dir.exists():
        yaml_files = list(configs_dir.glob("*.yaml"))
        console.print(f"  ✓ Found {len(yaml_files)} jurisdiction configs")
    else:
        console.print("  ✗ [red]configs/jurisdictions not found[/red]")

    # Check jobs directory
    console.print("\n[bold]Jobs Directory:[/bold]")
    jobs_dir = Path("jobs")
    if jobs_dir.exists():
        job_files = list(jobs_dir.glob("**/*.py"))
        job_files = [f for f in job_files if not f.name.startswith("__")]
        console.print(f"  ✓ Found {len(job_files)} job files")
    else:
        console.print("  ✗ [red]jobs directory not found[/red]")

    console.print()


@app.command()
def status() -> None:
    """Show coverage status summary by jurisdiction."""
    from core.models.jurisdiction import load_all_jurisdictions

    configs_dir = Path("configs/jurisdictions")
    if not configs_dir.exists():
        console.print("[red]Error: configs/jurisdictions not found[/red]")
        raise typer.Exit(1)

    jurisdictions = load_all_jurisdictions(configs_dir)

    # Create status table
    table = Table(title="EU Coverage Status")
    table.add_column("ISO", style="cyan")
    table.add_column("Country", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Sources", justify="right")
    table.add_column("Status", style="green")
    table.add_column("API", justify="center")

    for iso_code in sorted(jurisdictions.keys()):
        config = jurisdictions[iso_code]
        name = config.name.get("en", iso_code)
        sys_type = config.legal_system_type.value
        num_sources = len(config.legislation_sources) + len(config.case_law_sources)
        api = "✓" if config.api_available else "✗"

        table.add_row(
            iso_code,
            name[:20],
            sys_type,
            str(num_sources),
            config.status,
            api,
        )

    console.print()
    console.print(table)
    console.print(f"\nTotal jurisdictions: {len(jurisdictions)}")


@app.command("init-db")
def init_db() -> None:
    """Initialize database schema."""
    console.print("[bold]Initializing database schema...[/bold]")

    try:
        from core.storage.database import Database

        db = Database()
        db.init_schema()
        console.print("[green]✓ Schema initialized successfully[/green]")
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def run(
    job_id: str = typer.Argument(..., help="Job ID (e.g., eu/eurlex_legislation)"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Limit documents"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Don't write to database"),
) -> None:
    """Run a specific scraper job."""
    console.print(f"\n[bold]Running job: {job_id}[/bold]")
    console.print(f"  Limit: {limit or 'none'}")
    console.print(f"  Dry run: {dry_run}")

    # Parse job_id to get jurisdiction and source
    parts = job_id.split("/")
    if len(parts) != 2:
        console.print("[red]Invalid job ID format. Expected: <iso>/<source>[/red]")
        raise typer.Exit(1)

    jurisdiction, source = parts

    # Check if job file exists
    job_file = Path(f"jobs/{jurisdiction}/{source}.py")
    if not job_file.exists():
        console.print(f"[yellow]Warning: Job file {job_file} not found[/yellow]")
        console.print("Creating placeholder...")

    console.print("\n[yellow]Job execution not yet implemented.[/yellow]")
    console.print("To implement this job, create:")
    console.print(f"  jobs/{jurisdiction}/{source}.py")


@app.command()
def controller(
    once: bool = typer.Option(False, "--once", help="Run one iteration only"),
    interval: int = typer.Option(300, "--interval", "-i", help="Seconds between runs"),
) -> None:
    """Start the continuous controller loop.

    The controller:
    1. Reads configs/jurisdictions/*.yaml for tasks
    2. Checks GitHub issues for blocked/done status
    3. Runs the next available job
    4. Updates watermarks and creates issues on failure
    """
    import time

    console.print("[bold]Starting Legal Data Factory Controller[/bold]\n")
    console.print(f"  Interval: {interval}s")
    console.print(f"  Mode: {'single run' if once else 'continuous'}")

    iteration = 0
    while True:
        iteration += 1
        console.print(f"\n[bold cyan]--- Iteration {iteration} ---[/bold cyan]")

        try:
            # Load jurisdiction configs
            from core.models.jurisdiction import load_all_jurisdictions

            configs_dir = Path("configs/jurisdictions")
            jurisdictions = load_all_jurisdictions(configs_dir)
            console.print(f"Loaded {len(jurisdictions)} jurisdiction configs")

            # Find next task
            next_task = _find_next_task(jurisdictions)
            if next_task:
                console.print(f"Next task: {next_task}")
                # TODO: Execute task
                console.print("[yellow]Task execution not yet implemented[/yellow]")
            else:
                console.print("[green]No pending tasks - all caught up![/green]")

        except Exception as e:
            console.print(f"[red]Error in iteration: {e}[/red]")

        if once:
            break

        console.print(f"\nSleeping for {interval}s...")
        time.sleep(interval)


def _find_next_task(jurisdictions: dict) -> str | None:
    """Find the next task to execute based on priority.

    Returns job_id of next task, or None if no tasks available.
    """
    # Priority order:
    # 1. P0 tasks in planned status
    # 2. P1 tasks in planned status
    # TODO: Check GitHub issues for blocked status
    # TODO: Check watermarks for incomplete jobs

    for priority in ["p0", "p1"]:
        for _iso_code, config in jurisdictions.items():
            if config.coverage_plan:
                # Check legislation targets
                for target in config.coverage_plan.p80_legislation.get("targets", []):
                    if (
                        target.get("priority") == priority
                        and target.get("status") == "planned"
                    ):
                        # Find the source and job_id
                        source_ref = target.get("source_ref")
                        for source in config.legislation_sources:
                            if source.name == source_ref and source.job_id:
                                return source.job_id

                # Check case law targets
                for target in config.coverage_plan.p80_case_law.get("targets", []):
                    if (
                        target.get("priority") == priority
                        and target.get("status") == "planned"
                    ):
                        source_ref = target.get("source_ref")
                        for source in config.case_law_sources:
                            if source.name == source_ref and source.job_id:
                                return source.job_id

    return None


@app.command()
def stats() -> None:
    """Show database statistics."""
    try:
        from core.storage.database import Database

        db = Database()
        db_stats = db.get_stats()

        console.print("\n[bold]Database Statistics[/bold]\n")

        # Documents by jurisdiction
        if db_stats["documents_by_jurisdiction"]:
            table = Table(title="Documents by Jurisdiction")
            table.add_column("Jurisdiction", style="cyan")
            table.add_column("Type", style="yellow")
            table.add_column("Count", justify="right", style="green")

            for row in db_stats["documents_by_jurisdiction"]:
                table.add_row(row["jurisdiction"], row["doc_type"], str(row["count"]))

            console.print(table)

        console.print(f"\nTotal documents: {db_stats['total_documents']}")
        console.print(f"Total texts: {db_stats['total_texts']}")
        console.print(f"Total runs: {db_stats['total_runs']}")

        # Recent runs
        if db_stats["recent_runs"]:
            console.print("\n[bold]Recent Runs:[/bold]")
            for recent_run in db_stats["recent_runs"][:5]:
                status_color = (
                    "green" if recent_run["status"] == "completed" else
                    "red" if recent_run["status"] == "failed" else
                    "yellow"
                )
                console.print(
                    f"  {recent_run['job_id']}: [{status_color}]{recent_run['status']}"
                    f"[/{status_color}] "
                    f"(+{recent_run['documents_created']} / -{recent_run['documents_failed']})"
                )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(
            "[yellow]Tip: Make sure DATABASE_URL is set and database is initialized[/yellow]"
        )


@app.command("create-issues")
def create_issues(
    dry_run: bool = typer.Option(
        True, "--dry-run/--execute", help="Preview without creating"
    ),
) -> None:
    """Create GitHub issues from jurisdiction configs."""
    import os

    from core.models.jurisdiction import load_all_jurisdictions

    if not os.getenv("GITHUB_TOKEN") and not dry_run:
        console.print("[red]Error: GITHUB_TOKEN not set[/red]")
        raise typer.Exit(1)

    configs_dir = Path("configs/jurisdictions")
    jurisdictions = load_all_jurisdictions(configs_dir)

    console.print(f"\n[bold]{'Preview' if dry_run else 'Creating'} GitHub Issues[/bold]\n")

    issue_count = 0
    for iso_code, config in sorted(jurisdictions.items()):
        if config.coverage_plan:
            # Create issues for P0 legislation targets
            for target in config.coverage_plan.p80_legislation.get("targets", []):
                if target.get("priority") == "p0" and target.get("status") == "planned":
                    issue_count += 1
                    source_ref = target.get("source_ref")
                    title = f"[JOB] {iso_code}/{source_ref}: Implement legislation scraper"
                    console.print(f"  {issue_count}. {title}")

            # Create issues for P0 case law targets
            for target in config.coverage_plan.p80_case_law.get("targets", []):
                if target.get("priority") == "p0" and target.get("status") == "planned":
                    issue_count += 1
                    source_ref = target.get("source_ref")
                    title = f"[JOB] {iso_code}/{source_ref}: Implement case law scraper"
                    console.print(f"  {issue_count}. {title}")

    console.print(f"\nTotal issues to create: {issue_count}")

    if dry_run:
        console.print("\n[yellow]Dry run - no issues created. Use --execute to create.[/yellow]")


if __name__ == "__main__":
    app()
