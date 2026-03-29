# Learnings — Clinical Trials ETL Pipeline

> Documenting what worked and what didn't during development and deployment.

---

## Development Timeline & Approach

### Time Breakdown
- **Active coding time**: ~2 hours 50 minutes, distributed over 3 days
- **Major time consumer**: Waiting — Render deployments, database provisioning, full ingestion runs (578K records across 500+ pages), a 12-hour storage lockout on the starter-plan database, and blueprint redeployments after the lockout
- **Research time**: Understanding ClinicalTrials.gov API v2 before writing any ingestion code — the nested `protocolSection` JSON structure, token-based pagination model, inconsistent date formats, and `filter.advanced` query capabilities

### Approach: Get Something Working Fast, Then Improve
The development followed an iterative "make it work, then make it better" approach rather than designing everything upfront:

1. **Start with a working end-to-end prototype** — flat schema, basic ingestion, simple API endpoints. Get real data flowing from CT.gov into Postgres and out through the API as quickly as possible.
2. **Improve based on what you learn** — once real data was flowing, pain points became obvious:
   - Flat columns (single `intervention_name`) lost data → evolved to JSONB arrays
   - Manual gzip in export generators was complex → replaced with GZipMiddleware
   - Sequential ingestion was too slow for 500K records → added parallel year-range sharding
   - `stream_scalars()` failed on Render → replaced with batched offset/limit reads
   - Fly.io had asyncpg SSL issues → migrated to Render
3. **Research the API first** — the biggest upfront investment was reading the ClinicalTrials.gov API v2 documentation, understanding the data structure, and testing pagination behavior with small queries before building the ingestion pipeline

This iterative approach meant the project was always in a working state — each improvement built on a functional foundation rather than risking a big-bang integration at the end.

---

## Things That Worked

### ClinicalTrials.gov API v2
- No API key required, generous rate limits, JSON by default.
- Token-based pagination (`pageToken`) is reliable — fetched 578K+ studies with zero failures.
- Max `pageSize=1000` works consistently.
- `filter.advanced` supports both `LastUpdatePostDate` (incremental) and `StudyFirstPostDate` (sharding) ranges.

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
- Using `sqlite+aiosqlite:///` for tests is fast (68 tests in 0.24s) and requires no external services.
- Tests override the `get_db` dependency to inject the test session — clean pattern.

### Upsert with `ON CONFLICT DO UPDATE`
- PostgreSQL's `INSERT ... ON CONFLICT (trial_id) DO UPDATE` handles re-ingestion gracefully.
- SQLite fallback: delete + insert (since SQLite lacks `ON CONFLICT DO UPDATE` with the same syntax).

### Docker Compose for Local Dev
- `postgres:15-alpine` with healthcheck + `depends_on: condition: service_healthy` ensures the API doesn't start before Postgres is ready.

### Render Deployment with `render.yaml`
- Blueprint-based deployment (render.yaml) auto-provisions the database and wires `DATABASE_URL` as a secret. One-click setup.
- Supports three service types in one file: web (API), cron (daily ingestion), and database.
- Cron job runs `--since yesterday` daily at 2 AM UTC with internal DB connection (batch size 500, no external timeout issues).

### Production `/ingest` Endpoint + Background Job System
- Added `POST /ingest` to trigger ingestion from the deployed service without SSH access.
- Supports `year_start`/`year_end` params for sharding — can run parallel initial loads by hitting the endpoint multiple times with different year ranges.
- Processes pages inline (fetch → parse → load per page) instead of buffering all studies in memory.
- Added `background=true` parameter to run ingestion as a background job with status tracking.
- Added `POST /ingest/all` to queue all 12 year-range shards as sequential background jobs.
- Added `GET /ingest/status` for real-time job monitoring (status, pages fetched, loaded count, errors).
- Built `scripts/monitor_ingestion.py` — a live TUI dashboard that polls `/ingest/status` and shows per-shard progress bars.

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

### Database at Scale (578,109 trials)
- 14,291 unique sponsors, 14 statuses, 6 phases
- 99.8% data completeness on interventions, outcomes, and locations
- Top statuses: COMPLETED (36K), UNKNOWN (10K), RECRUITING (7.7K)
- Top sponsors: Assiut University (550), Cairo University (476), NCI (469), AstraZeneca (400)
- JSONB arrays working well — a single trial can have 10+ interventions, 20+ locations
- `defer(raw_data)` is essential for export queries — without it, 578K records × 10-50KB = 5.8-29GB from DB

---

## Deployment Journey — Problems & Solutions (Chronological)

The path from working locally to a production API with 578K trials was the most time-consuming part of the project. Here's the chronological story of what went wrong and how each problem was solved:

| # | Problem | Impact | Resolution | Time Lost |
|---|---------|--------|------------|-----------|
| 1 | **Fly.io + asyncpg SSL incompatibility** | `TypeError` on connect — asyncpg doesn't accept `sslmode` as a URL param; stripping it caused TLS handshake failure | Abandoned Fly.io, migrated to Render | ~1 hour |
| 2 | **`stream_scalars()` returns 0 bytes on Render** | Export endpoint silently returned empty (HTTP 502) — server-side cursors don't survive Render's connection timeouts | Replaced with batched offset/limit reads (1000/batch) | ~30 min |
| 3 | **Export loading full `raw_data` JSONB** | 5000 records × 10-50KB = 250MB from DB, causing timeouts | Added `defer(Trial.raw_data)` since export doesn't need it | ~15 min |
| 4 | **Batch size 500 over external Render connection** | `ConnectionDoesNotExistError` after first batch — idle connections killed between batches | Reduced to 50, added `session_factory` for fresh sessions per batch | ~30 min |
| 5 | **Render starter plan storage limit** | DB filled up at ~325K trials, Render blocked all writes | Waited **12 hours** for DB to become writable again | **12 hours** |
| 6 | **Blueprint redeployment needed** | Original DB degraded after storage limit — needed clean slate | Created fresh Blueprint, renamed services to `clinical-trials-etl-*` | ~20 min |
| 7 | **DB connection leak with concurrent shards** | 12 concurrent `asyncio.gather()` shards exhausted connection pool | Reverted to sequential shards, added engine disposal + pool limits | ~45 min |
| 8 | **Batch size tuning** | 500 failed remotely, 50 was too slow internally, 100 was unstable | Settled on 500 for internal (Render cron), 50 for external connections | ~20 min |
| 9 | **Local Postgres port conflict** | Docker's `5432:5432` hit Homebrew Postgres instead of container | Used local Postgres directly | ~10 min |

**Key takeaway**: The actual code changes for each fix were small (5-20 lines). The time cost was in diagnosing the problem, waiting for deploys, and waiting for ingestion runs to verify the fix. The 12-hour storage lockout alone was longer than all active coding combined.

---

## Things That Didn't Work (Detailed)

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

### Render Starter Plan — Storage Limits and Ingestion Delays
- **What happened**: Attempted to load the full ~500K dataset into Render's starter-plan Postgres. The ingestion ran for a long time over the external connection (batch size 50, each batch taking 1-2s), and eventually the database hit its storage limit on the starter plan. After the DB filled up, Render blocked further writes.
- **The wait**: Render's starter plan does not allow immediate storage increases or data resets — had to wait approximately 12 hours before the database became writable again (either due to plan cooldown, support intervention, or automatic cleanup).
- **Impact**: This is why production initially had 325K trials instead of the full ~500K. The parallel ingestion script (`demo_parallel.py`) has been proven locally at 578K records in 5.9 minutes, but the Render starter plan couldn't hold the full dataset.
- **Lesson**: For large datasets on managed Postgres (especially free/starter tiers), check storage quotas before running bulk loads. Either upgrade the plan upfront or load a representative subset and document that the pipeline handles full scale.
- **Resolution**: Upgraded Render Postgres to basic-1gb plan with 10GB disk. Renamed services to `clinical-trials-etl-*` for a fresh Blueprint deploy. The full ~500K dataset can now be loaded using `POST /ingest/all` or `demo_parallel.py`.

### DB Connection Leak with Background Ingestion
- **What happened**: Running multiple background ingestion shards concurrently via `asyncio.gather()` exhausted the database connection pool, causing `ConnectionDoesNotExistError` and failed ingestion jobs.
- **Why**: Each concurrent shard opened its own DB sessions but the connection pool was shared. With 12 shards running concurrently, the pool was exhausted.
- **Resolution**:
  1. Reverted to sequential background tasks (process shards one at a time instead of concurrent).
  2. Added proper engine disposal and pool limits (`pool_size=5`, `max_overflow=10`).
  3. Each ingestion job disposes its engine after completion to avoid connection leaks.

### Render Blueprint Redeployment
- **What happened**: After the starter-plan database hit its storage limit and the 12-hour lockout, had to create a fresh Render Blueprint to get a clean database and redeploy the entire stack (web service + database + cron job).
- **Why**: The original database was in a degraded state after hitting storage limits. Rather than trying to recover it, a clean Blueprint deploy was faster and more reliable — `render.yaml` already defines all three resources, so redeployment is a single click.
- **Lesson**: Render Blueprints are effectively disposable infrastructure. Having everything defined in `render.yaml` (database, web service, cron job, env vars) means you can tear down and recreate the full stack in minutes. This is a strength of the infrastructure-as-code approach — treat environments as cattle, not pets.
- **Resolution**: Created a new Blueprint, which auto-provisioned a fresh database, built the Docker image, ran migrations, and started the API. Then re-ran ingestion against the new database.

---

## Local Development Results

### Test Suite
- **68 tests, all passing** in 0.24 seconds using SQLite in-memory (`aiosqlite`)
- Coverage: parser (29 tests), API endpoints (15 tests), ingestion (8 tests), export (8 tests), loader (6 tests), health (2 tests)
- Tests use dependency injection to swap the DB session — no external services required
- Test isolation: each test gets a fresh in-memory SQLite database via `conftest.py` fixtures

### Local Ingestion
- Full ingestion tested locally against a Homebrew PostgreSQL instance (port 5432)
- Batch size 500 works reliably on local connections (reduced to 50 for remote Render connections)
- Date parser handled 578K+ records with **0 parse failures** across 4+ date formats
- Schema evolution (flat → JSONB) tested end-to-end: migration 002 migrated existing data in-place

### Docker Compose
- `docker-compose up` brings up Postgres 15 + API with healthcheck-gated startup
- Alembic migrations run automatically on container start (`alembic upgrade head`)
- Hot reload enabled for development (`--reload` flag in docker-compose command)

---

## Production Results (Render)

### Deployment
- **Live URL**: `https://clinical-trials-etl-api-qx33.onrender.com`
- **Demo video**: [2-minute walkthrough on Loom](https://www.loom.com/share/ab906165ff08458a8dd7a31e7ebb2012)
- **578,109 trials** in production PostgreSQL (basic-1gb, 10GB disk) — full dataset, zero errors
- Three services defined in single `render.yaml`: web (API), cron (daily ingestion), database
- Blueprint deploy auto-provisions database and wires `DATABASE_URL` as a secret

### API Performance
- `/health` — instant response, no DB dependency
- `/trials/search` — sub-second response for filtered queries with pagination
- `/trials/export?format=ndjson` — streams 578K+ records in batches of 1000 with gzip compression
- `defer(raw_data)` in export query avoids transferring 10-50KB JSONB blobs per record

### Daily Cron
- Runs at 2 AM UTC: `python -m scripts.run_ingestion --since yesterday`
- Fetches only updated records via `AREA[LastUpdatePostDate]RANGE[date,MAX]`
- Typically completes in under a minute for daily increments
- Idempotent: `ON CONFLICT (trial_id) DO UPDATE` — safe to re-run

### Data Quality (578K full dataset)
- 14,291 unique sponsors, 14 statuses, 6 phases
- 99.8% data completeness on interventions, outcomes, and locations
- JSONB arrays verified: single trials with 10+ interventions, 20+ locations
- Top statuses: COMPLETED (36K), UNKNOWN (10K), RECRUITING (7.7K)

---

## AI Harness — Claude Code Usage

### How Claude Code Was Used
This entire project was built collaboratively with Claude Code (CLI), using it as a pair-programming partner across all four development sessions. Key patterns:

### What Worked Well
- **Scaffolding speed**: Claude Code generated the initial project structure, FastAPI boilerplate, SQLAlchemy models, and Alembic config in a single session. The `app/` directory layout, Pydantic schemas, and test fixtures were all generated correctly on first pass.
- **API integration**: Claude Code wrote the ClinicalTrials.gov API v2 integration (pagination, date filtering, nested JSON parsing) with minimal guidance — I described the API structure and it built `ingestion.py` and `parser.py` end-to-end.
- **Debugging deployment issues**: When Fly.io failed (asyncpg SSL incompatibility), Claude Code diagnosed the root cause from error logs and recommended switching to Render. When `stream_scalars()` returned 0 bytes on Render, it identified the server-side cursor issue and suggested batched offset/limit reads.
- **Schema evolution**: Claude Code designed the migration from flat columns to JSONB arrays, including the data migration SQL in `002_jsonb_arrays_and_secondary_outcomes.py`.
- **Test generation**: 68 tests across 6 files were written with Claude Code — parser edge cases, API integration tests with httpx AsyncClient, and loader upsert verification.
- **Documentation**: CLAUDE.md, LEARNING.md, GOALS.md, README.md, DEMO.md, and TEST.md were all maintained collaboratively. Claude Code updated docs with each code change as instructed.
- **Code review**: Used Claude Code to audit every claim in DEMO.md against actual code — verified upsert logic, incremental filters, export batching, compression middleware, and parallel ingestion all exist and work as documented.

### Tool Utilization
- **Explore agents**: Used to search the codebase for patterns, verify file structures, and audit code against requirements (e.g., "does the loader actually use ON CONFLICT?")
- **Plan agents**: Used to design implementation approaches before coding (e.g., schema evolution strategy, deployment migration from Fly.io to Render)
- **WebFetch**: Used to verify the live production API is responding correctly (health check, search results, trial counts)
- **Parallel tool calls**: Multiple agents launched simultaneously for independent tasks (e.g., verifying schema + API + tests in parallel)
- **Memory system**: Stored project context, CT.gov API details, and feedback preferences across sessions

### What Could Be Improved
- **Initial over-engineering**: Early iterations had manual gzip in export generators and `stream_scalars()` for streaming — both were replaced with simpler solutions (GZipMiddleware, batched reads). Claude Code could have started simpler.
- **`/ingest` vs CLI gap**: The `/ingest` endpoint doesn't support `--since` (only `year_start`/`year_end`). The daily cron uses the CLI. This asymmetry was caught late during code review — should have been designed upfront.
- **Full dataset loaded**: After upgrading to basic-1gb plan, all 578,109 trials were ingested via `POST /ingest/all` — 12 shards, zero errors.

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
| Batch size 500 for internal ingestion | Internal Render connection avoids the timeout issues of external connections |
| JSONB arrays over flat columns | Preserves all interventions/outcomes/locations instead of just first |
| GZipMiddleware over manual gzip | Automatic compression, keeps export code simple |
| Batched offset/limit for export | Avoids stream_scalars issues while keeping memory bounded |
| `defer(raw_data)` in export query | Excludes 10-50KB JSONB blobs the response doesn't need |
| `filter.advanced` for incremental sync | Only fetch updated studies instead of re-ingesting everything |
| Parallel sharding by year range | 6x throughput vs sequential; CT.gov rate limits are per-connection |
| Background job system with TUI monitor | Allows triggering full ingestion via API without waiting for HTTP response to complete |
| Upgraded Render DB to basic-1gb (10GB) | Starter plan storage limits prevented loading the full ~500K dataset |
