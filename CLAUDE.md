# Clinical Trials ETL Pipeline & API

## What This Is
REST API that pulls clinical trial data from ClinicalTrials.gov, normalizes it into a unified schema, stores it in PostgreSQL, and serves it through a queryable API + bulk export. OpenAlex will consume the API directly.

## Tech Stack
- **Framework**: FastAPI (async, ASGI)
- **Database**: PostgreSQL + SQLAlchemy async + Alembic migrations
- **Data source**: ClinicalTrials.gov API v2 (`https://clinicaltrials.gov/api/v2/studies`)
- **Python**: 3.11+
- **Testing**: pytest + pytest-asyncio + httpx (AsyncClient)
- **Deploy target**: Render or Fly.io (Docker)

## Key Directories
```
app/
├── api/v1/          # Route handlers: trials, export, health
├── core/            # Config (Settings via pydantic-settings), dependencies
├── models/          # SQLAlchemy ORM models (trials table)
├── schemas/         # Pydantic request/response schemas
├── services/        # Business logic: ingestion, parsing, transformation
│   ├── ingestion.py # Fetch from ClinicalTrials.gov API v2
│   ├── parser.py    # Map CT.gov nested JSON → unified schema
│   └── loader.py    # Batch insert to PostgreSQL
├── db/              # Engine, session, Alembic config
│   └── migrations/
└── tests/           # Mirrors app/ structure
```

## Commands
```bash
uvicorn app.main:app --reload --port 8000    # dev server
pytest tests/ -v --tb=short                  # all tests
ruff check . && mypy app/                    # lint + types
alembic upgrade head                         # apply migrations
alembic revision --autogenerate -m "msg"     # new migration
docker-compose up -d                         # local Postgres + API
python -m app.services.ingestion             # run ingestion manually
```

## Core Schema
Single `trials` table with these columns:
- `trial_id` (TEXT, UNIQUE, indexed) — NCT ID from ClinicalTrials.gov
- `title` (TEXT)
- `phase` (TEXT, nullable)
- `status` (TEXT, indexed)
- `sponsor_name` (TEXT, indexed)
- `intervention_type` (TEXT, nullable)
- `intervention_name` (TEXT, nullable)
- `primary_outcome_description` (TEXT, nullable)
- `primary_outcome_measure` (TEXT, nullable)
- `start_date` (DATE, nullable)
- `completion_date` (DATE, nullable)
- `location_country` (TEXT, nullable)
- `enrollment_number` (INTEGER, nullable)
- `raw_data` (JSONB) — full original record for extensibility
- `created_at` / `updated_at` (TIMESTAMPTZ)

Indexes: `trial_id`, `sponsor_name`, `status`.

## ClinicalTrials.gov API v2 — Critical Details
- Base: `https://clinicaltrials.gov/api/v2/studies`
- No API key. No auth. Generous rate limits.
- JSON default. Max `pageSize=1000` (default 10 — always set explicitly).
- Pagination is token-based via `pageToken`, NOT offset.
- Study data nests under `protocolSection`:
  - `identificationModule` → NCTId, briefTitle
  - `statusModule` → overallStatus, startDateStruct, completionDateStruct
  - `sponsorCollaboratorsModule` → leadSponsor.name
  - `armsInterventionsModule` → interventions[].type, .name
  - `outcomesModule` → primaryOutcomes[].measure, .description
  - `designModule` → phases[], enrollmentInfo.count
  - `contactsLocationsModule` → locations[].country
- **Dates are INCONSISTENT**: "2024-01-15", "January 2024", "January 15, 2024". Parse defensively with fallback chain.
- Arrays (interventions, locations, outcomes) may be null or empty. Never assume they exist.
- Example: `GET /api/v2/studies?query.term=cancer&pageSize=100&format=json`

## API Endpoints (Our API)
- `GET /health` — no DB, always 200
- `GET /api/v1/trials` — paginated (`?skip=0&limit=50`, max 100)
- `GET /api/v1/trials/{trial_id}` — by NCT ID
- `GET /api/v1/trials?sponsor=…&status=…` — filtered
- `GET /api/v1/export?format=ndjson|csv` — streaming bulk export
- Errors: `{"detail": "…"}`, 422 validation, 404 not found

## OpenAlex Integration
- Must be publicly reachable at a stable URL
- Standard REST + JSON responses
- Keep open (no auth) during evaluation
- Document base URL + example curls in README

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
- Batch inserts: max 500 per batch
- `/health` must not touch the database

## References
- See @GOALS.md for current phase and task status
- CT.gov API: https://clinicaltrials.gov/data-api/api
- CT.gov data structure: https://clinicaltrials.gov/data-api/about-api/study-data-structure
- OpenAlex API: https://docs.openalex.org/how-to-use-the-api/api-overview
