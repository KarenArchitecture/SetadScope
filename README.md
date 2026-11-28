# SetadScope

SetadScope collects public auction and tender listings from Setad, stores normalized records in PostgreSQL, and presents searchable data through a React dashboard.

## Runtime architecture

All runtime components are managed by Docker Compose:

| Service | Technology | Container port | Host access |
| --- | --- | ---: | --- |
| `frontend` | React + Vite | 5173 | `http://localhost:5173` |
| `api` | FastAPI | 8000 | `http://localhost:18080` |
| `db` | PostgreSQL 17 | 5432 | Internal Docker network only |
| `collector` | Python one-shot job | — | Started by the project script |
| `ingest` | Python one-shot job | — | Started by the project script |

The frontend's Vite proxy calls `http://api:8000` over the private Compose network. The API connects to PostgreSQL at `db:5432`. Only the frontend and API are published to the host, bound to localhost. PostgreSQL is not exposed on a host port.

The collector and importer are short-lived job containers based on the backend image. They are not started by the normal `start` command.

## First-time setup (Windows / PowerShell)

1. Install and start Docker Desktop with the Linux container engine.
2. Clone the repository and check out `feature/postgres-keyword-pipeline` (or the branch containing this setup).
3. Copy `.env.example` to `.env`.
4. Set a strong password in both `POSTGRES_PASSWORD` and the password portion of `DATABASE_URL`. For this simple URL format, use letters, numbers, hyphens, and underscores; URL-reserved characters such as `@` must be percent-encoded.
5. Stop any locally running Vite process that is already using port 5173.
6. From the repository root, run:

```powershell
.\setad.ps1 start
```

Open:

- Dashboard: http://localhost:5173
- API health: http://localhost:18080/api/health
- API documentation: http://localhost:18080/docs

## Daily commands

Run these from the repository root:

```powershell
.\setad.ps1 start
.\setad.ps1 stop
.\setad.ps1 restart
.\setad.ps1 rebuild
.\setad.ps1 status
.\setad.ps1 logs
.\setad.ps1 collect
.\setad.ps1 collect -StartPage 1 -EndPage 5
.\setad.ps1 collect-tenders
```

- `stop` stops containers but preserves the named PostgreSQL volume.
- `restart` restarts existing containers without rebuilding images.
- `rebuild` rebuilds images and recreates services after code or dependency changes.
- `collect` fetches auction pages 1–37 into `data/raw`, then imports only keyword-matched records from the latest run into PostgreSQL.
- `collect-tenders` fetches tender pages using the total page count reported by the Setad response, then imports the latest run into the separate `tenders` table. Deadline filtering is intentionally disabled for this delivery; Jalali dates remain in the raw source payload until date parsing is implemented.
- To re-import every saved raw page snapshot manually: `docker compose run --rm ingest --all`.

If PowerShell blocks script execution, run the current command in a PowerShell session with an appropriate execution policy, for example:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Data and credentials

- `.env` contains local credentials and must never be committed.
- Raw collector snapshots are stored under `data/raw` on the host and mounted into the job/API containers.
- PostgreSQL data is stored in the named Docker volume `postgres_data`.
- Do not run `docker compose down -v` unless you intentionally want to delete the database volume and all persisted records.
- Changing `POSTGRES_PASSWORD` in `.env` does not rotate the password inside an already-initialized PostgreSQL volume. Use SQL `ALTER ROLE` to rotate an existing database password.

## Current data limitations

The current collectors cover the public main-estate auction listing and the separate tender listing. Auction keyword matching remains enabled, and date-based filtering is applied in the dashboard rather than during ingestion so matching records are not lost. Jalali dates are normalized into timezone-aware Gregorian timestamps for querying while the original source values remain in JSONB / original text fields. Document deadlines, currency semantics, and cubic-meter volume still require validation against real Setad records. Unknown values are kept empty rather than guessed. Daily scheduling and AI-assisted analysis are not enabled yet.


## Tender records

Tender listings are stored separately from auction listings. The complete source response row is retained in PostgreSQL JSONB; normalized fields are used for search, sorting, pagination, and export.

The importer expects response pages under data/raw/tenders/ named tender_page_*.json. Each page must contain the Setad response's top-level gridModel array.

After saving response pages in that folder, run:

```powershell
docker compose run --rm api python -m app.tender_jobs
```

To re-import every saved snapshot:

```powershell
docker compose run --rm api python -m app.tender_jobs --all
```

Tender API endpoints:

- GET /api/tenders
- GET /api/tenders/{id} (includes the retained raw_payload)
- GET /api/tenders/export.xlsx

The source dates arrive as Jalali strings (for example, 1405/09/17 14:30:00). The original strings are preserved, and parallel timezone-aware Gregorian columns are populated for reliable date sorting and filtering. The automated tender-page collector is implemented using the confirmed GET endpoint. It creates a fresh HTTP session and obtains the current CSRF token from the landing page; the token captured in DevTools is never hard-coded.


## Separate auction and tender workspaces

The dashboard has two independent routes:

- http://localhost:5173/auctions — auction records, auction collector, auction progress.
- http://localhost:5173/tenders — tender records, tender collector, tender progress.

Each page has its own search state, table, export, collection status, and collection action. The two collection jobs can run independently.

The tender collector calls the confirmed public listing endpoint:
`https://etend.setadiran.ir/etend/callMainPageCartable-anonymous.action`

It obtains a fresh CSRF token from the tender landing page within the same HTTP session. The token is not stored in source code or raw snapshots. The collector reads the total page count and record count from the first response, then follows the server-reported pagination.

The dashboard polls the matching collection status endpoint once per second while a job is running. Progress covers both fetching (0–85%) and database import (85–100%), including completed pages, fetched rows, and stored rows.


## Data table, filters, and date handling

Both /auctions and /tenders use server-side sorting, filtering, and pagination.

- Sortable columns include announcement date, proposal deadline / remaining time, price (auctions only), organization, location, status, and tender type where available.
- Province and city are separate filters. The city list is scoped to the selected province.
- Date filters include announcement and proposal-deadline ranges; tenders also support the document-deadline range.
- Auctions support minimum and maximum base-price filters. Tender price filters are intentionally absent because the inspected monetary fields (including offeredPrice1/2/3 and tndaFinancialEstimatesPrice) are null in the sample response.
- The Excel export uses the same active filters and sort order as the table.
- The summary cards distinguish the current result/page from full-archive counts.

Setad timestamps such as fromProposalDate, toProposalDate, fromSiteShowDate, toSiteShowDate, publishStartDate, publishFinishDate, winnerAnnounceDate, openedDate, openingDate, lastModifyDate, createDate, and trustOpenedDate are parsed where present. Tender publicNotificationDate, documentsDeadlineDate, proposalDeadlineDate, and openingDate are parsed as well. Original source values remain available in the raw JSONB payload and the tender source-text columns.


## Auction categories and collection groups (November 2026)

The auction workspace separates the owning collection from the listing category.
Both owning collections have five categories: four EAUC listing families and one
independent Central Board clearance source. There is no shared clearance group.

| Collection group | Category | Source | Request / parameters |
| --- | --- | --- | --- |
| executive_agencies | movable | EAUC | `mainEstate-Load.action` |
| executive_agencies | immovable | EAUC | `mainImmovable-Load.action` |
| executive_agencies | rental | EAUC | `mainRental-Load.action` |
| executive_agencies | minor | EAUC | `mainMinor-Load.action` |
| executive_agencies | clearance | Central Board | `tagCode=341,343&notOrgId=5315` |
| amval_tamliki | movable | EAUC | `mainEstate-Load.action` |
| amval_tamliki | immovable | EAUC | `mainImmovable-Load.action` |
| amval_tamliki | rental | EAUC | `mainRental-Load.action` |
| amval_tamliki | minor | EAUC | `mainMinor-Load.action` |
| amval_tamliki | clearance | Central Board | `tagCode=342&selectedOrganization=5315` |

The two Central Board requests use
`https://gw.setadiran.ir/api/centralboard/cards/` and the same pagination and
response adapter. Their ownership filters are different:
- Executive agencies: `tagCode=341,343` and `notOrgId=5315` (exclude Amval Tamliki).
- Amval Tamliki: `tagCode=342` and `selectedOrganization=5315`.

The Amval collector verifies that every returned card has `orgId=5315` before
saving the page. A missing or mismatched organization ID rejects the response,
preventing records from leaking into the wrong collection. The four EAUC
categories continue to use their own gateway session contexts:
`gateway=setad` for executive agencies and `gateway=amvalTamliki` for Amval.

Each group has its own collector invocation, raw snapshot directory, progress,
ingestion history and database identity. For example, clearance snapshots are
stored under `data/raw/auctions/clearance` for executive agencies and
`data/raw/auctions/amval_tamliki/clearance` for Amval Tamliki.

Alembic revision `0012` reclassifies historical Central Board rows that were
previously placed in the incorrect shared scope. Rows with `orgId=5315`,
`tagCode=342`, or the Amval organization name move to Amval; remaining
historical shared rows move to executive agencies. Raw JSONB payloads and
first-seen timestamps are preserved. Historical ingestion-run entries that
cannot be tied to individual cards are retained under the executive collection
as the legacy default.

The database keeps **all fetched records**, matching or not. `has_keyword_match`
and `matched_keywords` are derived metadata; the dashboard shows only matched
items by default with an explicit toggle to view all. An unmatched auction does
not get discarded, so future AI models can reclassify it without scraping it
again.

Auction row identity is `(collection_group, source, source_party_id)`. This
keeps the same card ID independent when it appears in different owner scopes.
Upsert preserves the original first-seen timestamp and updates the raw JSONB
and normalized columns.

To run a complete category fetch and import in PowerShell:

```powershell
.\setad.ps1 collect-category -Category clearance -Group executive_agencies
.\setad.ps1 collect-category -Category clearance -Group amval_tamliki
.\setad.ps1 collect-category -Category movable -Group amval_tamliki
.\setad.ps1 collect-category -Category rental -Group amval_tamliki
```

Or use the **جمع‌آوری داده** button in the matching collection/category view.
Selecting both collections with the clearance category runs two independent
sources in sequence; it never treats them as one shared feed.

The collector follows server-reported page counts. The first EAUC request uses
page 0, while the response reports page 1; the collector records it as page 1
and then requests pages 2 through the reported total. Central Board uses
zero-based `pageNumber` values and a default page size of five. Partial
Central Board snapshots are retained for diagnosis and imported as failed,
incomplete runs rather than being marked successful.

Auction API examples:
- `GET /api/auctions?category=clearance&collection_group=executive_agencies`
- `GET /api/auctions?category=clearance&collection_group=amval_tamliki`
- `GET /api/auctions?category=clearance&collection_group=all`
- `GET /api/auctions/export.xlsx?category=clearance&collection_group=amval_tamliki`
- `POST /api/collection/auctions/clearance/run?collection_group=amval_tamliki`
- `GET /api/collection/auctions/clearance/status?collection_group=amval_tamliki`
- `GET /api/collection/auctions/history?collection_group=amval_tamliki`

The old `.\setad.ps1 collect` alias remains the movable executive-agency
collection. `.\setad.ps1 collect-tenders` remains unchanged.


The Persian calendar year display uses `useGrouping: false` so ۱۴۰۵ is not
rendered as ۱٬۴۰۵.


Explicit CLI page ranges are still supported for diagnostics:
```powershell
.\setad.ps1 collect -StartPage 1 -EndPage 3
.\setad.ps1 collect-category -Category clearance -StartPage 0 -EndPage 2
```

Real-time connection to the remote Setad services must be validated on a
network that can reach those services; the automated CI suite exercises
representative captured shapes, migrations and PostgreSQL persistence without
making brittle calls to the live public APIs.
