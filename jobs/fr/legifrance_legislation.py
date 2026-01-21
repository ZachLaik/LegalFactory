"""Légifrance legislation job.

This job fetches French legislation from the Légifrance API (PISTE).
Requires PISTE OAuth credentials.
"""

import contextlib
import os
import uuid
from collections.abc import Generator
from datetime import date

from core.models.document import Document, DocumentType
from core.secrets import SecretRequirement
from jobs.base import BaseJob


class LegifranceLegislationJob(BaseJob):
    """Fetch French legislation from Légifrance API."""

    job_id = "fr/legifrance_legislation"
    jurisdiction = "FR"
    source_system = "legifrance"
    doc_type = DocumentType.LEGISLATION

    # PISTE API credentials are REQUIRED
    required_secrets = [
        SecretRequirement(
            env_var="PISTE_CLIENT_ID",
            description="PISTE OAuth Client ID",
            how_to_obtain="""
1. Create an account at https://piste.gouv.fr
2. Create a new application
3. Request access to the Légifrance API
4. Copy the Client ID from your application settings
""",
            required_for="accessing Légifrance API",
        ),
        SecretRequirement(
            env_var="PISTE_CLIENT_SECRET",
            description="PISTE OAuth Client Secret",
            how_to_obtain="""
Same as PISTE_CLIENT_ID - copy the Client Secret from your application settings.
""",
            required_for="accessing Légifrance API",
        ),
    ]

    # Légifrance API config
    TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
    BASE_URL = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
    rate_limit_delay = 1.0

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._access_token: str | None = None

    def _get_access_token(self) -> str:
        """Get OAuth access token from PISTE."""
        if self._access_token:
            return self._access_token

        client_id = os.environ.get("PISTE_CLIENT_ID")
        client_secret = os.environ.get("PISTE_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise ValueError("PISTE credentials not set")

        response = self.client.post(
            self.TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "openid",
            },
        )
        response.raise_for_status()
        self._access_token = response.json()["access_token"]
        return self._access_token

    def fetch_documents(self) -> Generator[Document, None, None]:
        """Fetch French legislation documents from Légifrance API."""
        token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Search for codes (major French legal codes)
        search_url = f"{self.BASE_URL}/search"
        payload = {
            "fond": "CODE_DATE",
            "recherche": {
                "pageNumber": 1,
                "pageSize": self.limit or 50,
                "sort": "PERTINENCE",
            },
        }

        try:
            response = self.client.post(search_url, headers=headers, json=payload)
            response.raise_for_status()
            results = response.json()

            for result in results.get("results", []):
                doc = self._parse_result(result)
                if doc:
                    yield doc

        except Exception as e:
            print(f"Error fetching from Légifrance: {e}")
            raise

    def _parse_result(self, result: dict) -> Document | None:
        """Parse a search result into a Document."""
        doc_id = result.get("id", "")
        if not doc_id:
            return None

        # Parse date
        date_text = result.get("dateTexte", "")
        doc_date = None
        if date_text:
            with contextlib.suppress(ValueError):
                doc_date = date.fromisoformat(date_text[:10])

        return Document(
            id=str(uuid.uuid4()),
            jurisdiction=self.jurisdiction,
            doc_type=self.doc_type,
            source_system=self.source_system,
            canonical_id=doc_id,
            secondary_ids={},
            title=result.get("titre", f"Document {doc_id}"),
            language="fr",
            date_document=doc_date,
            in_force=result.get("etat", "") == "VIGUEUR",
            subject_matters=[],
            keywords=[],
            source_url=f"https://www.legifrance.gouv.fr/codes/texte_lc/{doc_id}",
            canonical_url=f"https://www.legifrance.gouv.fr/codes/texte_lc/{doc_id}",
            raw_metadata={
                "id": doc_id,
                "source": "legifrance_api",
                "etat": result.get("etat", ""),
            },
        )


# Entry point for running the job directly
if __name__ == "__main__":
    job = LegifranceLegislationJob(limit=5, dry_run=True)
    run = job.execute()
    print(f"\nRun completed: {run.status}")
    print(f"Documents fetched: {run.documents_fetched}")
    print(f"Documents created: {run.documents_created}")
