# Project Goals — Clinical Trials ETL Pipeline

> **Purpose**: Track progress across sessions. Update `[ ]` → `[x]` as work completes.
> Referenced from CLAUDE.md via `@GOALS.md`.

## Success Definition
A working end-to-end system that ingests real trial records from ClinicalTrials.gov, stores them in a clean extensible PostgreSQL database, and serves them to OpenAlex via a public API. Focus is a functional MVP — precision can be improved later.

## Deliverables
1. [ ] Public GitHub repository with all source code
2. [ ] Short demo video walking through ingestion → storage → API call
3. [ ] Production-ready URL where the API is live and reachable by OpenAlex
4. [ ] Documentation: README, setup steps, env vars, example request

---

## Session 1 — Foundation (≈ 3 hours)
> Goal: Repo, database, schema, and a working ingestion script tested against a small sample.

- [ ] Initialize repo: `pyproject.toml` / `requirements.txt`, `.gitignore`, `.env.example`
- [ ] Project structure: `app/api/v1/`, `app/core/`, `app/models/`, `app/schemas/`, `app/services/`, `app/db/`, `tests/`
- [ ] `app/core/config.py`: pydantic-settings `Settings` class (DATABASE_URL, CT_GOV_BASE_URL, BATCH_SIZE)
- [ ] Docker-compose: PostgreSQL 15 + API service
- [ ] SQLAlchemy async engine + session factory in `app/db/`
- [ ] Alembic init + first migration: `trials` table with all core schema columns + JSONB `raw_data` + indexes
- [ ] `GET /health` endpoint (no DB dependency)
- [ ] `app/services/ingestion.py`: fetch studies from CT.gov API v2, paginate via `pageToken`
- [ ] `app/services/parser.py`: map nested `protocolSection` → flat schema dict, handle inconsistent dates
- [ ] Test with 50–100 real records: verify data lands in Postgres correctly
- [ ] Commit + push

**Done when**: `docker-compose up` starts everything, ingestion script pulls real trials into the database, `/health` returns 200.

---

## Session 2 — Full Ingestion Pipeline (≈ 3 hours)
> Goal: Reliable bulk ingestion with error handling and validation logging.

- [ ] `app/services/loader.py`: batch INSERT (upsert on `trial_id` conflict), max 500 per batch
- [ ] Full pagination loop: keep following `pageToken` until all records fetched
- [ ] Pydantic model for parsed trial record (validates before insert)
- [ ] Validation error logging: failed records → `ingestion_errors` log file with raw data + reason
- [ ] Handle nullable/missing fields: null interventions, missing outcomes, empty locations
- [ ] Date parser: try ISO 8601 → "Month Year" → "Month Day, Year" → null fallback
- [ ] `enrollment_number`: extract from `enrollmentInfo.count`, handle missing
- [ ] Run full ingestion: target 1,000–10,000 trials as proof of concept
- [ ] Verify data quality: spot-check 10 records against CT.gov website
- [ ] Unit tests for `parser.py` (date parsing, missing fields, array fields)
- [ ] Commit + push

**Done when**: Thousands of real trials in the database, error log captures any failures, spot-checks match CT.gov.

---

## Session 3 — API Endpoints + Bulk Export (≈ 3 hours)
> Goal: All API routes working with pagination, filtering, and streaming export.

- [ ] Pydantic response schemas: `TrialResponse`, `TrialListResponse` (with pagination meta)
- [ ] `GET /api/v1/trials` — paginated list (`skip`, `limit`), default 50, max 100
- [ ] `GET /api/v1/trials/{trial_id}` — single trial by NCT ID, 404 if not found
- [ ] `GET /api/v1/trials?sponsor=…&status=…` — query filters (case-insensitive ILIKE)
- [ ] `GET /api/v1/export?format=ndjson` — StreamingResponse, one JSON object per line
- [ ] `GET /api/v1/export?format=csv` — StreamingResponse, CSV with header row
- [ ] Error handling middleware: consistent `{"detail": "…"}` format
- [ ] CORS middleware (allow OpenAlex origin)
- [ ] Integration tests: test each endpoint with httpx AsyncClient against test DB
- [ ] Verify `/docs` (Swagger UI) is accurate and usable
- [ ] Commit + push

**Done when**: All five endpoints return correct data, filters work, export streams without memory issues, tests pass.

---

## Session 4 — Deploy + Documentation + Demo (≈ 2 hours)
> Goal: Live public URL, complete docs, demo video recorded.

- [ ] `Dockerfile`: multi-stage build, Python 3.11-slim, Uvicorn
- [ ] Choose deploy target: Render (simplest) or Fly.io (cheapest)
  - Render: create Web Service + PostgreSQL database, connect via internal URL
  - Fly.io: `fly launch`, `fly postgres create`, `fly postgres attach`
- [ ] Set env vars on deploy platform: `DATABASE_URL`, `ALLOWED_ORIGINS`
- [ ] Run `alembic upgrade head` on production DB
- [ ] Run ingestion against production DB (or a representative subset)
- [ ] Verify public URL returns JSON: `curl https://<your-url>/api/v1/trials?limit=5`
- [ ] Verify export endpoint streams correctly
- [ ] Write README:
  - [ ] Project overview (1 paragraph)
  - [ ] Quick start (clone, env, docker-compose up, migrate, ingest)
  - [ ] Environment variables table
  - [ ] API reference with curl examples for each endpoint
  - [ ] Architecture diagram (text-based is fine)
- [ ] Record demo video: show ingestion → DB query → API call → export
- [ ] Share URL with Joseph
- [ ] Final commit + push

**Done when**: Public URL returns correct JSON, README is complete, video is recorded, repo is clean.

---

## Pre-Session Checklist (do before starting each timer)
- [ ] Dependencies installed (`pip install -e ".[dev]"` or `pip install -r requirements.txt`)
- [ ] `.env` configured with DB credentials
- [ ] Docker running (for local Postgres)
- [ ] `alembic upgrade head` ran successfully
- [ ] Git branch created for the session's work

---

## Non-Goals (Out of Scope for MVP)
- No frontend / admin UI
- No real-time streaming — batch ingestion only
- No user authentication (open for evaluation)
- No incremental/delta sync (full ingestion each run is fine for now)
- No multi-source support (ClinicalTrials.gov only)
- Precision tuning of field mappings (fix later based on OpenAlex feedback)
