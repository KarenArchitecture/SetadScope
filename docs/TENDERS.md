# Tender ingestion

## Current scope

This slice adds the tender data model, JSONB persistence, API, export, and dashboard tab. It deliberately separates tender records from the existing keyword-filtered auction pipeline.

The uploaded Setad response has a top-level gridModel array. Each row has a source id, tender number, title/type, an organization object, province/city, description, and Jalali date strings.

## Storage

- tenders.source_tender_id is the source row ID and is unique per source.
- tender_number is stored as text to preserve the source identifier exactly.
- The full source row is stored in raw_payload JSONB.
- Original Jalali date strings are kept unchanged in the source-text columns and raw_payload JSONB. Parallel timezone-aware Gregorian DateTime columns are populated for sorting, date-range filtering, and remaining-time calculations.

## Importing response pages

Save response JSON files in data/raw/tenders/ using the tender_page_*.json naming pattern. Every file must contain a top-level gridModel array.

Run the importer:

\`\`\`powershell
docker compose run --rm api python -m app.tender_jobs
\`\`\`

By default, if a tender_run_*.json manifest exists, only its page files are imported. Without a manifest, all matching tender page files are imported. Use --all to explicitly import all snapshots.

The import is idempotent: the same source tender ID updates its existing row rather than creating a duplicate.

## API

- GET /api/tenders: server-side search, province/city/state/type filters, announcement/deadline date ranges, sorting, and pagination.
- GET /api/tenders/{id}: tender detail including the raw JSONB payload.
- GET /api/tenders/export.xlsx: Excel export.

## Automated collector

The request URL and method supplied from browser DevTools confirmed the public listing request:

- Method: GET
- Endpoint: https://etend.setadiran.ir/etend/callMainPageCartable-anonymous.action
- Query: struts.token.name=csrf_token, csrf_token, _search=false, nd, rows, page, sidx, sord, and cache-buster _.

The collector does not embed the CSRF token from a browser capture. It creates a new requests session, opens the tender landing page, extracts the current token from the HTML or session cookies, and sends the listing request with the same session. The landing URL can be overridden with SETAD_TENDER_LANDING_URL if the portal changes its entry route.

The first successful page determines the server-reported page count and record count. Unless an explicit end page is supplied, the collector fetches every page reported by the server. Each response is preserved unchanged in data/raw/tenders/; the import is then upserted by source tender ID.

Run both steps manually:

```powershell
docker compose run --rm api python -m setad_scope.collectors.fetch_tenders
docker compose run --rm api python -m app.tender_jobs
```

Or use .\setad.ps1 collect-tenders.

## Progress reporting

The collector emits structured progress after each page. FastAPI streams these progress events from the collector process into an independent in-memory status object for auctions and tenders. The dashboard polls the matching status endpoint while that job is active.

Progress is split into two phases: fetching (0–85%) and PostgreSQL import (85–100%). The UI displays page counts, fetched record counts, stored counts, errors, and the final totals.


## Data table behavior

The tender workspace displays dates using the Persian calendar while sorting and filtering against the normalized timestamp columns. Supported date filters are public announcement, proposal deadline, and document deadline. The table also supports sorting by announcement, document deadline, proposal deadline / remaining time, organization, location, type, and status.

Province and city are separate fields. The city filter is scoped to the selected province. The export endpoint accepts the same filter and sort parameters as the table.

The tender response does not currently provide a validated monetary amount in the mapped fields, so price sorting and price filters are intentionally limited to auctions. Archive summary metadata reports distinct province, city, organization, and tender-type counts across the complete tender archive, alongside the current filtered result count.


The inspected tender response contains monetary-related keys such as offeredPrice1, offeredPrice2, offeredPrice3, tenderDocumentsPrice, and tndaFinancialEstimatesPrice, but the sample values are null. The table therefore does not expose a price sort or price range filter for tenders until real values and their unit/meaning are verified.
