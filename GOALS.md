# Project Goals — Clinical Trials ETL Pipeline

> **Purpose**: Track progress across sessions. Update `[ ]` → `[x]` as work completes.
> Referenced from CLAUDE.md via `@GOALS.md`.
>
> **Timeline**: ~8–9 hours active coding over 4 days across 6 sessions. Initial development took ~2h50m across 4 sessions (Sessions 1–4); Session 5 (~5–6 hours on Mar 31, 2026) addressed detailed evaluation feedback from OpenAlex's CEO; Session 6 addressed all remaining schema and API gaps. Most elapsed time beyond coding was waiting on deploys, ingestion runs, and infrastructure.

## Success Definition
A working end-to-end system that ingests real trial records from ClinicalTrials.gov, stores them in a clean extensible PostgreSQL database, and serves them to OpenAlex via a public API. Focus is a functional MVP — precision can be improved later.

## Deliverables
1. [x] Public GitHub repository with all source code
2. [ ] Short demo video walking through ingestion → storage → API call
3. [x] Production-ready URL where the API is live and reachable by OpenAlex
4. [x] Documentation: README, setup steps, env vars, example request

---

## Session 1 — Foundation (≈ 3 hours)
> Goal: Repo, database, schema, and a working ingestion script tested against a small sample.

- [x] Initialize repo: `pyproject.toml` / `requirements.txt`, `.gitignore`, `.env.example`
- [x] Project structure: `app/api/v1/`, `app/core/`, `app/models/`, `app/schemas/`, `app/services/`, `app/db/`, `tests/`
- [x] `app/core/config.py`: pydantic-settings `Settings` class (DATABASE_URL, CT_GOV_BASE_URL, BATCH_SIZE)
- [x] Docker-compose: PostgreSQL 15 + API service
- [x] SQLAlchemy async engine + session factory in `app/db/`
- [x] Alembic init + first migration: `trials` table with all core schema columns + JSONB `raw_data` + indexes
- [x] `GET /health` endpoint (no DB dependency)
- [x] `app/services/ingestion.py`: fetch studies from CT.gov API v2, paginate via `pageToken`
- [x] `app/services/parser.py`: map nested `protocolSection` → JSONB arrays + flat columns, handle inconsistent dates
- [x] Test with 50–100 real records: verify data lands in Postgres correctly
- [x] Commit + push

**Done when**: `docker-compose up` starts everything, ingestion script pulls real trials into the database, `/health` returns 200.

---

## Session 2 — Full Ingestion Pipeline (≈ 3 hours)
> Goal: Reliable bulk ingestion with error handling and validation logging.

- [x] `app/services/loader.py`: batch INSERT (upsert on `trial_id` conflict), max 500 per batch
- [x] Full pagination loop: keep following `pageToken` until all records fetched
- [x] Pydantic model for parsed trial record (validates before insert)
- [x] Validation error logging: failed records → `ingestion_errors` log file with raw data + reason
- [x] Handle nullable/missing fields: null interventions, missing outcomes, empty locations
- [x] Date parser: try ISO 8601 → "Month Year" → "Month Day, Year" → null fallback
- [x] `enrollment_number`: extract from `enrollmentInfo.count`, handle missing
- [x] Run full ingestion: 578,109 trials ingested (full CT.gov dataset)
- [x] Verify data quality: spot-check records against CT.gov website
- [x] Unit tests for `parser.py` (date parsing, missing fields, array fields, secondary outcomes)
- [x] Commit + push

**Done when**: Thousands of real trials in the database, error log captures any failures, spot-checks match CT.gov.

---

## Session 3 — API Endpoints + Bulk Export (≈ 3 hours)
> Goal: All API routes working with pagination, filtering, and streaming export.

- [x] Pydantic response schemas: `TrialResponse`, `TrialListResponse` (with pagination meta)
- [x] `GET /trials/search` — paginated list (`skip`, `limit`), default 50, max 100
- [x] `GET /trials/{trial_id}` — single trial by NCT ID, 404 if not found
- [x] `GET /trials/search?sponsor=…&status=…&phase=…` — query filters (case-insensitive ILIKE)
- [x] `GET /trials/export?format=ndjson` — StreamingResponse, one JSON object per line
- [x] `GET /trials/export?format=csv` — StreamingResponse, CSV with header row
- [x] GZipMiddleware for automatic response compression
- [x] Error handling: consistent `{"detail": "…"}` format
- [x] CORS middleware (allow all origins)
- [x] Integration tests: test each endpoint with httpx AsyncClient against test DB
- [x] Verify `/docs` (Swagger UI) is accurate and usable
- [x] Commit + push

**Done when**: All endpoints return correct data, filters work (sponsor + status + phase), export streams without memory issues, tests pass.

---

## Session 4 — Deploy + Documentation + Demo (≈ 2 hours)
> Goal: Live public URL, complete docs, demo video recorded.

- [x] `Dockerfile`: multi-stage build, Python 3.11-slim, Uvicorn
- [x] Deploy target: Render (Web Service + PostgreSQL database)
- [x] Set env vars on deploy platform: `DATABASE_URL`, `ALLOWED_ORIGINS`
- [x] Run `alembic upgrade head` on production DB
- [x] Run ingestion against production DB
- [x] Verify public URL returns JSON: `curl https://clinical-trials-etl-api-qx33.onrender.com/trials/search?limit=5`
- [x] Verify export endpoint streams correctly
- [x] Write README:
  - [x] Project overview (1 paragraph)
  - [x] Quick start (clone, env, docker-compose up, migrate, ingest)
  - [x] Environment variables table
  - [x] API reference with curl examples for each endpoint
  - [x] Architecture diagram (text-based)
  - [x] OpenAlex integration example
  - [x] Daily incremental update instructions with cron example
- [ ] Record demo video: show ingestion → DB query → API call → export
- [x] Final commit + push

**Done when**: Public URL returns correct JSON, README is complete, video is recorded, repo is clean.

---

## Additional Work Completed (Beyond Original Plan)
- [x] Schema evolution: flat columns → JSONB arrays for interventions, outcomes, locations
- [x] Added `secondary_outcomes` JSONB field (requirement from take-home brief)
- [x] Added `phase` filter to `/trials/search` endpoint
- [x] Added `phase` index to database
- [x] Incremental daily ingestion via `--since` flag using CT.gov `LastUpdatePostDate` filter
- [x] Parallel ingestion: 6 concurrent workers sharded by year range (578K records in 5.9 min)
- [x] Streaming page-by-page ingestion (constant memory regardless of dataset size)
- [x] Batched export (1000 records/batch) with `defer(raw_data)` for memory efficiency
- [x] Migration 002: JSONB arrays + secondary outcomes + data migration from flat columns
- [x] Background ingestion with job tracking (`POST /ingest?background=true`)
- [x] Bulk ingestion via `POST /ingest/all` — queues all 12 year-range shards
- [x] Ingestion status monitoring via `GET /ingest/status`
- [x] Live TUI monitor (`scripts/monitor_ingestion.py`) for tracking background jobs
- [x] Upgraded Render Postgres to basic-1gb plan with 10GB disk
- [x] Fixed DB connection leak: engine dispose + pool limits for background ingestion

---

## Session 5 — Post-Evaluation Fixes (Mar 31, 2026, ~5–6 hours)
> Goal: Address all feedback from OpenAlex CEO's detailed evaluation (graded B+, decision: Advance).

- [x] Added `updated_since` date filter to `/trials/search` for OpenAlex daily polling
- [x] Replaced OFFSET pagination with keyset pagination (`WHERE id > last_id`) in export endpoint
- [x] Changed status filter from ILIKE substring to exact match (preserves `ix_trials_status` index)
- [x] Extracted `conditions` from CT.gov `conditionsModule` — new JSONB column + parser + schema + migration 003
- [x] Added `ix_trials_updated_at` index via `CREATE INDEX CONCURRENTLY` (non-blocking on 578K rows)
- [x] Added 7 new tests (75 total): status exact match, updated_since filtering, conditions parsing
- [x] Updated all documentation (README, CLAUDE.md, LEARNING.md, GOALS.md) with corrected timeline and post-evaluation work
- [x] Addressed automated PR review comments from Codex, CodeRabbit, and Cursor Bugbot

**Done when**: All evaluation feedback addressed, tests pass, docs consistent, PR merged.

---

## Session 6 — Schema Enrichment & Remaining Gaps (Mar 31, 2026)
> Goal: Address every remaining concern from the evaluation — leave no stone unturned.

- [x] Extracted `study_type` from CT.gov `designModule.studyType` (e.g., INTERVENTIONAL, OBSERVATIONAL)
- [x] Extracted `eligibility_criteria` from CT.gov `eligibilityModule.eligibilityCriteria` (free text)
- [x] Extracted `mesh_terms` from CT.gov `derivedSection.conditionBrowseModule.meshes` (list of MeSH term strings)
- [x] Extracted `references` (DOIs/PMIDs/citations) from CT.gov `referencesModule.references` (JSONB array)
- [x] Extracted `investigators` from CT.gov `contactsLocationsModule.overallOfficials` (JSONB array)
- [x] Added `source` field (TEXT, default "clinicaltrials.gov") for multi-registry readiness
- [x] Added `sort_by` + `order` (asc/desc) query parameters to `/trials/search`
- [x] Added `study_type` filter to `/trials/search` (exact match)
- [x] Added bounded retry logic to batch loader (3 attempts, exponential backoff: 1s, 2s, 4s)
- [x] Fixed `render.yaml` cron BATCH_SIZE from 50 → 500 (internal connection, not subject to external timeouts)
- [x] Migration 004: `study_type`, `eligibility_criteria`, `mesh_terms`, `references`, `investigators`, `source`
- [x] 20 new tests (95 total): parser extraction for all new fields, API enrichment response, study_type filter, sorting asc/desc/invalid, null fields
- [x] Updated all documentation (README, CLAUDE.md, GOALS.md, LEARNING.md) with new schema, test counts, and features

**Done when**: All evaluation concerns addressed, 95 tests pass, docs consistent.

---

## Pre-Session Checklist (do before starting each timer)
- [x] Dependencies installed (`pip install -r requirements.txt`)
- [x] `.env` configured with DB credentials
- [x] Docker running (for local Postgres)
- [x] `alembic upgrade head` ran successfully

---

## Non-Goals (Out of Scope for MVP)
- No frontend / admin UI
- No real-time streaming — batch ingestion only
- No user authentication (open for evaluation)
- ~~No incremental/delta sync~~ — **Implemented**: `--since` flag with `LastUpdatePostDate` filter
- No multi-source support (ClinicalTrials.gov only)
- Precision tuning of field mappings (fix later based on OpenAlex feedback)
