# SetadScope — PostgreSQL foundation (Phase 2)

Backend remains FastAPI. PostgreSQL runs in Docker Compose, with SQLAlchemy and Alembic migrations.

## Quick start

1. Install and start Docker Desktop (Compose v2).
2. Copy `.env.example` to `.env`; set the same secure password in `POSTGRES_PASSWORD` and `DATABASE_URL`.
3. From the repository root: `docker compose up -d --build`.
4. Open `http://localhost:8000/api/health` and `http://localhost:8000/docs`.
5. Use the existing collector to fetch data into `data/raw/`, then import: `docker compose exec api python -m app.jobs`.
6. For frontend: `cd frontend`, `npm install`, `npm run dev`.

## API

- `GET /api/auctions?status=active` — valid matching opportunities (default)
- `GET /api/auctions?status=archive` — previously stored, now expired
- `GET /api/auctions?sort_by=base_total_price&sort_dir=desc`
- `GET /api/auctions/export.xlsx?status=active`
- `GET /api/auctions/{id}`

## Important limitations

- Only the existing main-estate source is collected; other tenders/purchases need separate collectors.
- Deadline parser supports ISO, epoch milliseconds, and /Date(ms)/. Unknown date formats are rejected and must be checked against real Setad samples.
- The current source does not confirm document receipt deadlines, cubic-meter volumes, currency, or detail URLs. These fields remain empty, not guessed.
- An advertisement must contain at least one configured keyword and must have an open proposal deadline to be stored. Rows already stored are retained in the archive when time expires.
- Source snapshots live under `data/` and credentials under `.env`; neither belongs in Git.
- Automatic daily collection and the enhanced frontend are not yet enabled in this foundation stage. Run import after collection.
- Never use `docker compose down -v` unless you intend to delete the PostgreSQL volume.

Debug with `docker compose logs -f api` and `docker compose ps`.
