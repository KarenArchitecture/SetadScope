# Tender ingestion

## Current scope

This slice adds the tender data model, JSONB persistence, API, export, and dashboard tab. It deliberately separates tender records from the existing keyword-filtered auction pipeline.

The uploaded Setad response has a top-level gridModel array. Each row has a source id, tender number, title/type, an organization object, province/city, description, and Jalali date strings.

## Storage

- tenders.source_tender_id is the source row ID and is unique per source.
- tender_number is stored as text to preserve the source identifier exactly.
- The full source row is stored in raw_payload JSONB.
- Jalali date strings are kept unchanged until a calendar conversion is implemented and tested.

## Importing response pages

Save response JSON files in data/raw/tenders/ using the tender_page_*.json naming pattern. Every file must contain a top-level gridModel array.

Run the importer:

\`\`\`powershell
docker compose run --rm api python -m app.tender_jobs
\`\`\`

By default, if a tender_run_*.json manifest exists, only its page files are imported. Without a manifest, all matching tender page files are imported. Use --all to explicitly import all snapshots.

The import is idempotent: the same source tender ID updates its existing row rather than creating a duplicate.

## API

- GET /api/tenders: paginated and searchable tender rows.
- GET /api/tenders/{id}: tender detail including the raw JSONB payload.
- GET /api/tenders/export.xlsx: Excel export.

## Collector follow-up

The uploaded JSON body does not contain the URL or HTTP method used to retrieve it. The public page URL alone is not enough to reconstruct the request safely. Before adding a scheduled collector, capture the successful XHR/fetch request in browser DevTools (Request URL, method, query/form payload, and required public headers). The existing auction collector must remain unchanged.
