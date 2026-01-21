"""Database connection and schema management for Neon Postgres."""

import os
from contextlib import contextmanager
from typing import Any, Generator

import psycopg
from psycopg.rows import dict_row
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration from environment."""

    database_url: str = ""
    database_pool_size: int = 5

    class Config:
        env_file = ".env.local"
        env_file_encoding = "utf-8"


# SQL schema for Legal Data Factory
SCHEMA_SQL = """
-- Documents table: normalized metadata for all legal documents
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction VARCHAR(5) NOT NULL,
    doc_type VARCHAR(50) NOT NULL,
    source_system VARCHAR(100) NOT NULL,

    -- Primary identifiers
    canonical_id VARCHAR(500) NOT NULL,
    secondary_ids JSONB DEFAULT '{}',

    -- Metadata
    title TEXT NOT NULL,
    title_native TEXT,
    language VARCHAR(10) NOT NULL,
    languages_available VARCHAR(10)[] DEFAULT '{}',

    -- Temporal
    date_document DATE,
    date_publication DATE,
    date_entry_into_force DATE,
    date_repeal DATE,
    in_force BOOLEAN,

    -- Classification
    subject_matters TEXT[] DEFAULT '{}',
    keywords TEXT[] DEFAULT '{}',

    -- Legal hierarchy
    legal_basis TEXT[] DEFAULT '{}',
    amends TEXT[] DEFAULT '{}',
    amended_by TEXT[] DEFAULT '{}',
    repeals TEXT[] DEFAULT '{}',
    repealed_by TEXT[] DEFAULT '{}',

    -- Court information (case law)
    court VARCHAR(200),
    court_chamber VARCHAR(200),
    court_ecli_code VARCHAR(50),
    case_number VARCHAR(200),
    decision_type VARCHAR(100),
    parties TEXT[] DEFAULT '{}',

    -- Source
    source_url TEXT NOT NULL,
    canonical_url TEXT,

    -- Provenance
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    source_last_modified TIMESTAMPTZ,

    -- Raw metadata
    raw_metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT unique_doc_canonical UNIQUE (jurisdiction, source_system, canonical_id)
);

-- Indexes for documents
CREATE INDEX IF NOT EXISTS idx_documents_jurisdiction ON documents(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_source_system ON documents(source_system);
CREATE INDEX IF NOT EXISTS idx_documents_canonical_id ON documents(canonical_id);
CREATE INDEX IF NOT EXISTS idx_documents_date_document ON documents(date_document);
CREATE INDEX IF NOT EXISTS idx_documents_in_force ON documents(in_force);
CREATE INDEX IF NOT EXISTS idx_documents_court ON documents(court);
CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents(updated_at);

-- Document texts table: content versions
CREATE TABLE IF NOT EXISTS document_texts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Version info
    version VARCHAR(100),
    version_date DATE,
    is_current BOOLEAN DEFAULT TRUE,
    is_consolidated BOOLEAN DEFAULT FALSE,

    -- Content
    content_type VARCHAR(100) NOT NULL,
    content_text TEXT,
    content_html TEXT,
    content_xml TEXT,
    content_hash VARCHAR(64),

    -- Storage
    blob_url TEXT,
    blob_size_bytes BIGINT,

    -- Processing
    extraction_method VARCHAR(100),
    word_count INTEGER,
    char_count INTEGER,

    -- Provenance
    created_at TIMESTAMPTZ DEFAULT NOW(),
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for document_texts
CREATE INDEX IF NOT EXISTS idx_document_texts_document_id ON document_texts(document_id);
CREATE INDEX IF NOT EXISTS idx_document_texts_is_current ON document_texts(is_current);
CREATE INDEX IF NOT EXISTS idx_document_texts_content_hash ON document_texts(content_hash);

-- Runs table: job execution tracking
CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(200) NOT NULL,
    jurisdiction VARCHAR(5) NOT NULL,
    source_system VARCHAR(100) NOT NULL,

    -- Execution
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds FLOAT,

    -- Configuration
    config JSONB DEFAULT '{}',
    doc_limit INTEGER,
    dry_run BOOLEAN DEFAULT FALSE,

    -- Results
    documents_fetched INTEGER DEFAULT 0,
    documents_created INTEGER DEFAULT 0,
    documents_updated INTEGER DEFAULT 0,
    documents_skipped INTEGER DEFAULT 0,
    documents_failed INTEGER DEFAULT 0,

    -- Errors
    error_message TEXT,
    error_traceback TEXT,
    errors JSONB DEFAULT '[]',

    -- Watermark
    watermark_before TEXT,
    watermark_after TEXT,

    -- Provenance
    runner_version VARCHAR(50),
    runner_host VARCHAR(200),
    github_run_id VARCHAR(100),
    github_issue INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for runs
CREATE INDEX IF NOT EXISTS idx_runs_job_id ON runs(job_id);
CREATE INDEX IF NOT EXISTS idx_runs_jurisdiction ON runs(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at DESC);

-- Watermarks table: crawl progress tracking
CREATE TABLE IF NOT EXISTS watermarks (
    job_id VARCHAR(200) NOT NULL,
    jurisdiction VARCHAR(5) NOT NULL,
    source_system VARCHAR(100) NOT NULL,

    -- Position markers
    last_id TEXT,
    last_date TIMESTAMPTZ,
    last_page INTEGER,
    last_cursor TEXT,
    position_data JSONB DEFAULT '{}',

    -- State
    total_documents INTEGER,
    is_complete BOOLEAN DEFAULT FALSE,
    completion_date TIMESTAMPTZ,

    -- Provenance
    last_run_id UUID REFERENCES runs(id),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (job_id, jurisdiction, source_system)
);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_watermarks_updated_at ON watermarks;
CREATE TRIGGER update_watermarks_updated_at
    BEFORE UPDATE ON watermarks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""


class Database:
    """Database connection manager for Neon Postgres."""

    def __init__(self, database_url: str | None = None) -> None:
        """Initialize database connection.

        Args:
            database_url: Postgres connection URL. If not provided, reads from
                         DATABASE_URL environment variable.
        """
        if database_url:
            self.database_url = database_url
        else:
            settings = DatabaseSettings()
            self.database_url = settings.database_url or os.getenv("DATABASE_URL", "")

        if not self.database_url:
            raise ValueError(
                "DATABASE_URL not set. Set it via environment variable or .env.local"
            )

    @contextmanager
    def connection(self) -> Generator[psycopg.Connection[dict[str, Any]], None, None]:
        """Get a database connection."""
        conn = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def cursor(self) -> Generator[psycopg.Cursor[dict[str, Any]], None, None]:
        """Get a database cursor."""
        with self.connection() as conn:
            with conn.cursor() as cur:
                yield cur
                conn.commit()

    def init_schema(self) -> None:
        """Initialize database schema."""
        with self.cursor() as cur:
            cur.execute(SCHEMA_SQL)

    def check_connection(self) -> dict[str, Any]:
        """Check database connection and return status."""
        try:
            with self.cursor() as cur:
                cur.execute("SELECT version(), current_database(), current_user")
                row = cur.fetchone()
                if row:
                    return {
                        "status": "ok",
                        "version": row["version"],
                        "database": row["current_database"],
                        "user": row["current_user"],
                    }
                return {"status": "error", "message": "No result from version query"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        stats = {}
        with self.cursor() as cur:
            # Document counts
            cur.execute("""
                SELECT
                    jurisdiction,
                    doc_type,
                    COUNT(*) as count
                FROM documents
                GROUP BY jurisdiction, doc_type
                ORDER BY jurisdiction, doc_type
            """)
            stats["documents_by_jurisdiction"] = cur.fetchall()

            # Total counts
            cur.execute("SELECT COUNT(*) as count FROM documents")
            row = cur.fetchone()
            stats["total_documents"] = row["count"] if row else 0

            cur.execute("SELECT COUNT(*) as count FROM document_texts")
            row = cur.fetchone()
            stats["total_texts"] = row["count"] if row else 0

            cur.execute("SELECT COUNT(*) as count FROM runs")
            row = cur.fetchone()
            stats["total_runs"] = row["count"] if row else 0

            # Recent runs
            cur.execute("""
                SELECT job_id, status, started_at, documents_created, documents_failed
                FROM runs
                ORDER BY started_at DESC NULLS LAST
                LIMIT 10
            """)
            stats["recent_runs"] = cur.fetchall()

        return stats


# Global database instance
_database: Database | None = None


def get_database() -> Database:
    """Get the global database instance."""
    global _database
    if _database is None:
        _database = Database()
    return _database
