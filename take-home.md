**Take-home project brief**

**Goal**
Build a minimal, end-to-end system that pulls clinical-trial records from ClinicalTrials.gov, normalizes them into a unified schema and makes the data available through both a bulk-export and a query API that OpenAlex can consume.

**Core requirements**

* **Schema** – include at least: trial ID, title, intervention, primary and secondary outcomes, sponsor, start date, status, phase, enrollment, location. Use JSONB fields for any semi-structured data.
* **Data volume** – work with the full set of roughly 500 K trials. The pipeline should be able to handle daily increments; the day is the granularity that matters.
* **Ingestion** – script that runs once a day, fetches new or updated records, normalizes them to the schema and upserts into the database.
* **Database** – PostgreSQL is the default choice; SQLite is acceptable for local testing but the final deliverable should run on Postgres.
* **API** – two endpoints:
  * `/trials/export` returns a compressed JSON or CSV dump of all records.
  * `/trials/search` accepts query parameters (e.g., sponsor, phase, status) and returns matching trials.
* **OpenAlex integration** – the API should be reachable via a simple HTTP call; a short example request/response showing OpenAlex pulling data is enough.
* **Demo** – a short video (under two minutes) that walks through: running the daily ingest, checking a few rows in the DB, calling the export endpoint and the search endpoint.
* **Code repo** – public GitHub repository with clear README, setup instructions, Dockerfile (or docker-compose) that brings up the DB and the service, and the demo video linked.

**Non-functional expectations**

* Daily updates must be idempotent; running the ingest twice for the same day should not create duplicates.
* The system should start processing the daily batch within a few minutes of launch and finish well before the next day's window.
* Keep the design simple and purposeful; avoid extra features that aren't needed for the core flow.

**Timeline**

* Aim to finish a working prototype within one week.
* Break the work into focused three-hour sessions:
  1. Define schema and set up Postgres.
  2. Implement daily fetch and normalization.
  3. Build the two API endpoints.
  4. Test end-to-end flow with real data and record the demo.

Deliver the GitHub repo, the demo video and a brief note confirming the daily-update capability.
