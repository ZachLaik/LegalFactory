"""Run and watermark models for tracking job execution."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Status of a job run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Run(BaseModel):
    """Job run record.

    Tracks execution of scraper/parser jobs.
    """

    id: str = Field(..., description="Run ID (UUID)")
    job_id: str = Field(..., description="Job identifier (e.g., eu/eurlex_legislation)")
    jurisdiction: str = Field(..., description="ISO code")
    source_system: str = Field(..., description="Source system name")

    # Execution
    status: RunStatus = RunStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None

    # Configuration
    config: dict[str, Any] = Field(default_factory=dict)
    limit: int | None = Field(None, description="Document limit for this run")
    dry_run: bool = False

    # Results
    documents_fetched: int = 0
    documents_created: int = 0
    documents_updated: int = 0
    documents_skipped: int = 0
    documents_failed: int = 0

    # Error tracking
    error_message: str | None = None
    error_traceback: str | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)

    # Watermark
    watermark_before: str | None = None
    watermark_after: str | None = None

    # Provenance
    runner_version: str | None = None
    runner_host: str | None = None
    github_run_id: str | None = None
    github_issue: int | None = None


class Watermark(BaseModel):
    """Watermark for tracking crawl progress.

    Stores the last successfully processed position for incremental crawling.
    """

    job_id: str = Field(..., description="Job identifier")
    jurisdiction: str = Field(..., description="ISO code")
    source_system: str = Field(..., description="Source system name")

    # Position markers (depends on source)
    last_id: str | None = Field(None, description="Last processed document ID")
    last_date: datetime | None = Field(None, description="Last processed date")
    last_page: int | None = Field(None, description="Last processed page number")
    last_cursor: str | None = Field(None, description="API cursor/token")

    # Metadata
    position_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific position data",
    )

    # State
    total_documents: int | None = Field(None, description="Total docs seen so far")
    is_complete: bool = False
    completion_date: datetime | None = None

    # Provenance
    last_run_id: str | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
