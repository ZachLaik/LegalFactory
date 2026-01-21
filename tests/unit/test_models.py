"""Tests for core models."""

from datetime import date

from core.models.document import Document, DocumentType
from core.models.run import Run, RunStatus, Watermark


class TestDocument:
    """Tests for Document model."""

    def test_create_legislation_document(self) -> None:
        """Test creating a legislation document."""
        doc = Document(
            id="test-123",
            jurisdiction="EU",
            doc_type=DocumentType.LEGISLATION,
            source_system="eurlex",
            canonical_id="32016R0679",
            title="General Data Protection Regulation",
            language="en",
            source_url="https://eur-lex.europa.eu/CELEX:32016R0679",
        )

        assert doc.jurisdiction == "EU"
        assert doc.doc_type == DocumentType.LEGISLATION
        assert doc.canonical_id == "32016R0679"
        assert doc.secondary_ids == {}
        assert doc.in_force is None

    def test_create_case_law_document(self) -> None:
        """Test creating a case law document."""
        doc = Document(
            id="test-456",
            jurisdiction="EU",
            doc_type=DocumentType.CASE_LAW,
            source_system="curia",
            canonical_id="ECLI:EU:C:2014:317",
            title="Google Spain",
            language="en",
            source_url="https://curia.europa.eu/...",
            court="Court of Justice",
            court_ecli_code="EU:C",
            case_number="C-131/12",
            decision_type="Judgment",
            date_document=date(2014, 5, 13),
        )

        assert doc.doc_type == DocumentType.CASE_LAW
        assert doc.court == "Court of Justice"
        assert doc.case_number == "C-131/12"

    def test_document_with_relationships(self) -> None:
        """Test document with legal relationships."""
        doc = Document(
            id="test-789",
            jurisdiction="DE",
            doc_type=DocumentType.LEGISLATION,
            source_system="gesetze_im_internet",
            canonical_id="BJNR001950896",
            title="Bürgerliches Gesetzbuch",
            language="de",
            source_url="https://www.gesetze-im-internet.de/bgb/",
            in_force=True,
            amends=["BJNR000010001"],
            amended_by=["BJNR123450020"],
        )

        assert doc.in_force is True
        assert len(doc.amends) == 1
        assert len(doc.amended_by) == 1


class TestRun:
    """Tests for Run model."""

    def test_create_run(self) -> None:
        """Test creating a run record."""
        run = Run(
            id="run-123",
            job_id="eu/eurlex_legislation",
            jurisdiction="EU",
            source_system="eurlex",
            status=RunStatus.PENDING,
        )

        assert run.status == RunStatus.PENDING
        assert run.documents_fetched == 0

    def test_run_status_transitions(self) -> None:
        """Test run status values."""
        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.COMPLETED.value == "completed"
        assert RunStatus.FAILED.value == "failed"


class TestWatermark:
    """Tests for Watermark model."""

    def test_create_watermark(self) -> None:
        """Test creating a watermark."""
        wm = Watermark(
            job_id="eu/eurlex_legislation",
            jurisdiction="EU",
            source_system="eurlex",
            last_page=10,
            total_documents=1000,
        )

        assert wm.last_page == 10
        assert wm.is_complete is False
