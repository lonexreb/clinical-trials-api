# Clinical Trials ETL Pipeline & API

REST API that ingests clinical trial data from [ClinicalTrials.gov](https://clinicaltrials.gov) API v2, normalizes it into a PostgreSQL database, and serves it through a queryable API with bulk export support. Built for [OpenAlex](https://openalex.org) integration.

## Live API

**Base URL**: `https://clinical-trials-api-meoh.onrender.com`

```bash
# Health check
curl https://clinical-trials-api-meoh.onrender.com/health

# Search trials (paginated)
curl "https://clinical-trials-api-meoh.onrender.com/trials/search?limit=5"

# Single trial by NCT ID
curl https://clinical-trials-api-meoh.onrender.com/trials/NCT00597909

# Filter by sponsor
curl "https://clinical-trials-api-meoh.onrender.com/trials/search?sponsor=pfizer&limit=5"

# Filter by status
curl "https://clinical-trials-api-meoh.onrender.com/trials/search?status=recruiting&limit=5"

# Filter by phase
curl "https://clinical-trials-api-meoh.onrender.com/trials/search?phase=PHASE3&limit=5"

# Bulk export (gzip-compressed NDJSON)
curl "https://clinical-trials-api-meoh.onrender.com/trials/export?format=ndjson" --compressed > trials.ndjson

# Bulk export (gzip-compressed CSV)
curl "https://clinical-trials-api-meoh.onrender.com/trials/export?format=csv" --compressed > trials.csv
```

## Architecture

```
ClinicalTrials.gov API v2        PostgreSQL          FastAPI
 ┌──────────────────┐       ┌───────────────┐    ┌──────────────────┐
 │  /api/v2/studies  │──────►│  trials table  │◄───│  /trials/search  │
 │  (JSON, paginated │ ETL  │  (JSONB arrays │    │  /trials/export  │
 │   via pageToken)  │      │   + flat cols) │    │  /health         │
 └──────────────────┘       └───────────────┘    └──────────────────┘
         │                         │                      │
    ingestion.py              loader.py              trials.py
    parser.py              (batch upsert)           export.py
```

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> && cd OpenAlex
cp .env.example .env

# 2. Start PostgreSQL
docker-compose up -d db

# 3. Install dependencies
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Run migrations
alembic upgrade head

# 5. Start the API
uvicorn app.main:app --reload --port 8000

# 6. Ingest trial data
python -m scripts.run_ingestion --query cancer --max-pages 5
```

Or run everything with Docker:
```bash
docker-compose up
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/clinical_trials` | PostgreSQL connection string |
| `CT_GOV_BASE_URL` | `https://clinicaltrials.gov/api/v2/studies` | ClinicalTrials.gov API base URL |
| `BATCH_SIZE` | `500` | Max records per batch insert (use 50 for remote Postgres) |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Reference

### Health Check
```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}
```

### Search Trials (paginated + filtered)
```bash
# Basic pagination
curl "http://localhost:8000/trials/search?skip=0&limit=10"

# Filter by sponsor (case-insensitive)
curl "http://localhost:8000/trials/search?sponsor=pfizer"

# Filter by status
curl "http://localhost:8000/trials/search?status=recruiting"

# Filter by phase
curl "http://localhost:8000/trials/search?phase=PHASE3"

# Combined filters
curl "http://localhost:8000/trials/search?sponsor=novartis&status=completed&limit=20"
```

Response:
```json
{
  "data": [
    {
      "trial_id": "NCT12345678",
      "title": "A Study of Drug X...",
      "phase": "PHASE3",
      "status": "RECRUITING",
      "sponsor_name": "Pfizer",
      "interventions": [{"type": "DRUG", "name": "Drug X"}],
      "primary_outcomes": [{"measure": "Overall Survival", "description": "Time from..."}],
      "secondary_outcomes": null,
      "start_date": "2023-01-15",
      "completion_date": "2025-12-31",
      "locations": [{"facility": "Hospital A", "city": "Boston", "country": "United States"}],
      "enrollment_number": 500,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ],
  "meta": {
    "total": 1000,
    "skip": 0,
    "limit": 10,
    "has_more": true
  }
}
```

### Get Single Trial
```bash
curl http://localhost:8000/trials/NCT12345678
# Returns single trial object, or 404
```

### Bulk Export
```bash
# Gzip-compressed NDJSON (one JSON object per line)
curl "http://localhost:8000/trials/export?format=ndjson" --compressed > trials.ndjson

# Gzip-compressed CSV
curl "http://localhost:8000/trials/export?format=csv" --compressed > trials.csv
```

Export streams data in batches of 1000 from the database, excluding the large `raw_data` field to keep responses fast.

### Interactive Docs
Open [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger UI.

## Data Ingestion

```bash
# Ingest all trials (follows pagination to completion)
python -m scripts.run_ingestion

# Ingest with search filter and page limit
python -m scripts.run_ingestion --query "breast cancer" --max-pages 10

# Each page fetches up to 1000 studies from ClinicalTrials.gov
```

Ingestion supports incremental updates via `since_date` parameter, using CT.gov's `LastUpdatePostDate` filter.

Ingestion errors are logged to `ingestion_errors.jsonl` for review.

## Schema

The `trials` table stores both structured columns for fast queries and JSONB arrays for full data fidelity:

| Column | Type | Description |
|--------|------|-------------|
| `trial_id` | TEXT (unique, indexed) | NCT ID |
| `title` | TEXT | Brief title |
| `phase` | TEXT (indexed) | e.g., PHASE1, PHASE2 |
| `status` | TEXT (indexed) | e.g., RECRUITING, COMPLETED |
| `sponsor_name` | TEXT (indexed) | Lead sponsor name |
| `interventions` | JSONB | Full array of intervention dicts |
| `primary_outcomes` | JSONB | Full array of primary outcome dicts |
| `secondary_outcomes` | JSONB | Full array of secondary outcome dicts |
| `start_date` | DATE | Study start date |
| `completion_date` | DATE | Expected/actual completion |
| `locations` | JSONB | Full array of location dicts |
| `enrollment_number` | INTEGER | Target/actual enrollment |
| `raw_data` | JSONB | Complete original CT.gov record |

## Running Tests

```bash
# All tests
pytest tests/ -v --tb=short

# Specific test file
pytest tests/test_parser.py -v

# With coverage
pytest tests/ -v --cov=app --cov-report=term-missing
```

See [TEST.md](TEST.md) for the full test matrix and verification checklist.

## Development

```bash
# Lint
ruff check .

# Type check
mypy app/

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Tech Stack

- **Python 3.11+** / **FastAPI** (async ASGI)
- **PostgreSQL 15** + **SQLAlchemy 2.0** (async) + **Alembic**
- **httpx** for async HTTP to ClinicalTrials.gov API v2
- **Pydantic v2** for validation and serialization
- **pytest** + **pytest-asyncio** + **aiosqlite** for testing
- **Render** for deployment (Docker + managed Postgres)

## Additional Docs

- [LEARNING.md](LEARNING.md) — What worked and what didn't during development
- [CLAUDE.md](CLAUDE.md) — Developer guide and conventions
- [GOALS.md](GOALS.md) — Session-by-session task tracking
- [TEST.md](TEST.md) — Test plan and verification checklist
