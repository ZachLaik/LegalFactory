# Legal Data Factory

**Scraper development and validation framework** for EU legislation + case law. This repo contains scraper code, jurisdiction configs, and test infrastructure. Scrapers run in **dry-run mode** (no database required) - a separate orchestration tool handles production execution and data storage.

## Purpose

This repo is for:
- ✅ Developing and testing scrapers
- ✅ Validating parser output against golden fixtures
- ✅ CI/CD with auto-retry on transient failures
- ✅ Jurisdiction coverage tracking via configs

This repo does NOT:
- ❌ Save data to a database (dry-run only)
- ❌ Run production crawls (use a separate orchestration tool)

## Quick Start

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# View coverage status
ldf status

# Test a scraper (dry-run, no DB needed)
ldf run eu/eurlex_legislation --limit 5 --dry-run
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
│   └── storage/           # Database layer (for production use)
├── cli/
│   └── main.py            # CLI entrypoint (ldf command)
├── tests/
│   ├── unit/              # Unit tests
│   ├── fixtures/          # Golden fixtures for parser tests
│   └── integration/       # Integration tests
└── .github/
    ├── workflows/         # CI with auto-retry
    └── ISSUE_TEMPLATE/    # Issue templates
```

## CLI Commands

```bash
ldf status              # Show coverage status by jurisdiction
ldf run <job> --dry-run # Test a scraper (no database)
ldf doctor              # Check configuration
```

## Jurisdiction Coverage

28 YAML configs in `configs/jurisdictions/` covering EU + 27 Member States:

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

## CI/CD

GitHub Actions runs on every push:

1. **Lint** - ruff + mypy
2. **Unit Tests** - pytest
3. **Config Validation** - JSON Schema
4. **Scraper Tests** - dry-run with **auto-retry** (3 attempts)

Scrapers are tested against real endpoints but don't save data. Transient failures (network issues, rate limits) trigger automatic retries.

## Development

```bash
# Run tests locally
pytest tests/unit -v

# Lint
ruff check .

# Type check
mypy cli core jobs

# Test a specific scraper
ldf run eu/eurlex_legislation --limit 3 --dry-run
```

## Adding a New Scraper

1. Create `jobs/<iso>/<source>.py` extending `BaseJob`
2. Add source to `configs/jurisdictions/<ISO>.yaml`
3. Add golden fixtures to `tests/fixtures/<source>/`
4. Add to CI matrix in `.github/workflows/ci.yml`

## Production Execution

This repo is **test-only**. For production:
- Use a separate orchestration tool to run scrapers
- That tool should import jobs from this repo
- Configure DATABASE_URL in the orchestration environment
- The orchestration tool handles scheduling, storage, and monitoring

## License

MIT
