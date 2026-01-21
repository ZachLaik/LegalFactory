"""EUR-Lex legislation scraper.

This job fetches EU legislation from EUR-Lex using the SPARQL/REST API.

Target: EU Regulations and Directives currently in force.
"""

import uuid
from datetime import date
from typing import Any, Generator

from bs4 import BeautifulSoup

from core.models.document import Document, DocumentType
from jobs.base import BaseJob


class EurlexLegislationJob(BaseJob):
    """Scraper for EUR-Lex legislation."""

    job_id = "eu/eurlex_legislation"
    jurisdiction = "EU"
    source_system = "eurlex"
    doc_type = DocumentType.LEGISLATION

    # EUR-Lex configuration
    BASE_URL = "https://eur-lex.europa.eu"
    SEARCH_URL = f"{BASE_URL}/search.html"

    # Rate limiting (be respectful)
    rate_limit_delay = 2.0

    def fetch_documents(self) -> Generator[Document, None, None]:
        """Fetch EU legislation documents.

        Uses EUR-Lex search to find in-force regulations and directives.
        """
        # For now, implement a basic HTML scraper
        # In production, would use the SPARQL/REST API

        # Search for in-force regulations
        params = {
            "SUBDOM_INIT": "LEGISLATION",
            "DTS_DOM": "EU_LAW",
            "type": "advanced",
            "DTS_SUBDOM": "LEGISLATION",
            "qid": "1",
            "page": "1",
            # Filter: Regulations, in force
        }

        try:
            response = self.fetch_url(self.SEARCH_URL, params=params)
            soup = BeautifulSoup(response.text, "lxml")

            # Parse search results
            results = soup.select(".SearchResult")

            for result in results:
                try:
                    doc = self._parse_search_result(result)
                    if doc:
                        yield doc
                except Exception as e:
                    print(f"Error parsing result: {e}")
                    continue

        except Exception as e:
            print(f"Error fetching EUR-Lex: {e}")
            raise

    def _parse_search_result(self, result: Any) -> Document | None:
        """Parse a search result into a Document."""
        # Extract CELEX number
        celex_elem = result.select_one("a[href*='CELEX']")
        if not celex_elem:
            return None

        href = celex_elem.get("href", "")
        celex = self._extract_celex_from_url(href)
        if not celex:
            return None

        # Extract title
        title_elem = result.select_one(".title")
        title = title_elem.get_text(strip=True) if title_elem else f"Document {celex}"

        # Extract date
        date_elem = result.select_one(".date")
        doc_date = None
        if date_elem:
            try:
                date_text = date_elem.get_text(strip=True)
                # Parse date (format varies)
                doc_date = self._parse_date(date_text)
            except Exception:
                pass

        # Determine document type from CELEX
        doc_type_code = celex[5:6] if len(celex) > 5 else ""
        is_regulation = doc_type_code == "R"
        is_directive = doc_type_code == "L"

        return Document(
            id=str(uuid.uuid4()),
            jurisdiction=self.jurisdiction,
            doc_type=self.doc_type,
            source_system=self.source_system,
            canonical_id=celex,
            secondary_ids={
                "eli": f"http://data.europa.eu/eli/{self._celex_to_eli(celex)}",
            },
            title=title,
            language="en",
            date_document=doc_date,
            in_force=True,  # We're searching for in-force docs
            subject_matters=[],
            keywords=[
                "regulation" if is_regulation else "directive" if is_directive else "other"
            ],
            source_url=f"{self.BASE_URL}/legal-content/EN/TXT/?uri=CELEX:{celex}",
            canonical_url=f"{self.BASE_URL}/legal-content/EN/ALL/?uri=CELEX:{celex}",
            raw_metadata={
                "celex": celex,
                "source": "eurlex_search",
            },
        )

    def _extract_celex_from_url(self, url: str) -> str | None:
        """Extract CELEX number from EUR-Lex URL."""
        import re

        match = re.search(r"CELEX[=:]([0-9A-Z]+)", url)
        if match:
            return match.group(1)
        return None

    def _celex_to_eli(self, celex: str) -> str:
        """Convert CELEX to ELI path component."""
        # Simplified conversion
        # Full implementation would parse CELEX structure
        if len(celex) >= 10:
            year = celex[1:5]
            doc_type = celex[5:6]
            number = celex[6:]

            type_map = {
                "R": "reg",
                "L": "dir",
                "D": "dec",
            }
            eli_type = type_map.get(doc_type, "act")
            return f"{eli_type}/{year}/{number}/oj"

        return celex

    def _parse_date(self, date_text: str) -> date | None:
        """Parse date from various formats."""
        import re
        from datetime import datetime

        # Try common formats
        formats = [
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%B %d, %Y",
        ]

        # Extract date-like pattern
        match = re.search(r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|\d{4}-\d{2}-\d{2})", date_text)
        if match:
            date_text = match.group(1)

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt).date()
            except ValueError:
                continue

        return None


# Entry point for running the job directly
if __name__ == "__main__":
    job = EurlexLegislationJob(limit=5, dry_run=True)
    run = job.execute()
    print(f"\nRun completed: {run.status}")
    print(f"Documents fetched: {run.documents_fetched}")
    print(f"Documents created: {run.documents_created}")
