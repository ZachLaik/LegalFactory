"""Secrets management for Legal Data Factory.

This module handles:
1. Loading secrets from environment variables
2. Validating required credentials for jobs
3. Signaling when human intervention is needed (e.g., obtaining API keys)
"""

import os
from dataclasses import dataclass
from enum import Enum


class SecretStatus(str, Enum):
    """Status of a required secret."""

    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"


@dataclass
class SecretRequirement:
    """Describes a secret requirement for a job."""

    env_var: str
    description: str
    how_to_obtain: str
    required_for: str = "full functionality"
    validation_hint: str | None = None


@dataclass
class SecretValidationResult:
    """Result of validating secrets for a job."""

    all_available: bool
    missing: list[SecretRequirement]
    available: list[str]

    def to_issue_body(self, job_id: str) -> str:
        """Generate GitHub issue body for missing credentials."""
        lines = [
            f"## Credentials Required for `{job_id}`",
            "",
            "This job requires credentials that are not currently configured.",
            "",
            "### Missing Credentials",
            "",
        ]

        for req in self.missing:
            lines.extend([
                f"#### `{req.env_var}`",
                f"**Description:** {req.description}",
                f"**Required for:** {req.required_for}",
                "",
                "**How to obtain:**",
                f"{req.how_to_obtain}",
                "",
            ])

        lines.extend([
            "### Setup Instructions",
            "",
            "1. Obtain the credentials following the instructions above",
            "2. Add them to your `.env.local` file:",
            "```bash",
        ])

        for req in self.missing:
            lines.append(f"{req.env_var}=your_value_here")

        lines.extend([
            "```",
            "3. For CI/CD, add these as repository secrets in GitHub Settings > Secrets",
            "",
            "### Labels",
            "- `blocked:credentials` - This job is blocked until credentials are provided",
            "- `human-needed` - Requires manual intervention",
        ])

        return "\n".join(lines)


# Registry of known secret requirements by job pattern
SECRET_REGISTRY: dict[str, list[SecretRequirement]] = {
    # EUR-Lex (optional - for higher rate limits)
    "eu/eurlex_*": [
        SecretRequirement(
            env_var="EURLEX_API_KEY",
            description="EUR-Lex SPARQL/REST API key",
            how_to_obtain="""
1. Visit https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html
2. Register for API access
3. You'll receive an API key via email

Note: EUR-Lex is accessible without an API key, but rate limits are lower.
""",
            required_for="higher rate limits (optional)",
        ),
    ],
    # France - PISTE API (required for Légifrance)
    "fr/legifrance_*": [
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
    ],
    # Germany - No API, but may need special headers
    "de/*": [],
    # Netherlands - may require API key
    "nl/overheid_*": [
        SecretRequirement(
            env_var="OVERHEID_API_KEY",
            description="Overheid.nl API key",
            how_to_obtain="""
1. Visit https://developer.overheid.nl
2. Register for an account
3. Create an application to get API credentials
""",
            required_for="accessing official Dutch government data",
            validation_hint="Starts with 'ov_'",
        ),
    ],
}


def get_secret(env_var: str) -> str | None:
    """Get a secret from environment variables.

    Args:
        env_var: Environment variable name

    Returns:
        Secret value or None if not set
    """
    return os.getenv(env_var)


def get_requirements_for_job(job_id: str) -> list[SecretRequirement]:
    """Get secret requirements for a specific job.

    Args:
        job_id: Job identifier (e.g., "eu/eurlex_legislation")

    Returns:
        List of secret requirements
    """
    requirements = []

    for pattern, reqs in SECRET_REGISTRY.items():
        # Simple glob matching
        if _matches_pattern(job_id, pattern):
            requirements.extend(reqs)

    return requirements


def validate_secrets(job_id: str) -> SecretValidationResult:
    """Validate that all required secrets are available for a job.

    Args:
        job_id: Job identifier

    Returns:
        Validation result with missing/available secrets
    """
    requirements = get_requirements_for_job(job_id)

    missing = []
    available = []

    for req in requirements:
        value = get_secret(req.env_var)

        if value:
            # Optional: validate format
            if req.validation_hint and not _validate_format(value, req.validation_hint):
                missing.append(req)
            else:
                available.append(req.env_var)
        else:
            missing.append(req)

    return SecretValidationResult(
        all_available=len(missing) == 0,
        missing=missing,
        available=available,
    )


def _matches_pattern(job_id: str, pattern: str) -> bool:
    """Check if job_id matches a glob pattern.

    Supports * as wildcard.
    """
    import fnmatch
    return fnmatch.fnmatch(job_id, pattern)


def _validate_format(value: str, hint: str) -> bool:
    """Validate secret format based on hint."""
    if hint.startswith("Starts with"):
        prefix = hint.replace("Starts with ", "").strip("'\"")
        return value.startswith(prefix)
    return True


def register_job_secrets(job_id: str, requirements: list[SecretRequirement]) -> None:
    """Register secret requirements for a job.

    This allows jobs to declare their own requirements.

    Args:
        job_id: Job identifier or pattern
        requirements: List of requirements
    """
    SECRET_REGISTRY[job_id] = requirements
