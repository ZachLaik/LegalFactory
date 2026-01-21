# Secrets Management

This document explains how credentials and API keys are managed in the Legal Data Factory.

## Overview

The Legal Data Factory supports three data acquisition methods, each with different credential requirements:

| Method | Description | Credentials Needed |
|--------|-------------|-------------------|
| **Bulk Downloads** | One-time download of full datasets | Usually none (open data) |
| **APIs** | Incremental updates via REST/SPARQL APIs | Often required (API keys) |
| **Scrapers** | Web scraping as fallback | Rarely needed |

**Philosophy**: We prefer bulk downloads and APIs over scraping. Scraping is only used when no better option exists.

## How It Works

### 1. Jobs Declare Their Requirements

Each job declares what secrets it needs:

```python
from jobs.base import BaseJob
from core.secrets import SecretRequirement

class LegiFranceAPIJob(BaseJob):
    job_id = "fr/legifrance_api"

    # These must be present or the job fails
    required_secrets = [
        SecretRequirement(
            env_var="PISTE_CLIENT_ID",
            description="PISTE OAuth Client ID for Légifrance API",
            how_to_obtain="Register at https://piste.gouv.fr",
            required_for="API authentication",
        ),
    ]

    # These enhance functionality but aren't mandatory
    optional_secrets = [
        SecretRequirement(
            env_var="PISTE_PREMIUM_KEY",
            description="Premium API access for higher rate limits",
            how_to_obtain="Contact DILA for premium access",
            required_for="higher rate limits (optional)",
        ),
    ]
```

### 2. Credentials Are Validated Before Execution

When a job runs:

1. **Dry Run Mode (`--dry-run`)**: Missing credentials produce a warning but don't stop execution
2. **Real Mode**: Missing *required* credentials raise `MissingCredentialsError`

### 3. Missing Credentials Trigger Issues

When credentials are missing, you can:

```bash
# Check what's missing
ldf check-secrets fr/legifrance_api

# Generate .env template
ldf secrets-template fr/legifrance_api

# Create GitHub issue for tracking
ldf check-secrets fr/legifrance_api --create-issue
```

The created issue will have:
- Label: `blocked:credentials`
- Label: `human-needed`
- Instructions on how to obtain the credentials

## Setting Up Credentials

### Local Development

1. Copy the example file:
   ```bash
   cp .env.example .env.local
   ```

2. Fill in your credentials:
   ```bash
   # .env.local
   PISTE_CLIENT_ID=your_client_id
   PISTE_CLIENT_SECRET=your_client_secret
   ```

3. The CLI automatically loads `.env.local`

### CI/CD (GitHub Actions)

1. Go to your repository Settings > Secrets and variables > Actions
2. Add each secret as a repository secret
3. Reference in workflows:
   ```yaml
   env:
     PISTE_CLIENT_ID: ${{ secrets.PISTE_CLIENT_ID }}
   ```

## Credential Registry

Known credentials by jurisdiction:

### EU Level
| Variable | Source | Required | How to Get |
|----------|--------|----------|------------|
| `EURLEX_API_KEY` | EUR-Lex SPARQL | Optional | [Register here](https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html) |

### France
| Variable | Source | Required | How to Get |
|----------|--------|----------|------------|
| `PISTE_CLIENT_ID` | Légifrance API | Yes | [PISTE Portal](https://piste.gouv.fr) |
| `PISTE_CLIENT_SECRET` | Légifrance API | Yes | Same as above |

### Netherlands
| Variable | Source | Required | How to Get |
|----------|--------|----------|------------|
| `OVERHEID_API_KEY` | Overheid.nl | Yes | [Developer Portal](https://developer.overheid.nl) |

### Germany
No API credentials required - uses open bulk data from:
- [Gesetze im Internet](https://www.gesetze-im-internet.de/Teilliste_translations.html)
- [Rechtsprechung im Internet](https://www.rechtsprechung-im-internet.de)

## Data Source Preferences

For each jurisdiction, we prefer data sources in this order:

1. **Official APIs with bulk export**
   - Best for: Complete datasets, structured data, versioning
   - Example: Légifrance API (France), N-Lex gateways

2. **Open Data portals**
   - Best for: One-time downloads, XML/JSON formats
   - Example: data.europa.eu, national open data portals

3. **SPARQL endpoints**
   - Best for: Flexible queries, linked data
   - Example: EUR-Lex SPARQL, Cellar

4. **REST APIs for incremental updates**
   - Best for: Keeping data current after bulk load
   - Example: Changes API, notification feeds

5. **Web scraping (last resort)**
   - Only when no structured data source exists
   - Must respect robots.txt and rate limits

## Adding New Credentials

When adding a new job that requires credentials:

1. **Add to `core/secrets.py` registry**:
   ```python
   SECRET_REGISTRY["de/new_source_*"] = [
       SecretRequirement(
           env_var="NEW_SOURCE_KEY",
           description="API key for new source",
           how_to_obtain="Register at https://...",
           required_for="accessing the API",
       ),
   ]
   ```

2. **Update `.env.example`**:
   ```bash
   # New Source API Key
   # Register at: https://...
   NEW_SOURCE_KEY=
   ```

3. **Document in this file** under the appropriate jurisdiction section

4. **Update CI workflow** if the job will run in CI

## Troubleshooting

### "MissingCredentialsError" in CI

The job requires credentials that aren't set up. Either:
1. Add the secrets to GitHub repository secrets, or
2. Mark the job as `skip_if_no_credentials: true` to skip in CI

### Credentials work locally but not in CI

Check that:
1. Secret names match exactly (case-sensitive)
2. Secrets are added to the correct environment (production vs. staging)
3. Workflow has the `secrets` context configured

### Rate limiting despite having API key

Some APIs have rate limits even with credentials. Check the jurisdiction config for `rate_limits` settings and adjust `rate_limit_delay` in the job.
