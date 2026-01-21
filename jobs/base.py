"""Base job class for all data acquisition jobs.

Supports three acquisition methods:
- Bulk downloads: One-time download of complete datasets
- APIs: Incremental updates via REST/SPARQL endpoints
- Scrapers: Web scraping as fallback when no API exists
"""

import uuid
from abc import ABC, abstractmethod
from collections.abc import Generator
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.models.document import Document, DocumentType
from core.models.run import Run, RunStatus, Watermark
from core.secrets import SecretRequirement, SecretValidationResult, validate_secrets
from core.storage.database import Database
from core.storage.repository import DocumentRepository, RunRepository, WatermarkRepository


class MissingCredentialsError(Exception):
    """Raised when a job is missing required credentials.

    This error signals that human intervention is needed to provide
    the necessary API keys or credentials.
    """

    def __init__(self, job_id: str, validation_result: SecretValidationResult):
        self.job_id = job_id
        self.validation_result = validation_result
        self.missing = validation_result.missing

        missing_vars = ", ".join(r.env_var for r in self.missing)
        super().__init__(
            f"Job {job_id} requires credentials: {missing_vars}. "
            f"Run 'ldf check-secrets {job_id}' for details."
        )

    def get_issue_body(self) -> str:
        """Generate GitHub issue body for this error."""
        return self.validation_result.to_issue_body(self.job_id)


class BaseJob(ABC):
    """Base class for all data acquisition jobs.

    Supports:
    - Bulk downloads (preferred): Download complete datasets
    - API access (preferred): Incremental updates via REST/SPARQL
    - Web scraping (fallback): When no structured source exists

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

    # Secret requirements - override in subclass if needed
    required_secrets: list[SecretRequirement] = []
    optional_secrets: list[SecretRequirement] = []

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
        self.doc_repo: DocumentRepository | None = None
        self.run_repo: RunRepository | None = None
        self.watermark_repo: WatermarkRepository | None = None
        if db and not dry_run:
            self.doc_repo = DocumentRepository(db)
            self.run_repo = RunRepository(db)
            self.watermark_repo = WatermarkRepository(db)

        # Run state
        self.run: Run | None = None
        self.watermark: Watermark | None = None

        # Counters
        self.fetched = 0
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.failed = 0

        # Validate secrets (unless dry run)
        self._secrets_validated = False
        self._missing_credentials: SecretValidationResult | None = None

    def validate_credentials(self) -> SecretValidationResult:
        """Validate that all required credentials are available.

        Required secrets MUST be present - the job cannot run without them.
        This applies to both dry-run and real mode, because we need to verify
        the job actually works before it can be committed to main.

        Returns:
            Validation result

        Raises:
            MissingCredentialsError: If required secrets are missing
        """
        result = validate_secrets(self.job_id)

        # Check if any REQUIRED secrets are missing
        if result.missing and self.required_secrets:
            required_missing = [
                r for r in result.missing
                if any(req.env_var == r.env_var for req in self.required_secrets)
            ]

            if required_missing:
                result.missing = required_missing
                raise MissingCredentialsError(self.job_id, result)

        # Optional secrets just get a warning
        if result.missing:
            optional_missing = [r.env_var for r in result.missing]
            print(f"Note: Optional credentials not set: {optional_missing}")

        self._secrets_validated = True
        return result

    def execute(self) -> Run:
        """Execute the job.

        Returns:
            Run record with execution results

        Raises:
            MissingCredentialsError: If required credentials are not configured
        """
        # Validate credentials first
        self.validate_credentials()

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
