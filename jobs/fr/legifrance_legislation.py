"""Légifrance legislation job.

This job fetches French legislation from the Légifrance API (PISTE).
Requires PISTE OAuth credentials.
"""

from collections.abc import Generator

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
    BASE_URL = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
    rate_limit_delay = 1.0

    def fetch_documents(self) -> Generator[Document, None, None]:
        """Fetch French legislation documents.

        This is a placeholder - real implementation would use PISTE OAuth
        to authenticate and fetch from the Légifrance API.
        """
        # Would authenticate with PISTE and fetch documents
        # For now, this just shows the structure
        raise NotImplementedError(
            "Légifrance API integration requires PISTE credentials. "
            "See https://piste.gouv.fr for registration."
        )
