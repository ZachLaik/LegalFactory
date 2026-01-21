# Legal Data Factory

Continuously bootstraps and updates EU legislation + case law, writing to a Neon Postgres database with comprehensive jurisdiction coverage tracking.

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env.local
# Edit .env.local with your Neon database URL

# Check configuration
ldf doctor

# Initialize database schema
ldf init-db

# View coverage status
ldf status
```

## Architecture

```
LegalDataFactory/
├── configs/
│   ├── jurisdictions/     # YAML configs for each EU country + EU
│   │   ├── EU.yaml        # European Union (supranational)
│   │   ├── DE.yaml        # Germany (federal)
│   │   ├── FR.yaml        # France (unitary)
│   │   └── ...            # All 27 EU Member States
│   └── schemas/           # JSON Schema for validation
├── jobs/
│   ├── base.py            # Base scraper class
│   ├── eu/                # EU-level scrapers
│   ├── de/                # German scrapers
│   └── ...
├── core/
│   ├── models/            # Pydantic data models
│   └── storage/           # Database layer (Neon Postgres)
├── cli/
│   └── main.py            # CLI entrypoint (ldf command)
├── tests/
│   ├── unit/              # Unit tests
│   ├── fixtures/          # Golden fixtures for parser tests
│   └── integration/       # Integration tests (gated)
└── .github/
    ├── workflows/         # CI/CD pipelines
    └── ISSUE_TEMPLATE/    # Issue templates for task tracking
```

## CLI Commands

```bash
ldf doctor          # Check secrets + database connection
ldf status          # Show coverage status by jurisdiction
ldf stats           # Show database statistics
ldf init-db         # Initialize database schema
ldf run <job>       # Run a specific job (e.g., eu/eurlex_legislation)
ldf controller      # Start continuous crawling loop
ldf create-issues   # Create GitHub issues from configs
```

## Jurisdiction Coverage

Each jurisdiction has a YAML configuration in `configs/jurisdictions/`:

- **80/20 Plan**: What yields most value fast (supreme courts, consolidated law)
- **Backlog**: Everything needed for completeness later
- **Sources**: Official gazette, consolidated law portals, court databases
- **Identifiers**: ECLI, CELEX, national ID schemes

### Coverage by System Type

| Type | Countries | Notes |
|------|-----------|-------|
| Supranational | EU | EUR-Lex, CJEU via CURIA |
| Federal | DE, AT, BE | Multiple levels of legislation |
| Devolved | ES, IT, PT | Autonomous regions with legislative powers |
| Unitary | FR, NL, PL, ... | Single national system |

## Database Schema

Single logical schema with columns for jurisdiction and doc_type:

- `documents`: Normalized metadata for all legal documents
- `document_texts`: Content versions and extracted text
- `runs`: Job execution tracking
- `watermarks`: Crawl progress for incremental updates

## GitHub Integration

Task tracking via GitHub Issues:

- Labels: `country:DE`, `type:scraper`, `priority:P0`, `blocked:credentials`
- Issue templates: Inventory, Implement Job, Data Bug, Blocked
- Project board: EU Coverage (by country, by type, by status)

## Development

```bash
# Run tests
pytest tests/unit -v

# Lint
ruff check .

# Type check
mypy cli core jobs

# Run integration tests (requires approval)
# Via GitHub Actions workflow_dispatch
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | Neon Postgres connection string | Yes |
| `GITHUB_TOKEN` | GitHub PAT for issue management | For issues |
| `EURLEX_API_KEY` | EUR-Lex API key | Optional |

## License

MIT
