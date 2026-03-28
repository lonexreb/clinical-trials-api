# Clinical Trials ETL Pipeline & API

REST API that ingests clinical trial data from [ClinicalTrials.gov](https://clinicaltrials.gov) API v2, normalizes it into a PostgreSQL database, and serves it through a queryable API with bulk export support. Built for [OpenAlex](https://openalex.org) integration.

## Live API

**Base URL**: `https://clinical-trials-api-meoh.onrender.com`

```bash
# Health check
curl https://clinical-trials-api-meoh.onrender.com/health

# List trials (paginated)
curl "https://clinical-trials-api-meoh.onrender.com/api/v1/trials?limit=5"

# Single trial by NCT ID
curl https://clinical-trials-api-meoh.onrender.com/api/v1/trials/NCT00597909

# Filter by sponsor
curl "https://clinical-trials-api-meoh.onrender.com/api/v1/trials?sponsor=pfizer&limit=5"

# Filter by status
curl "https://clinical-trials-api-meoh.onrender.com/api/v1/trials?status=recruiting&limit=5"

# Bulk export (NDJSON)
curl "https://clinical-trials-api-meoh.onrender.com/api/v1/export?format=ndjson" > trials.ndjson

# Bulk export (CSV)
curl "https://clinical-trials-api-meoh.onrender.com/api/v1/export?format=csv" > trials.csv
```

## Architecture

```
ClinicalTrials.gov API v2        PostgreSQL          FastAPI
 ┌──────────────────┐       ┌───────────────┐    ┌──────────────────┐
 │  /api/v2/studies  │──────►│  trials table  │◄───│  /api/v1/trials  │
 │  (JSON, paginated │ ETL  │  (JSONB + flat │    │  /api/v1/export  │
 │   via pageToken)  │      │   columns)     │    │  /health         │
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
| `BATCH_SIZE` | `500` | Max records per batch insert |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Reference

### Health Check
```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}
```

### List Trials (paginated + filtered)
```bash
# Basic pagination
curl "http://localhost:8000/api/v1/trials?skip=0&limit=10"

# Filter by sponsor (case-insensitive)
curl "http://localhost:8000/api/v1/trials?sponsor=pfizer"

# Filter by status
curl "http://localhost:8000/api/v1/trials?status=recruiting"

# Combined filters
curl "http://localhost:8000/api/v1/trials?sponsor=novartis&status=completed&limit=20"
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
      "intervention_type": "DRUG",
      "intervention_name": "Drug X",
      "primary_outcome_measure": "Overall Survival",
      "primary_outcome_description": "Time from randomization...",
      "start_date": "2023-01-15",
      "completion_date": "2025-12-31",
      "location_country": "United States",
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
curl http://localhost:8000/api/v1/trials/NCT12345678
# Returns single trial object, or 404
```

### Bulk Export
```bash
# NDJSON (one JSON object per line)
curl "http://localhost:8000/api/v1/export?format=ndjson" > trials.ndjson

# CSV
curl "http://localhost:8000/api/v1/export?format=csv" > trials.csv
```

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

Ingestion errors are logged to `ingestion_errors.jsonl` for review.

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
