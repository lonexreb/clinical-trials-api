# Demo Script — Clinical Trials ETL Pipeline

> Under 2 minutes. Four steps per the brief: run daily ingest → check DB rows → call export → call search.

**Demo Video**: [Watch on Loom](https://www.loom.com/share/ab906165ff08458a8dd7a31e7ebb2012)

**Live URL**: `https://clinical-trials-etl-api-qx33.onrender.com`

---

## 1. Run the Daily Ingest (30s)

```bash
curl -s -X POST "https://clinical-trials-etl-api-qx33.onrender.com/ingest?max_pages=2" | python3 -m json.tool
```

**Say**: "This triggers the ingestion pipeline — fetches trials from ClinicalTrials.gov API v2, normalizes them into our schema, and upserts into PostgreSQL. In production, a cron job runs this daily at 2 AM UTC with `--since yesterday` for incremental sync. Upserts mean running it twice creates no duplicates."

---

## 2. Check a Few Rows in the DB (30s)

```bash
# Show total count
curl -s "https://clinical-trials-etl-api-qx33.onrender.com/ingest/status" | python3 -m json.tool

# Show actual rows with structured fields
curl -s "https://clinical-trials-etl-api-qx33.onrender.com/trials/search?limit=3" | python3 -m json.tool
```

Point out: `trial_id`, `title`, `status`, `sponsor_name`, `interventions` (JSONB array), `primary_outcomes`, `secondary_outcomes`, `enrollment_number`, `start_date`, `locations`.

---

## 3. Call the Export Endpoint (20s)

```bash
curl -s "https://clinical-trials-etl-api-qx33.onrender.com/trials/export?format=ndjson" | head -2 | python3 -m json.tool
```

**Say**: "Export streams all records as NDJSON or CSV. Reads from the database in batches of 1000 with automatic gzip compression. OpenAlex can consume this as a full dataset dump."

---

## 4. Call the Search Endpoint (20s)

```bash
curl -s "https://clinical-trials-etl-api-qx33.onrender.com/trials/search?sponsor=Pfizer&phase=PHASE3&status=RECRUITING&limit=2" | python3 -m json.tool
```

**Say**: "Search supports filtering by sponsor, phase, and status — case-insensitive partial matching. Pagination via skip/limit. This is the exact call OpenAlex would make — single HTTP GET, no auth, standard JSON."

---

## Wrap-Up (10s)

**Say**: "To run locally: `git clone`, `docker-compose up` — Postgres and the API start with migrations applied automatically. The production instance on Render has the database, web service, and daily cron defined in a single `render.yaml`."
