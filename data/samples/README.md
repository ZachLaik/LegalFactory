# Sample Data

Generated on 2026-01-22 using `scripts/fetch_sample_data.py`.

## Contents

This directory contains real document metadata fetched from official legal databases:

- **EU/**: Data from EUR-Lex CELLAR SPARQL endpoint
- **FR/**: Data from Légifrance (PISTE API or curated list)

## Regenerating

```bash
# Fetch all jurisdictions
python scripts/fetch_sample_data.py --all --limit 50

# Fetch specific jurisdiction
python scripts/fetch_sample_data.py --jurisdiction EU --limit 100

# For French data with full API access, set credentials:
export PISTE_CLIENT_ID=your_client_id
export PISTE_CLIENT_SECRET=your_client_secret
python scripts/fetch_sample_data.py --jurisdiction FR --limit 50
```

## Data Sources

- **EUR-Lex**: https://publications.europa.eu/webapi/rdf/sparql
- **Légifrance**: https://api.piste.gouv.fr (requires PISTE credentials)

## Notes

- Data is fetched from official government sources
- Document IDs and metadata are real and verifiable
- Sample data is for testing purposes, not authoritative legal reference
