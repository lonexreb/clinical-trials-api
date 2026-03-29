# Clinical Trials ETL Pipeline & API

## What This Is
REST API that pulls clinical trial data from ClinicalTrials.gov, normalizes it into a unified schema, stores it in PostgreSQL, and serves it through a queryable API + bulk export. OpenAlex will consume the API directly.

**Development**: ~2hr 50min active coding over 3 days. Most elapsed time was waiting (Render deploys, DB provisioning, ingestion runs, storage lockouts). Approach: research CT.gov API design first, get an end-to-end prototype working fast, then iteratively improve.

## Tech Stack
- **Framework**: FastAPI (async, ASGI)
- **Database**: PostgreSQL + SQLAlchemy async + Alembic migrations
- **Data source**: ClinicalTrials.gov API v2 (`https://clinicaltrials.gov/api/v2/studies`)
- **Python**: 3.11+
- **Testing**: pytest + pytest-asyncio + httpx (AsyncClient)
- **Middleware**: GZipMiddleware (automatic compression for responses > 1KB)
- **Deploy target**: Render (Docker + cron) — live at `https://clinical-trials-etl-api-qx33.onrender.com`
- **DB plan**: basic-1gb (10GB disk)

## Key Directories
```
app/
├── api/v1/          # Route handlers: trials, export, health, ingest
├── core/            # Config (Settings via pydantic-settings), dependencies
├── models/          # SQLAlchemy ORM models (trials table)
├── schemas/         # Pydantic request/response schemas
├── services/        # Business logic: ingestion, parsing, transformation
│   ├── ingestion.py # Fetch from ClinicalTrials.gov API v2, incremental sync
│   ├── parser.py    # Map CT.gov nested JSON → unified schema (JSONB arrays)
│   └── loader.py    # Batch upsert to PostgreSQL (session-per-batch)
├── db/              # Engine, session, Alembic config
│   └── migrations/
└── tests/           # Mirrors app/ structure
scripts/
├── run_ingestion.py      # CLI: full or incremental ingestion (--since, --query)
├── demo_parallel.py      # Parallel initial load via year-range sharding
├── demo_progressive.py   # Progressive ingestion demo
├── monitor_ingestion.py  # Live TUI monitor for background ingestion jobs
└── initial_load.sh       # Convenience script for full dataset load
```

## Commands
```bash
uvicorn app.main:app --reload --port 8000           # dev server
pytest tests/ -v --tb=short                         # all tests
ruff check . && mypy app/                           # lint + types
alembic upgrade head                                # apply migrations
alembic revision --autogenerate -m "msg"            # new migration
docker-compose up -d                                # local Postgres + API
python -m scripts.run_ingestion                     # full ingestion
python -m scripts.run_ingestion --since yesterday   # incremental update
python -m scripts.demo_parallel --workers 6         # parallel initial load (~6 min for 578K)
```

## Core Schema
Single `trials` table with these columns:
- `trial_id` (TEXT, UNIQUE, indexed) — NCT ID from ClinicalTrials.gov
- `title` (TEXT)
- `phase` (TEXT, nullable, indexed)
- `status` (TEXT, indexed)
- `sponsor_name` (TEXT, indexed)
- `interventions` (JSONB, nullable) — full array of intervention dicts from CT.gov
- `primary_outcomes` (JSONB, nullable) — full array of primary outcome dicts
- `secondary_outcomes` (JSONB, nullable) — full array of secondary outcome dicts
- `start_date` (DATE, nullable)
- `completion_date` (DATE, nullable)
- `locations` (JSONB, nullable) — full array of location dicts from CT.gov
- `enrollment_number` (INTEGER, nullable)
- `raw_data` (JSONB) — full original record for extensibility
- `created_at` / `updated_at` (TIMESTAMPTZ)

Indexes: `trial_id`, `sponsor_name`, `status`, `phase`.

Migrations:
- `001_initial_schema.py` — base table with JSONB raw_data + indexes
- `002_jsonb_arrays_and_secondary_outcomes.py` — evolve flat columns to JSONB arrays

## Database Stats (325,733 trials in production)
- **14,291** unique sponsors, **14** statuses, **6** phases
- Top statuses: COMPLETED (36K), UNKNOWN (10K), RECRUITING (7.7K)
- Top sponsors: Assiut University, Cairo University, NCI, AstraZeneca, GSK
- Data completeness: 99.8% have interventions, 99.9% have primary outcomes, 99.8% have locations
- Full 500K dataset loadable via `python -m scripts.demo_parallel --workers 6` (~6 min)

## Test Suite
- **68 tests**, all passing in 0.24s (SQLite in-memory via aiosqlite)
- Coverage: parser (29), API (15), ingestion (8), export (8), loader (6), health (2)
- No external services required — tests use dependency injection for DB session

## Local vs Production
- **Local**: docker-compose up → Postgres 15 + API with hot reload, batch size 500
- **Production (Render)**: 325K trials, basic-1gb plan (10GB disk), batch size 500 (internal connection)
- **Daily cron**: CLI script via render.yaml (`--since yesterday`), not the `/ingest` API endpoint
- **`/ingest` endpoint**: Supports `query`, `max_pages`, `year_start`/`year_end`, `background` — does NOT support `--since`
- **`/ingest/all` endpoint**: Queues all 12 year-range shards as sequential background jobs
- **`/ingest/status` endpoint**: Check job status + current DB count; used by `scripts/monitor_ingestion.py` TUI

## ClinicalTrials.gov API v2 — Critical Details
- Base: `https://clinicaltrials.gov/api/v2/studies`
- No API key. No auth. Generous rate limits.
- JSON default. Max `pageSize=1000` (default 10 — always set explicitly).
- Pagination is token-based via `pageToken`, NOT offset.
- Supports `filter.advanced` for:
  - Incremental sync: `AREA[LastUpdatePostDate]RANGE[MM/DD/YYYY,MAX]`
  - Year-range sharding: `AREA[StudyFirstPostDate]RANGE[01/01/YYYY,12/31/YYYY]`
- Study data nests under `protocolSection`:
  - `identificationModule` → NCTId, briefTitle
  - `statusModule` → overallStatus, startDateStruct, completionDateStruct
  - `sponsorCollaboratorsModule` → leadSponsor.name
  - `armsInterventionsModule` → interventions[] (full array stored as JSONB)
  - `outcomesModule` → primaryOutcomes[], secondaryOutcomes[] (full arrays stored as JSONB)
  - `designModule` → phases[], enrollmentInfo.count
  - `contactsLocationsModule` → locations[] (full array stored as JSONB)
- **Dates are INCONSISTENT**: "2024-01-15", "January 2024", "January 15, 2024". Parse defensively with fallback chain.
- Arrays (interventions, locations, outcomes) may be null or empty. Never assume they exist.

## API Endpoints (Our API)
- `GET /health` — no DB, always 200
- `GET /trials/search` — paginated (`?skip=0&limit=50`, max 100), filterable by `sponsor`, `status`, `phase`
- `GET /trials/{trial_id}` — by NCT ID
- `GET /trials/export?format=ndjson|csv` — streaming bulk export, batched DB reads (1000/batch), auto gzip via GZipMiddleware
- `POST /ingest` — trigger ingestion (supports `query`, `max_pages`, `year_start`, `year_end`, `background`)
- `POST /ingest/all` — queue all 12 year-range shards as sequential background jobs
- `GET /ingest/status` — check background ingestion job status + current DB count
- Errors: `{"detail": "…"}`, 422 validation, 404 not found

## Production Deployment (Render)
- **Web service**: `clinical-trials-etl-api` (Docker, starter plan)
- **Database**: `clinical-trials-etl-db` (PostgreSQL, basic-1gb, 10GB disk)
- **Cron job**: `clinical-trials-etl-ingest` — runs daily at 2 AM UTC, `--since yesterday`
- `render.yaml` defines all three resources with auto-wired DATABASE_URL

## OpenAlex Integration
- Publicly reachable at `https://clinical-trials-etl-api-qx33.onrender.com`
- Standard REST + JSON responses
- Open (no auth) during evaluation
- Base URL + example curls documented in README

## Code Style
- Type hints on ALL signatures — no `Any`
- Pydantic for all request/response bodies
- Async by default; thin handlers, logic in `services/`
- `Depends()` for DB sessions and config
- snake_case everywhere

## Hard Rules
- NEVER modify applied migration files
- NEVER hardcode credentials — env vars via `app/core/config.py`
- Date parsing MUST handle multiple CT.gov formats
- Batch inserts: max 500 per batch (use 50 for external remote Postgres)
- `/health` must not touch the database
- Update CLAUDE.md, README.md, and LEARNING.md with each commit

## References
- See @GOALS.md for current phase and task status
- See @LEARNING.md for what worked, what didn't, local/production results, and AI harness usage
- See @DEMO.md for the demo recording script (under 2 min)
- See @take-home.md for the original project brief
- CT.gov API: https://clinicaltrials.gov/data-api/api
- CT.gov data structure: https://clinicaltrials.gov/data-api/about-api/study-data-structure
- OpenAlex API: https://docs.openalex.org/how-to-use-the-api/api-overview
