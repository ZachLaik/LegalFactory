"""Base job class for all scrapers."""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Generator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.models.document import Document, DocumentType
from core.models.run import Run, RunStatus, Watermark
from core.storage.database import Database
from core.storage.repository import DocumentRepository, RunRepository, WatermarkRepository


class BaseJob(ABC):
    """Base class for all scraper jobs.

    Subclasses must implement:
    - job_id: Unique job identifier
    - jurisdiction: ISO code
    - source_system: Source system name
    - fetch_documents(): Generator yielding documents
    """

    job_id: str
    jurisdiction: str
    source_system: str
    doc_type: DocumentType

    # Configuration
    rate_limit_delay: float = 1.0  # Seconds between requests
    max_retries: int = 3
    timeout: float = 30.0

    def __init__(
        self,
        db: Database | None = None,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> None:
        """Initialize the job.

        Args:
            db: Database instance (optional for dry runs)
            limit: Maximum documents to fetch
            dry_run: If True, don't write to database
        """
        self.db = db
        self.limit = limit
        self.dry_run = dry_run

        # HTTP client
        self.client = httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "LegalDataFactory/0.1 (legal-data-factory)"},
        )

        # Repositories
        if db and not dry_run:
            self.doc_repo = DocumentRepository(db)
            self.run_repo = RunRepository(db)
            self.watermark_repo = WatermarkRepository(db)
        else:
            self.doc_repo = None
            self.run_repo = None
            self.watermark_repo = None

        # Run state
        self.run: Run | None = None
        self.watermark: Watermark | None = None

        # Counters
        self.fetched = 0
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.failed = 0

    def execute(self) -> Run:
        """Execute the job.

        Returns:
            Run record with execution results
        """
        # Create run record
        self.run = Run(
            id=str(uuid.uuid4()),
            job_id=self.job_id,
            jurisdiction=self.jurisdiction,
            source_system=self.source_system,
            status=RunStatus.RUNNING,
            started_at=datetime.utcnow(),
            limit=self.limit,
            dry_run=self.dry_run,
        )

        if self.run_repo:
            self.run_repo.create(self.run)

        # Load watermark
        if self.watermark_repo:
            self.watermark = self.watermark_repo.get(
                self.job_id, self.jurisdiction, self.source_system
            )

        try:
            # Fetch and process documents
            for doc in self.fetch_documents():
                self.fetched += 1

                if self.limit and self.fetched > self.limit:
                    break

                try:
                    self._process_document(doc)
                except Exception as e:
                    self.failed += 1
                    print(f"Error processing document {doc.canonical_id}: {e}")

            # Mark success
            self.run.status = RunStatus.COMPLETED
            self.run.completed_at = datetime.utcnow()

        except Exception as e:
            self.run.status = RunStatus.FAILED
            self.run.completed_at = datetime.utcnow()
            self.run.error_message = str(e)
            import traceback

            self.run.error_traceback = traceback.format_exc()
            raise

        finally:
            # Update counts
            self.run.documents_fetched = self.fetched
            self.run.documents_created = self.created
            self.run.documents_updated = self.updated
            self.run.documents_skipped = self.skipped
            self.run.documents_failed = self.failed

            # Save run record
            if self.run_repo:
                self.run_repo.update_status(
                    self.run.id,
                    self.run.status,
                    completed_at=self.run.completed_at,
                    error_message=self.run.error_message,
                    error_traceback=self.run.error_traceback,
                )
                self.run_repo.update_counts(
                    self.run.id,
                    documents_fetched=self.fetched,
                    documents_created=self.created,
                    documents_updated=self.updated,
                    documents_skipped=self.skipped,
                    documents_failed=self.failed,
                )

            # Close HTTP client
            self.client.close()

        return self.run

    def _process_document(self, doc: Document) -> None:
        """Process a single document."""
        if self.dry_run:
            print(f"[DRY RUN] Would upsert: {doc.canonical_id}")
            self.created += 1
            return

        if self.doc_repo:
            # Check if exists
            existing = self.doc_repo.get_by_canonical_id(
                doc.jurisdiction, doc.source_system, doc.canonical_id
            )

            self.doc_repo.upsert(doc)

            if existing:
                self.updated += 1
            else:
                self.created += 1

    @abstractmethod
    def fetch_documents(self) -> Generator[Document, None, None]:
        """Fetch documents from the source.

        Yields:
            Document objects to be stored
        """
        ...

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def fetch_url(self, url: str, **kwargs: Any) -> httpx.Response:
        """Fetch a URL with retry logic.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments for httpx

        Returns:
            HTTP response
        """
        import time

        response = self.client.get(url, **kwargs)
        response.raise_for_status()

        # Rate limiting
        time.sleep(self.rate_limit_delay)

        return response
