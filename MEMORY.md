# Memory Index

> This file seeds Claude Code's auto-memory for the clinical trials project.
> Install: `cp MEMORY.md ~/.claude/projects/<project-slug>/memory/MEMORY.md`
> Claude reads the first 200 lines at session start, then manages this file itself.

## Project
- Clinical trials ETL pipeline: ClinicalTrials.gov → PostgreSQL → FastAPI API
- Consumer: OpenAlex (will call our API directly)
- See CLAUDE.md for conventions, schema, commands
- See GOALS.md for session-by-session task tracking

## Data Source: ClinicalTrials.gov API v2
- Base URL: `https://clinicaltrials.gov/api/v2/studies`
- No auth required. JSON default. Max pageSize=1000.
- Pagination: token-based (`pageToken`), NOT offset. Must follow tokens to exhaustion.
- Study data nests deeply: `protocolSection.identificationModule.nctId` etc.
- Date formats are inconsistent — parser must try ISO, "Month Year", "Month Day, Year"
- Arrays (interventions, locations, outcomes) can be null or empty
- pytrials library exists but may target old API — consider raw httpx/aiohttp instead

## Architecture Decisions
- Async SQLAlchemy with asyncpg driver for PostgreSQL
- Single `trials` table with JSONB `raw_data` column for schema evolution
- Batch upserts (INSERT ON CONFLICT) in groups of 500
- StreamingResponse for bulk export (NDJSON and CSV)
- pydantic-settings for all configuration via environment variables
- Alembic for migrations — never modify applied migration files

## Key Dependencies
- fastapi, uvicorn[standard], pydantic, pydantic-settings
- sqlalchemy[asyncio], asyncpg, alembic
- httpx (async HTTP client for CT.gov API)
- pytest, pytest-asyncio, httpx (test client)
- ruff (linting), mypy (type checking)
- python-dotenv (local .env loading)

## Field Mapping: CT.gov → Our Schema
- trial_id ← protocolSection.identificationModule.nctId
- title ← protocolSection.identificationModule.briefTitle
- phase ← protocolSection.designModule.phases[0] (may be list, take first)
- status ← protocolSection.statusModule.overallStatus
- sponsor_name ← protocolSection.sponsorCollaboratorsModule.leadSponsor.name
- intervention_type ← protocolSection.armsInterventionsModule.interventions[0].type
- intervention_name ← protocolSection.armsInterventionsModule.interventions[0].name
- primary_outcome_description ← protocolSection.outcomesModule.primaryOutcomes[0].description
- primary_outcome_measure ← protocolSection.outcomesModule.primaryOutcomes[0].measure
- start_date ← protocolSection.statusModule.startDateStruct.date (parse defensively)
- completion_date ← protocolSection.statusModule.completionDateStruct.date (parse defensively)
- location_country ← protocolSection.contactsLocationsModule.locations[0].country
- enrollment_number ← protocolSection.designModule.enrollmentInfo.count
- raw_data ← entire study object as-is

## Deployment
- Target: Render (Web Service + managed PostgreSQL) or Fly.io (Docker + Fly Postgres)
- Render: free tier has 750 hrs/mo, Postgres expires after 90 days unless upgraded
- Fly.io: 3 free shared VMs, Postgres via `fly postgres create`
- Production command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Must run `alembic upgrade head` on production DB before first request

## Debugging Notes
- [Claude will populate this section as issues are encountered]

## Topic Files
- [Claude creates additional .md files here for detailed notes as needed]
