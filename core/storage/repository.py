"""Repository classes for database operations."""

import json
from datetime import datetime
from typing import Any

from core.models.document import Document, DocumentType
from core.models.run import Run, RunStatus, Watermark
from core.storage.database import Database


class DocumentRepository:
    """Repository for document operations."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, doc: Document) -> str:
        """Insert or update a document."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (
                    id, jurisdiction, doc_type, source_system,
                    canonical_id, secondary_ids, title, title_native,
                    language, languages_available,
                    date_document, date_publication, date_entry_into_force, date_repeal,
                    in_force, subject_matters, keywords,
                    legal_basis, amends, amended_by, repeals, repealed_by,
                    court, court_chamber, court_ecli_code, case_number, decision_type, parties,
                    source_url, canonical_url, source_last_modified, raw_metadata
                ) VALUES (
                    %(id)s, %(jurisdiction)s, %(doc_type)s, %(source_system)s,
                    %(canonical_id)s, %(secondary_ids)s, %(title)s, %(title_native)s,
                    %(language)s, %(languages_available)s,
                    %(date_document)s, %(date_publication)s, %(date_entry_into_force)s, %(date_repeal)s,
                    %(in_force)s, %(subject_matters)s, %(keywords)s,
                    %(legal_basis)s, %(amends)s, %(amended_by)s, %(repeals)s, %(repealed_by)s,
                    %(court)s, %(court_chamber)s, %(court_ecli_code)s, %(case_number)s, %(decision_type)s, %(parties)s,
                    %(source_url)s, %(canonical_url)s, %(source_last_modified)s, %(raw_metadata)s
                )
                ON CONFLICT (jurisdiction, source_system, canonical_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    title_native = EXCLUDED.title_native,
                    languages_available = EXCLUDED.languages_available,
                    date_document = EXCLUDED.date_document,
                    date_publication = EXCLUDED.date_publication,
                    date_entry_into_force = EXCLUDED.date_entry_into_force,
                    date_repeal = EXCLUDED.date_repeal,
                    in_force = EXCLUDED.in_force,
                    subject_matters = EXCLUDED.subject_matters,
                    keywords = EXCLUDED.keywords,
                    legal_basis = EXCLUDED.legal_basis,
                    amends = EXCLUDED.amends,
                    amended_by = EXCLUDED.amended_by,
                    repeals = EXCLUDED.repeals,
                    repealed_by = EXCLUDED.repealed_by,
                    court = EXCLUDED.court,
                    court_chamber = EXCLUDED.court_chamber,
                    case_number = EXCLUDED.case_number,
                    decision_type = EXCLUDED.decision_type,
                    parties = EXCLUDED.parties,
                    source_url = EXCLUDED.source_url,
                    canonical_url = EXCLUDED.canonical_url,
                    source_last_modified = EXCLUDED.source_last_modified,
                    raw_metadata = EXCLUDED.raw_metadata,
                    updated_at = NOW()
                RETURNING id
                """,
                {
                    "id": doc.id,
                    "jurisdiction": doc.jurisdiction,
                    "doc_type": doc.doc_type.value,
                    "source_system": doc.source_system,
                    "canonical_id": doc.canonical_id,
                    "secondary_ids": json.dumps(doc.secondary_ids),
                    "title": doc.title,
                    "title_native": doc.title_native,
                    "language": doc.language,
                    "languages_available": doc.languages_available,
                    "date_document": doc.date_document,
                    "date_publication": doc.date_publication,
                    "date_entry_into_force": doc.date_entry_into_force,
                    "date_repeal": doc.date_repeal,
                    "in_force": doc.in_force,
                    "subject_matters": doc.subject_matters,
                    "keywords": doc.keywords,
                    "legal_basis": doc.legal_basis,
                    "amends": doc.amends,
                    "amended_by": doc.amended_by,
                    "repeals": doc.repeals,
                    "repealed_by": doc.repealed_by,
                    "court": doc.court,
                    "court_chamber": doc.court_chamber,
                    "court_ecli_code": doc.court_ecli_code,
                    "case_number": doc.case_number,
                    "decision_type": doc.decision_type,
                    "parties": doc.parties,
                    "source_url": doc.source_url,
                    "canonical_url": doc.canonical_url,
                    "source_last_modified": doc.source_last_modified,
                    "raw_metadata": json.dumps(doc.raw_metadata),
                },
            )
            row = cur.fetchone()
            return str(row["id"]) if row else doc.id

    def get_by_canonical_id(
        self, jurisdiction: str, source_system: str, canonical_id: str
    ) -> Document | None:
        """Get a document by its canonical ID."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM documents
                WHERE jurisdiction = %s AND source_system = %s AND canonical_id = %s
                """,
                (jurisdiction, source_system, canonical_id),
            )
            row = cur.fetchone()
            if row:
                return self._row_to_document(row)
            return None

    def count_by_jurisdiction(self) -> dict[str, int]:
        """Count documents by jurisdiction."""
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT jurisdiction, COUNT(*) as count
                FROM documents
                GROUP BY jurisdiction
            """)
            return {row["jurisdiction"]: row["count"] for row in cur.fetchall()}

    def _row_to_document(self, row: dict[str, Any]) -> Document:
        """Convert database row to Document model."""
        return Document(
            id=str(row["id"]),
            jurisdiction=row["jurisdiction"],
            doc_type=DocumentType(row["doc_type"]),
            source_system=row["source_system"],
            canonical_id=row["canonical_id"],
            secondary_ids=row["secondary_ids"] or {},
            title=row["title"],
            title_native=row["title_native"],
            language=row["language"],
            languages_available=row["languages_available"] or [],
            date_document=row["date_document"],
            date_publication=row["date_publication"],
            date_entry_into_force=row["date_entry_into_force"],
            date_repeal=row["date_repeal"],
            in_force=row["in_force"],
            subject_matters=row["subject_matters"] or [],
            keywords=row["keywords"] or [],
            legal_basis=row["legal_basis"] or [],
            amends=row["amends"] or [],
            amended_by=row["amended_by"] or [],
            repeals=row["repeals"] or [],
            repealed_by=row["repealed_by"] or [],
            court=row["court"],
            court_chamber=row["court_chamber"],
            court_ecli_code=row["court_ecli_code"],
            case_number=row["case_number"],
            decision_type=row["decision_type"],
            parties=row["parties"] or [],
            source_url=row["source_url"],
            canonical_url=row["canonical_url"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            source_last_modified=row["source_last_modified"],
            raw_metadata=row["raw_metadata"] or {},
        )


class RunRepository:
    """Repository for run tracking operations."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, run: Run) -> str:
        """Create a new run record."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (
                    id, job_id, jurisdiction, source_system,
                    status, config, doc_limit, dry_run,
                    runner_version, runner_host, github_run_id, github_issue
                ) VALUES (
                    %(id)s, %(job_id)s, %(jurisdiction)s, %(source_system)s,
                    %(status)s, %(config)s, %(limit)s, %(dry_run)s,
                    %(runner_version)s, %(runner_host)s, %(github_run_id)s, %(github_issue)s
                )
                RETURNING id
                """,
                {
                    "id": run.id,
                    "job_id": run.job_id,
                    "jurisdiction": run.jurisdiction,
                    "source_system": run.source_system,
                    "status": run.status.value,
                    "config": json.dumps(run.config),
                    "limit": run.limit,
                    "dry_run": run.dry_run,
                    "runner_version": run.runner_version,
                    "runner_host": run.runner_host,
                    "github_run_id": run.github_run_id,
                    "github_issue": run.github_issue,
                },
            )
            row = cur.fetchone()
            return str(row["id"]) if row else run.id

    def update_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
        error_traceback: str | None = None,
    ) -> None:
        """Update run status."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE runs SET
                    status = %(status)s,
                    started_at = COALESCE(%(started_at)s, started_at),
                    completed_at = %(completed_at)s,
                    duration_seconds = CASE
                        WHEN %(completed_at)s IS NOT NULL AND started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM %(completed_at)s - started_at)
                        ELSE duration_seconds
                    END,
                    error_message = %(error_message)s,
                    error_traceback = %(error_traceback)s
                WHERE id = %(id)s
                """,
                {
                    "id": run_id,
                    "status": status.value,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "error_message": error_message,
                    "error_traceback": error_traceback,
                },
            )

    def update_counts(
        self,
        run_id: str,
        *,
        documents_fetched: int = 0,
        documents_created: int = 0,
        documents_updated: int = 0,
        documents_skipped: int = 0,
        documents_failed: int = 0,
    ) -> None:
        """Update document counts."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE runs SET
                    documents_fetched = %(fetched)s,
                    documents_created = %(created)s,
                    documents_updated = %(updated)s,
                    documents_skipped = %(skipped)s,
                    documents_failed = %(failed)s
                WHERE id = %(id)s
                """,
                {
                    "id": run_id,
                    "fetched": documents_fetched,
                    "created": documents_created,
                    "updated": documents_updated,
                    "skipped": documents_skipped,
                    "failed": documents_failed,
                },
            )

    def get_recent(self, limit: int = 20) -> list[Run]:
        """Get recent runs."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM runs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [self._row_to_run(row) for row in cur.fetchall()]

    def _row_to_run(self, row: dict[str, Any]) -> Run:
        """Convert database row to Run model."""
        return Run(
            id=str(row["id"]),
            job_id=row["job_id"],
            jurisdiction=row["jurisdiction"],
            source_system=row["source_system"],
            status=RunStatus(row["status"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_seconds=row["duration_seconds"],
            config=row["config"] or {},
            limit=row["doc_limit"],
            dry_run=row["dry_run"],
            documents_fetched=row["documents_fetched"],
            documents_created=row["documents_created"],
            documents_updated=row["documents_updated"],
            documents_skipped=row["documents_skipped"],
            documents_failed=row["documents_failed"],
            error_message=row["error_message"],
            error_traceback=row["error_traceback"],
            errors=row["errors"] or [],
            watermark_before=row["watermark_before"],
            watermark_after=row["watermark_after"],
            runner_version=row["runner_version"],
            runner_host=row["runner_host"],
            github_run_id=row["github_run_id"],
            github_issue=row["github_issue"],
        )


class WatermarkRepository:
    """Repository for watermark operations."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, job_id: str, jurisdiction: str, source_system: str) -> Watermark | None:
        """Get watermark for a job."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM watermarks
                WHERE job_id = %s AND jurisdiction = %s AND source_system = %s
                """,
                (job_id, jurisdiction, source_system),
            )
            row = cur.fetchone()
            if row:
                return self._row_to_watermark(row)
            return None

    def upsert(self, wm: Watermark) -> None:
        """Insert or update a watermark."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO watermarks (
                    job_id, jurisdiction, source_system,
                    last_id, last_date, last_page, last_cursor, position_data,
                    total_documents, is_complete, completion_date, last_run_id
                ) VALUES (
                    %(job_id)s, %(jurisdiction)s, %(source_system)s,
                    %(last_id)s, %(last_date)s, %(last_page)s, %(last_cursor)s, %(position_data)s,
                    %(total_documents)s, %(is_complete)s, %(completion_date)s, %(last_run_id)s
                )
                ON CONFLICT (job_id, jurisdiction, source_system)
                DO UPDATE SET
                    last_id = EXCLUDED.last_id,
                    last_date = EXCLUDED.last_date,
                    last_page = EXCLUDED.last_page,
                    last_cursor = EXCLUDED.last_cursor,
                    position_data = EXCLUDED.position_data,
                    total_documents = EXCLUDED.total_documents,
                    is_complete = EXCLUDED.is_complete,
                    completion_date = EXCLUDED.completion_date,
                    last_run_id = EXCLUDED.last_run_id
                """,
                {
                    "job_id": wm.job_id,
                    "jurisdiction": wm.jurisdiction,
                    "source_system": wm.source_system,
                    "last_id": wm.last_id,
                    "last_date": wm.last_date,
                    "last_page": wm.last_page,
                    "last_cursor": wm.last_cursor,
                    "position_data": json.dumps(wm.position_data),
                    "total_documents": wm.total_documents,
                    "is_complete": wm.is_complete,
                    "completion_date": wm.completion_date,
                    "last_run_id": wm.last_run_id,
                },
            )

    def _row_to_watermark(self, row: dict[str, Any]) -> Watermark:
        """Convert database row to Watermark model."""
        return Watermark(
            job_id=row["job_id"],
            jurisdiction=row["jurisdiction"],
            source_system=row["source_system"],
            last_id=row["last_id"],
            last_date=row["last_date"],
            last_page=row["last_page"],
            last_cursor=row["last_cursor"],
            position_data=row["position_data"] or {},
            total_documents=row["total_documents"],
            is_complete=row["is_complete"],
            completion_date=row["completion_date"],
            last_run_id=str(row["last_run_id"]) if row["last_run_id"] else None,
            updated_at=row["updated_at"],
            created_at=row["created_at"],
        )
