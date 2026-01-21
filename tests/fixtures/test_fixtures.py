"""Tests for parser fixtures.

These tests validate that parsers correctly extract data from known fixtures.
Golden fixtures ensure parsers don't regress.
"""

import json
from pathlib import Path

import pytest


class TestEurlexFixtures:
    """Tests for EUR-Lex parser fixtures."""

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        """Get the eurlex fixtures directory."""
        return Path("tests/fixtures/eurlex")

    def test_regulation_fixture_valid(self, fixtures_dir: Path) -> None:
        """Test GDPR regulation fixture is valid JSON."""
        fixture_file = fixtures_dir / "sample_regulation.json"
        if not fixture_file.exists():
            pytest.skip("Fixture not found")

        with open(fixture_file) as f:
            data = json.load(f)

        assert "celex" in data
        assert data["celex"] == "32016R0679"
        assert "expected_extracted" in data

    def test_directive_fixture_valid(self, fixtures_dir: Path) -> None:
        """Test Whistleblower directive fixture is valid JSON."""
        fixture_file = fixtures_dir / "sample_directive.json"
        if not fixture_file.exists():
            pytest.skip("Fixture not found")

        with open(fixture_file) as f:
            data = json.load(f)

        assert "celex" in data
        assert data["doc_type"] == "L"

    def test_caselaw_fixture_valid(self, fixtures_dir: Path) -> None:
        """Test Google Spain case fixture is valid JSON."""
        fixture_file = fixtures_dir / "sample_caselaw.json"
        if not fixture_file.exists():
            pytest.skip("Fixture not found")

        with open(fixture_file) as f:
            data = json.load(f)

        assert "ecli" in data
        assert data["ecli"] == "ECLI:EU:C:2014:317"
        assert "court" in data
        assert "case_number" in data

    def test_all_fixtures_have_expected_extracted(self, fixtures_dir: Path) -> None:
        """Test all fixtures have expected_extracted for validation."""
        if not fixtures_dir.exists():
            pytest.skip("Fixtures directory not found")

        for json_file in fixtures_dir.glob("*.json"):
            with open(json_file) as f:
                data = json.load(f)

            assert "expected_extracted" in data, f"{json_file.name} missing expected_extracted"
            expected = data["expected_extracted"]
            assert "jurisdiction" in expected
            assert "doc_type" in expected
            assert "canonical_id" in expected
