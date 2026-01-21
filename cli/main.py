"""Main CLI entrypoint for Legal Data Factory.

Usage:
    ldf doctor          Check secrets + database connection
    ldf run <job>       Run a specific job
    ldf controller      Start continuous controller loop
    ldf status          Show coverage status summary
    ldf init-db         Initialize database schema
"""

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from jobs.base import MissingCredentialsError

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
    """Run a specific data acquisition job."""
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
        console.print(f"[red]Error: Job file {job_file} not found[/red]")
        console.print("\nTo create this job, add:")
        console.print(f"  jobs/{jurisdiction}/{source}.py")
        raise typer.Exit(1)

    # Dynamically import and run the job
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(f"jobs.{jurisdiction}.{source}", job_file)
        if spec is None or spec.loader is None:
            console.print(f"[red]Error: Could not load job module from {job_file}[/red]")
            raise typer.Exit(1)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the job class (look for subclass of BaseJob)
        from jobs.base import BaseJob

        job_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseJob)
                and attr is not BaseJob
                and hasattr(attr, "job_id")
            ):
                job_class = attr
                break

        if job_class is None:
            console.print(f"[red]Error: No job class found in {job_file}[/red]")
            console.print("Job file must contain a class that inherits from BaseJob")
            raise typer.Exit(1)

        # Initialize and run the job
        console.print(f"\n[cyan]Executing {job_class.__name__}...[/cyan]\n")

        job_instance = job_class(db=None, limit=limit, dry_run=dry_run)
        result = job_instance.execute()

        # Show results
        console.print(f"\n[bold]Run completed: {result.status.value}[/bold]")
        console.print(f"  Documents fetched: {result.documents_fetched}")
        console.print(f"  Documents created: {result.documents_created}")
        console.print(f"  Documents updated: {result.documents_updated}")
        console.print(f"  Documents skipped: {result.documents_skipped}")
        console.print(f"  Documents failed: {result.documents_failed}")

        if result.error_message:
            console.print(f"\n[red]Error: {result.error_message}[/red]")
            raise typer.Exit(1)

    except ImportError as e:
        console.print(f"[red]Import error: {e}[/red]")
        console.print("[yellow]Make sure all dependencies are installed: pip install -e '.[dev]'[/yellow]")
        raise typer.Exit(1) from e

    except Exception as e:
        # Check if this is a missing credentials error
        from jobs.base import MissingCredentialsError

        if isinstance(e, MissingCredentialsError):
            console.print("\n[red]BLOCKED: Missing required credentials[/red]")
            console.print(f"\nJob [bold]{job_id}[/bold] requires the following credentials:\n")

            for req in e.missing:
                console.print(f"  [yellow]•[/yellow] [bold]{req.env_var}[/bold]")
                console.print(f"    {req.description}")
                console.print(f"    Required for: {req.required_for}")
                console.print()

            console.print("[bold]How to fix:[/bold]")
            console.print("  1. Obtain the credentials (see instructions above)")
            console.print("  2. Add them to .env.local for local testing")
            console.print("  3. Add them as GitHub Secrets for CI")
            console.print()
            console.print(f"Run [cyan]ldf secrets-template {job_id}[/cyan] for a copy-paste template")

            # In CI, create an issue automatically
            import os

            if os.getenv("CI") and os.getenv("GITHUB_TOKEN"):
                console.print("\n[yellow]Creating GitHub issue for missing credentials...[/yellow]")
                _create_credentials_issue(job_id, e)

            # Exit with special code 78 (EX_CONFIG) to signal configuration error
            raise typer.Exit(78) from e

        console.print(f"[red]Error running job: {e}[/red]")
        import traceback

        if dry_run:
            console.print("\n[dim]" + traceback.format_exc() + "[/dim]")
        raise typer.Exit(1) from e


def _create_credentials_issue(job_id: str, error: "MissingCredentialsError") -> None:
    """Create a GitHub issue for missing credentials."""
    import os

    try:
        from github import Github
        from github.GithubException import UnknownObjectException

        token = os.getenv("GITHUB_TOKEN")
        repo_name = os.getenv("GITHUB_REPOSITORY", "")

        if not token or not repo_name:
            console.print("[yellow]Cannot create issue: GITHUB_TOKEN or GITHUB_REPOSITORY not set[/yellow]")
            return

        g = Github(token)
        repo = g.get_repo(repo_name)

        # Check if issue already exists
        title = f"[BLOCKED] {job_id}: Missing credentials"
        try:
            existing = list(repo.get_issues(state="open", labels=["blocked:credentials"]))
            for existing_issue in existing:
                if existing_issue.title == title:
                    console.print(f"[dim]Issue already exists: #{existing_issue.number}[/dim]")
                    return
        except Exception:
            pass  # Label might not exist yet, continue to create issue

        # Ensure labels exist
        label_configs = [
            ("blocked:credentials", "e99695", "Blocked: needs credentials/API key"),
            ("human-needed", "d93f0b", "Requires human intervention"),
        ]

        labels_to_use = []
        for label_name, color, description in label_configs:
            try:
                repo.get_label(label_name)
                labels_to_use.append(label_name)
            except UnknownObjectException:
                try:
                    repo.create_label(name=label_name, color=color, description=description)
                    labels_to_use.append(label_name)
                    console.print(f"[dim]Created label: {label_name}[/dim]")
                except Exception:
                    pass  # Couldn't create label, continue without it

        # Create new issue
        body = error.get_issue_body()
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=labels_to_use if labels_to_use else None,
        )
        console.print(f"[green]Created issue #{issue.number}[/green]")

    except Exception as e:
        console.print(f"[yellow]Failed to create issue: {e}[/yellow]")


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


def _find_next_task(jurisdictions: dict) -> str | None:  # type: ignore[type-arg]
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
                                return str(source.job_id)

                # Check case law targets
                for target in config.coverage_plan.p80_case_law.get("targets", []):
                    if (
                        target.get("priority") == priority
                        and target.get("status") == "planned"
                    ):
                        source_ref = target.get("source_ref")
                        for source in config.case_law_sources:
                            if source.name == source_ref and source.job_id:
                                return str(source.job_id)

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


@app.command("check-secrets")
def check_secrets(
    job_id: str | None = typer.Argument(None, help="Specific job to check (e.g., fr/legifrance_legislation)"),
    create_issue: bool = typer.Option(False, "--create-issue", help="Create GitHub issue for missing secrets"),
) -> None:
    """Check secrets/credentials status for jobs.

    Shows which secrets are configured and which are missing.
    Can create GitHub issues to request credentials.
    """
    import os

    from dotenv import load_dotenv

    from core.secrets import SECRET_REGISTRY, validate_secrets

    load_dotenv(".env.local")

    console.print("\n[bold]Secrets Status Check[/bold]\n")

    jobs_to_check = [job_id] if job_id else list(SECRET_REGISTRY.keys())

    missing_any = False

    for job_pattern in jobs_to_check:
        result = validate_secrets(job_pattern)

        if result.missing:
            missing_any = True
            console.print(f"[red]✗[/red] [bold]{job_pattern}[/bold] - Missing credentials:")
            for req in result.missing:
                console.print(f"    • {req.env_var}: {req.description}")
        elif result.available:
            console.print(f"[green]✓[/green] [bold]{job_pattern}[/bold] - All credentials available")
        else:
            console.print(f"[dim]○[/dim] [bold]{job_pattern}[/bold] - No credentials required")

    if missing_any and create_issue:
        if not os.getenv("GITHUB_TOKEN"):
            console.print("\n[red]Cannot create issue: GITHUB_TOKEN not set[/red]")
            raise typer.Exit(1)

        console.print("\n[yellow]GitHub issue creation not yet implemented[/yellow]")
        console.print("Would create issue with label: blocked:credentials, human-needed")

    elif missing_any:
        console.print("\n[yellow]Tip: Use --create-issue to create a GitHub issue for missing credentials[/yellow]")

    console.print()


@app.command("secrets-template")
def secrets_template(
    job_id: str = typer.Argument(..., help="Job ID to generate template for"),
) -> None:
    """Generate .env template for a job's required secrets.

    Outputs environment variable declarations that can be added to .env.local
    """
    from core.secrets import get_requirements_for_job

    requirements = get_requirements_for_job(job_id)

    if not requirements:
        console.print(f"[green]No secrets required for {job_id}[/green]")
        return

    console.print(f"# Secrets required for {job_id}")
    console.print("# Add these to your .env.local file\n")

    for req in requirements:
        console.print(f"# {req.description}")
        console.print(f"# How to obtain: {req.how_to_obtain.strip()}")
        console.print(f"{req.env_var}=")
        console.print()


if __name__ == "__main__":
    app()
