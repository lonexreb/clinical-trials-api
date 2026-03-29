# Clinical Trials ETL Pipeline & API

REST API that ingests clinical trial data from [ClinicalTrials.gov](https://clinicaltrials.gov) API v2, normalizes it into a PostgreSQL database, and serves it through a queryable API with bulk export support. Built for [OpenAlex](https://openalex.org) integration.

## Live API

**Base URL**: `https://clinical-trials-etl-api-qx33.onrender.com`

```bash
# Health check
curl https://clinical-trials-etl-api-qx33.onrender.com/health

# Search trials (paginated)
curl "https://clinical-trials-etl-api-qx33.onrender.com/trials/search?limit=5"

# Single trial by NCT ID
curl https://clinical-trials-etl-api-qx33.onrender.com/trials/NCT00597909

# Filter by sponsor
curl "https://clinical-trials-etl-api-qx33.onrender.com/trials/search?sponsor=pfizer&limit=5"

# Filter by status
curl "https://clinical-trials-etl-api-qx33.onrender.com/trials/search?status=recruiting&limit=5"

# Filter by phase
curl "https://clinical-trials-etl-api-qx33.onrender.com/trials/search?phase=PHASE3&limit=5"

# Bulk export (gzip-compressed NDJSON)
curl "https://clinical-trials-etl-api-qx33.onrender.com/trials/export?format=ndjson" --compressed > trials.ndjson

# Bulk export (gzip-compressed CSV)
curl "https://clinical-trials-etl-api-qx33.onrender.com/trials/export?format=csv" --compressed > trials.csv
```

## Current Database
- **325,733 trials** ingested from ClinicalTrials.gov
- **14,291** unique sponsors | **14** statuses | **6** phases
- 99.8% data completeness on interventions, outcomes, and locations
- Top statuses: COMPLETED (36K), RECRUITING (7.7K), TERMINATED (3.8K)
- Top sponsors: Assiut University, Cairo University, NCI, AstraZeneca, GSK, Pfizer
- Full ~500K dataset loadable via parallel ingestion (`scripts/demo_parallel.py`) in ~6 minutes

## Architecture

![Architecture Diagram](clinical-trial.png)

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

### Trigger Ingestion (from deployed service)
```bash
# Ingest cancer trials (2 pages)
curl -X POST "http://localhost:8000/ingest?query=cancer&max_pages=2"

# Shard by year range (for parallel loading)
curl -X POST "http://localhost:8000/ingest?year_start=2020&year_end=2023"

# Run in background (returns job_id for status polling)
curl -X POST "http://localhost:8000/ingest?year_start=2020&year_end=2023&background=true"

# Queue all 12 year-range shards as sequential background jobs
curl -X POST "http://localhost:8000/ingest/all"

# Check ingestion job status and DB count
curl http://localhost:8000/ingest/status
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

### Daily Incremental Updates

The pipeline supports incremental ingestion to fetch only records updated since a given date:

```bash
# Fetch only trials updated since yesterday
python -m scripts.run_ingestion --since yesterday

# Fetch trials updated since a specific date
python -m scripts.run_ingestion --since 2024-03-01

# Combine with query filter
python -m scripts.run_ingestion --since yesterday --query "cancer"
```

This uses ClinicalTrials.gov's `filter.advanced=AREA[LastUpdatePostDate]RANGE[date,MAX]` to only fetch new/updated records. Upserts are idempotent — running the same ingestion twice produces no duplicates.

**Setting up a daily cron job:**
```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/OpenAlex && .venv/bin/python -m scripts.run_ingestion --since yesterday
```

Ingestion errors are logged to `ingestion_errors.jsonl` for review.

### Parallel Initial Load

For the initial full dataset load (~500K+ trials), the parallel ingestion script splits the dataset into 12 year-range shards and fetches them concurrently:

```bash
# 6 concurrent workers — loads 578K trials in ~6 minutes
python -m scripts.demo_parallel --workers 6

# Or use the convenience script
./scripts/initial_load.sh
```

**Performance:** 578,109 trials loaded in 5.9 minutes (1,633 records/sec) with 6 concurrent workers.

### Live Ingestion Progress

Screenshots from a production ingestion run using `POST /ingest/all` with the TUI monitor (`scripts/monitor_ingestion.py`). Each shard processes sequentially, fetching trials by year range:

| ![Shards 1-3 running](live-demo-1.png) | ![Shards 4-5 complete](live-demo-2.png) |
|:---:|:---:|
| **33.8%** — First 3 shards complete (192K loaded) | **47.1%** — 5 shards done, shard 6 running |

| ![Halfway through](live-demo-3.png) | ![Shards 1-7 complete](live-demo-4.png) |
|:---:|:---:|
| **47.1%** — Shard 6 (2018-2019) in progress | **~60%** — 7 shards complete |

| ![Past 60%](live-demo-5.png) | ![8 shards done](live-demo-6.png) |
|:---:|:---:|
| **~65%** — Shard 8 (2021) running | **~75%** — 8 shards complete |

| ![Almost done](live-demo-7.png) | ![Final shard](live-demo-8.png) |
|:---:|:---:|
| **~90%** — 11 of 12 shards complete, final shard running | **~97%** — All shards complete except last (2025-2026) |

### Production Ingestion (Render)

On Render, ingestion runs as a **cron job** (not via HTTP endpoints) with direct internal DB access:
- **Daily cron**: runs at 2 AM UTC via `render.yaml`, fetches only new/updated records
- **Initial load**: trigger the cron job manually from the Render dashboard, use `POST /ingest/all` to queue all shards, or run `scripts/initial_load.sh` as a one-off job
- **Batch size**: 500 (uses internal DB connection, no external timeout limits)
- **Monitor progress**: `python -m scripts.monitor_ingestion --url https://clinical-trials-etl-api-qx33.onrender.com` — live TUI dashboard for background ingestion jobs

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

## OpenAlex Integration

The API is designed for direct consumption by OpenAlex. Example workflow:

```bash
# 1. Search for Phase 3 recruiting trials sponsored by Pfizer
curl "https://clinical-trials-etl-api-qx33.onrender.com/trials/search?sponsor=pfizer&phase=phase3&status=recruiting&limit=100"

# 2. Bulk export all trials as NDJSON for batch processing
curl --compressed "https://clinical-trials-etl-api-qx33.onrender.com/trials/export?format=ndjson" -o all_trials.ndjson

# 3. Get a specific trial by NCT ID
curl "https://clinical-trials-etl-api-qx33.onrender.com/trials/NCT12345678"
```

No authentication required. Standard JSON responses. CORS enabled for all origins.

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

## Daily-Update Capability

The system supports fully automated, idempotent daily updates:

- **Cron job** runs daily at 2 AM UTC via `render.yaml`, executing `python -m scripts.run_ingestion --since yesterday`.
- **Incremental fetch**: uses ClinicalTrials.gov's `AREA[LastUpdatePostDate]RANGE[date,MAX]` filter to pull only new or updated records — typically completes in under a minute.
- **Idempotent upserts**: `INSERT ... ON CONFLICT (trial_id) DO UPDATE` ensures running the ingest twice for the same day produces no duplicates.
- **Batch processing**: starts within seconds of launch; a full day's updates (typically a few hundred to a few thousand records) finish well before the next day's window.

## Development Approach

Built in ~2 hours 50 minutes of active coding, distributed over 3 days. Most elapsed time was spent waiting — Render deployments, database provisioning, full ingestion runs (578K records), and a 12-hour storage lockout on the starter-plan database.

**Approach**: Research the ClinicalTrials.gov API v2 design first (nested JSON structure, pagination model, date formats), then get a working end-to-end prototype fast and iteratively improve — flat schema to JSONB arrays, manual gzip to middleware, sequential to parallel ingestion, Fly.io to Render.

See [LEARNING.md](LEARNING.md) for the full breakdown of what worked, what didn't, and key architectural decisions.

## Additional Docs

- [LEARNING.md](LEARNING.md) — What worked and what didn't, development timeline, AI harness usage
- [CLAUDE.md](CLAUDE.md) — Developer guide and conventions
- [GOALS.md](GOALS.md) — Session-by-session task tracking
- [TEST.md](TEST.md) — Test plan and verification checklist
