# Learnings — Clinical Trials ETL Pipeline

> Documenting what worked and what didn't during development and deployment.

---

## Things That Worked

### ClinicalTrials.gov API v2
- No API key required, generous rate limits, JSON by default.
- Token-based pagination (`pageToken`) is reliable — fetched 5000 studies across 5 pages with zero failures.
- Max `pageSize=1000` works consistently.

### Date Parsing with Fallback Chain
- CT.gov dates come in 4+ formats: `"2018-11-29"`, `"2015-10"`, `"January 2024"`, `"January 15, 2024"`.
- A simple try/except chain (ISO → year-month → month-year text → full text → None) handled every format encountered across 5000 records with **0 parse errors**.

### SQLAlchemy Async + Pydantic v2
- `asyncpg` + `SQLAlchemy 2.0` async works well for the API layer.
- `Pydantic v2` with `model_validate()` + `from_attributes=True` makes ORM → response conversion trivial.
- `model_dump_json()` for NDJSON export is fast and clean.

### JSONB with `with_variant`
- `JSON().with_variant(JSONB, "postgresql")` lets the model use JSONB on Postgres and JSON on SQLite (for tests). No conditional code needed.

### SQLite In-Memory Tests
- Using `sqlite+aiosqlite:///` for tests is fast (56 tests in 0.2s) and requires no external services.
- Tests override the `get_db` dependency to inject the test session — clean pattern.

### Upsert with `ON CONFLICT DO UPDATE`
- PostgreSQL's `INSERT ... ON CONFLICT (trial_id) DO UPDATE` handles re-ingestion gracefully.
- SQLite fallback: delete + insert (since SQLite lacks `ON CONFLICT DO UPDATE` with the same syntax).

### Docker Compose for Local Dev
- `postgres:15-alpine` with healthcheck + `depends_on: condition: service_healthy` ensures the API doesn't start before Postgres is ready.

### Render Deployment with `render.yaml`
- Blueprint-based deployment (render.yaml) auto-provisions the database and wires `DATABASE_URL` as a secret. One-click setup.

### Schema Evolution: Flat Columns → JSONB Arrays
- **Original**: `intervention_type`, `intervention_name`, `primary_outcome_measure`, `primary_outcome_description`, `location_country` — single scalar columns that only captured the first item from each array.
- **Evolved to**: `interventions`, `primary_outcomes`, `secondary_outcomes`, `locations` — full JSONB arrays storing all items from CT.gov.
- **Why**: A trial can have 5+ interventions, 3+ outcomes, locations in 10+ countries. Flattening to a single value lost critical data. JSONB arrays preserve full fidelity while still being queryable via Postgres JSONB operators.
- **Bonus**: Added `secondary_outcomes` which wasn't in the original schema — free with JSONB.

### GZipMiddleware over Manual Gzip
- Initially implemented gzip compression manually in the export generators (writing to `gzip.GzipFile` in an `io.BytesIO` buffer). This added complexity and made the export code hard to read/test.
- Switched to `GZipMiddleware(minimum_size=1000)` in `app/main.py` — automatic, transparent compression for all responses > 1KB when client sends `Accept-Encoding: gzip`. Export code stays simple (yields plain strings).
- Batched DB reads (1000 records at a time via offset/limit) with `defer(Trial.raw_data)` keeps memory bounded and avoids the `stream_scalars` issues.

### Incremental Ingestion via `filter.advanced`
- CT.gov API supports `AREA[LastUpdatePostDate]RANGE[MM/DD/YYYY,MAX]` to fetch only recently updated studies.
- Added `since_date` parameter to `run_full_ingestion()` to support incremental sync without re-fetching everything.

### Parallel Ingestion via Year-Range Sharding
- CT.gov's `pageToken` pagination is inherently sequential — can't parallelize a single stream.
- **Solution**: Split the dataset into 12 year-range shards (1999-2005, 2006-2009, ..., 2025-2026) using `AREA[StudyFirstPostDate]RANGE[start,end]` and run them concurrently with `asyncio.gather()` + a semaphore.
- **Result**: 6 concurrent workers ingested **578,109 trials in 5.9 minutes** (1,633 records/sec) — a ~4-5x improvement over sequential.
- Key insight: CT.gov doesn't rate-limit per IP, it rate-limits per connection. Multiple connections work fine.

---

## Things That Didn't Work

### Fly.io + asyncpg SSL Incompatibility
- **What happened**: Fly.io attaches Postgres with `?sslmode=disable` in the DATABASE_URL. `asyncpg` does not recognize `sslmode` as a URL query parameter and throws `TypeError: connect() got an unexpected keyword argument 'sslmode'`.
- **Attempted fix**: Stripped `sslmode=disable` from the URL in a Pydantic `model_validator`.
- **Result**: Stripping it caused asyncpg to default to SSL (`prefer` mode), but Fly's internal Postgres doesn't support SSL → `ConnectionResetError` during TLS handshake.
- **Resolution**: Abandoned Fly.io in favor of Render, which provides standard PostgreSQL URLs that asyncpg handles natively.

### `stream_scalars()` on Render
- **What happened**: Replaced `scalars()` with `stream_scalars()` for memory-efficient streaming export. The endpoint returned **0 bytes** silently (HTTP 502).
- **Why**: `stream_scalars()` uses server-side cursors which require the connection to stay open during the entire streaming response. Render's managed Postgres appears to close idle connections during the stream, and Starlette's `StreamingResponse` swallows the resulting exception.
- **Resolution**: Replaced with batched offset/limit reads (1000 records at a time) — keeps memory bounded without needing server-side cursors.

### Export Loading Full `raw_data` JSONB
- **What happened**: `select(Trial)` loads every column including `raw_data` (the full CT.gov JSON blob, often 10-50KB per record). For 5000 records, this is 50-250MB of data transferred from the database — causing timeouts on Render.
- **Resolution**: Added `defer(Trial.raw_data)` to the export query since `TrialResponse` doesn't include `raw_data`. This dramatically reduces the data fetched.

### Batch Size 500 on Render External Connection
- **What happened**: Inserting 500-record batches over the public internet to Render's Postgres caused `ConnectionDoesNotExistError: connection was closed in the middle of operation` after the first batch.
- **Why**: Render's free/starter tier has aggressive connection timeouts. Large batch inserts with JSONB data take 10-15 seconds each, and the connection pool's idle connections get terminated between batches.
- **Resolution**:
  1. Reduced batch size to 50 (each batch completes in ~1-2 seconds).
  2. Added `session_factory` parameter to `load_trials()` so each batch uses a fresh database session instead of reusing a stale one.

### Local Postgres Port Conflict with Docker
- **What happened**: A local Homebrew Postgres was already running on port 5432. Docker's port mapping (`5432:5432`) appeared to work, but connections from the host hit the local Postgres (which had a different user) instead of the Docker container.
- **Error**: `role "postgres" does not exist` — the local Postgres runs as the OS user, not as `postgres`.
- **Resolution**: Used the local Postgres directly instead of Docker. Created the `clinical_trials` database there.

### `allow_credentials=True` with Wildcard Origin
- **What happened**: CORS config had `allow_origins=["*"]` with `allow_credentials=True`. This is invalid per the CORS spec — browsers reject credentialed requests with wildcard origins.
- **Resolution**: Changed to `allow_credentials=False`. The API has no authentication, so credentials are irrelevant.

### Alembic Migration Not Auto-Generated
- **What happened**: Alembic was configured (env.py, script.py.mako) but `alembic/versions/` was empty. The docker-compose CMD ran `alembic upgrade head` on startup, which did nothing.
- **Resolution**: Manually wrote the initial migration (`001_initial_schema.py`) since `alembic revision --autogenerate` requires a running Postgres connection.

---

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| API v2 (JSON) over XML/CSV dump | Real-time, paginated, no file management needed |
| Single `trials` table + JSONB arrays | Scalar columns for querying, JSONB arrays for full data fidelity |
| `pageToken` pagination (CT.gov) vs offset | CT.gov API requires token-based pagination |
| `skip/limit` pagination (our API) vs cursor | Simpler for consumers, acceptable at MVP scale |
| ILIKE for filtering | Case-insensitive partial matching without extra indexes |
| Render over Fly.io | Standard Postgres URLs, simpler deployment, no SSL workarounds |
| Batch size 50 for remote ingestion | Balances throughput vs connection stability on managed Postgres |
| JSONB arrays over flat columns | Preserves all interventions/outcomes/locations instead of just first |
| GZipMiddleware over manual gzip | Automatic compression, keeps export code simple |
| Batched offset/limit for export | Avoids stream_scalars issues while keeping memory bounded |
| `defer(raw_data)` in export query | Excludes 10-50KB JSONB blobs the response doesn't need |
| `filter.advanced` for incremental sync | Only fetch updated studies instead of re-ingesting everything |
| Parallel sharding by year range | 6x throughput vs sequential; CT.gov rate limits are per-connection |
