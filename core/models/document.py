"""Document models for legal data."""

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Type of legal document."""

    LEGISLATION = "legislation"
    CASE_LAW = "case_law"
    TREATY = "treaty"
    PREPARATORY = "preparatory"
    OTHER = "other"


class Document(BaseModel):
    """Core document model for legal data.

    This is the normalized metadata representation stored in the database.
    """

    # Identity
    id: str = Field(..., description="Unique document ID (UUID)")
    jurisdiction: str = Field(..., description="ISO code (e.g., EU, DE, FR)")
    doc_type: DocumentType
    source_system: str = Field(..., description="Source system identifier (e.g., eurlex)")

    # Primary identifiers
    canonical_id: str = Field(..., description="Canonical ID (CELEX, ECLI, national ID)")
    secondary_ids: dict[str, str] = Field(
        default_factory=dict,
        description="Secondary identifiers (e.g., ELI, NOR, case number)",
    )

    # Metadata
    title: str
    title_native: str | None = None
    language: str = Field(..., description="Primary language (ISO 639-1)")
    languages_available: list[str] = Field(default_factory=list)

    # Temporal
    date_document: date | None = Field(None, description="Document date")
    date_publication: date | None = Field(None, description="Publication date")
    date_entry_into_force: date | None = Field(None, description="Entry into force date")
    date_repeal: date | None = Field(None, description="Repeal/abolition date")
    in_force: bool | None = Field(None, description="Currently in force")

    # Classification
    subject_matters: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    # Legal hierarchy (for legislation)
    legal_basis: list[str] = Field(default_factory=list)
    amends: list[str] = Field(default_factory=list)
    amended_by: list[str] = Field(default_factory=list)
    repeals: list[str] = Field(default_factory=list)
    repealed_by: list[str] = Field(default_factory=list)

    # Court information (for case law)
    court: str | None = None
    court_chamber: str | None = None
    court_ecli_code: str | None = None
    case_number: str | None = None
    decision_type: str | None = None
    parties: list[str] = Field(default_factory=list)

    # Source information
    source_url: str
    canonical_url: str | None = None

    # Provenance
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source_last_modified: datetime | None = None

    # Raw metadata from source
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentText(BaseModel):
    """Document text content and versions.

    Separate from Document to allow multiple text versions/formats.
    """

    id: str = Field(..., description="Unique text ID (UUID)")
    document_id: str = Field(..., description="Reference to parent Document")

    # Version info
    version: str | None = Field(None, description="Version identifier")
    version_date: date | None = None
    is_current: bool = True
    is_consolidated: bool = False

    # Content
    content_type: str = Field(..., description="MIME type (text/html, application/pdf)")
    content_text: str | None = Field(None, description="Extracted plain text")
    content_html: str | None = Field(None, description="HTML content")
    content_xml: str | None = Field(None, description="XML content (Akoma Ntoso, etc.)")
    content_hash: str | None = Field(None, description="SHA-256 hash of content")

    # Storage
    blob_url: str | None = Field(None, description="URL to raw blob storage")
    blob_size_bytes: int | None = None

    # Processing
    extraction_method: str | None = Field(None, description="How text was extracted")
    word_count: int | None = None
    char_count: int | None = None

    # Provenance
    created_at: datetime = Field(default_factory=datetime.utcnow)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
