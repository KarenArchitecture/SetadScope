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
```

- `stop` stops containers but preserves the named PostgreSQL volume.
- `restart` restarts existing containers without rebuilding images.
- `rebuild` rebuilds images and recreates services after code or dependency changes.
- `collect` fetches pages 1–37 (the currently reported full listing) into `data/raw`, then imports only keyword-matched records from the latest run into PostgreSQL. Deadline filtering is intentionally disabled for this delivery; Jalali dates remain in the raw source payload until date parsing is implemented.
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

The current collector covers the public main-estate listing source only. Keyword matching is enabled; deadline filtering is temporarily disabled so matched listings are not lost while Jalali date parsing is pending. Document deadlines, currency semantics, and cubic-meter volume still require validation against real Setad records. Unknown values are kept empty rather than guessed. Daily scheduling and AI-assisted analysis are not enabled yet.


## Tender records

Tender listings are stored separately from auction listings. The complete source response row is retained in PostgreSQL JSONB; normalized fields are used for search, sorting, pagination, and export.

The importer expects response pages under data/raw/tenders/ named tender_page_*.json. Each page must contain the Setad response's top-level gridModel array.

After saving response pages in that folder, run:

\`\`\`powershell
docker compose run --rm api python -m app.tender_jobs
\`\`\`

To re-import every saved snapshot:

\`\`\`powershell
docker compose run --rm api python -m app.tender_jobs --all
\`\`\`

Tender API endpoints:

- GET /api/tenders
- GET /api/tenders/{id} (includes the retained raw_payload)
- GET /api/tenders/export.xlsx

The source dates currently arrive as Jalali strings (for example, 1405/09/17 14:30:00). They are stored unchanged as text; no Gregorian conversion or date-based active/archive filtering is applied. The automated tender-page fetcher is intentionally not wired yet because the uploaded response body does not identify the exact AJAX endpoint or request method. Do not guess that endpoint; capture it from the browser Network panel before implementing the collector.
