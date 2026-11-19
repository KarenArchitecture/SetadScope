# SetadScope — Phase 2: Dockerized application stack

This phase adds the PostgreSQL-backed API and a single-command local development workflow. The full runtime stack is managed by Docker Compose.

## Services

- `db`: PostgreSQL 17, internal port 5432, persistent named volume.
- `api`: FastAPI on container port 8000, published as host port 18080.
- `frontend`: React + Vite on container/host port 5173. Its Vite proxy reaches the API using the Compose DNS name `api:8000`.
- `collector`: one-shot Python job container that writes raw JSON pages to the shared `data/raw` folder.
- `ingest`: one-shot Python job container that imports the latest collector run into PostgreSQL.

Only the frontend and API are published to localhost. The database stays private to the Docker network.

## Quick start

1. Install and start Docker Desktop.
2. Copy `.env.example` to `.env`.
3. Set the same strong password in `POSTGRES_PASSWORD` and in `DATABASE_URL`. URL-reserved characters must be percent-encoded; a password using letters, numbers, hyphens, and underscores avoids this issue.
4. From the repository root run `.\setad.ps1 start`.
5. Open the dashboard at http://localhost:5173.

API health and Swagger:

- http://localhost:18080/api/health
- http://localhost:18080/docs

## Project manager

- `.\setad.ps1 start`: build and start the full stack.
- `.\setad.ps1 stop`: stop all long-running containers without deleting data.
- `.\setad.ps1 restart`: restart existing containers.
- `.\setad.ps1 rebuild`: rebuild images and recreate services.
- `.\setad.ps1 status`: show service state.
- `.\setad.ps1 logs`: follow logs.
- `.\setad.ps1 collect`: fetch pages 1–3 and import the latest run.
- `.\setad.ps1 collect -StartPage 1 -EndPage 5`: choose a page range.

The collector and importer are invoked as disposable containers from the same backend image. They do not need separate terminals or host Python environments.

## Persistence and safety

- Database data persists in the `postgres_data` named volume.
- Raw snapshots persist under the host `data/raw` folder.
- Local credentials stay in `.env`, which is ignored by Git.
- Never use `docker compose down -v` unless deleting all database data is intentional.
- The `ingest` job imports only files listed in the latest collector run summary by default. Use `docker compose run --rm ingest --all` to re-import all stored page snapshots.

## Not implemented in this phase

- Automatic daily scheduling.
- Additional Setad data-source collectors.
- Extraction/validation of document-receipt deadlines, currency, and cubic-meter volume where the source does not yet provide verified mappings.
- AI analysis and company-specific opportunity scoring.
