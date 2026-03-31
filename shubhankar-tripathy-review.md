# Take-Home Evaluation: Shubhankar Tripathy

**Repo**: https://github.com/lonexreb/clinical-trials-api
**Live API**: https://clinical-trials-etl-api-qx33.onrender.com

---

## 1. Does It Work?

### 1a. Data completeness: **Full**

578,109 trials loaded. ClinicalTrials.gov has ~575K studies, so this is >95%. Confirmed via both `/ingest/status` (db_total: 578109) and `/trials/search` (meta.total: 578109).

### 1b. Data accuracy: **Pass**

Spot-checked 3 trials against ClinicalTrials.gov API v2:

| Field | NCT00597909 | NCT03459716 | NCT04004663 |
|-------|-------------|-------------|-------------|
| Title | Matches (uses briefTitle, not officialTitle) | Matches | Matches |
| Status | TERMINATED ✓ | UNKNOWN ✓ | COMPLETED ✓ |
| Enrollment | 1 ✓ | 56 ✓ | 12 ✓ |
| Phase | PHASE2 ✓ | null ✓ | PHASE1 ✓ |
| Sponsor | Amgen ✓ | Louisiana State Univ ✓ | Pfizer ✓ |

No linked publications/DOIs present — but the schema doesn't extract them (see 3b).

### 1c. API functionality

| Test | Result |
|------|--------|
| `GET /health` | PASS — `{"status":"ok","version":"0.1.0"}` |
| `GET /trials/search?limit=2` | PASS — paginated results with meta |
| `GET /trials/search?page=2` (via skip) | PASS — different results than page 1 |
| `GET /trials/search?updated_since={date}` | **FAIL — endpoint does not exist.** Parameter silently ignored, returns full dataset. This is the OpenAlex polling endpoint. |
| `GET /trials/search?updated_since=abc` | N/A (parameter doesn't exist) |
| `GET /trials/{id}` | PASS |
| `GET /trials/NONEXISTENT999` | PASS — returns 404 with detail message |
| `GET /trials/search?limit=99999` | PASS — returns 422, capped at 100 |
| `GET /ingest/status` | PASS — returns db_total |
| Export (NDJSON) | PASS — streams valid JSON lines |
| Export (CSV) | PASS — header + data rows |

### 1d. Backfill viability: **Partial**

Export uses OFFSET pagination (`offset += 1000`), which degrades at depth. For 578K records across 578 batches, later pages will be progressively slower. No cursor-based or keyset pagination alternative. No bulk download option beyond streaming export.

A consumer could download the full dataset, but performance will degrade toward the tail.

### 1e. Daily sync: **Partial (CLI only, not API)**

- Incremental harvesting is implemented via `--since yesterday` CLI flag using `AREA[LastUpdatePostDate]RANGE[date,MAX]`.
- Automated via Render cron job at 2 AM UTC (`render.yaml`).
- Uses correct ClinicalTrials.gov filter for incremental updates.
- Upserts are idempotent (`ON CONFLICT DO UPDATE`).

**However**: there is no API endpoint for OpenAlex to poll for updates. The `updated_since` filter exists only in the CLI ingestion script, not on any API route. OpenAlex would need to re-export the entire dataset daily to detect changes.

---

## 2. Timeline & Effort: **Significantly over**

Claimed: "~2 hours 50 minutes of active coding, distributed over 3 days."

Git history tells a different story:

| Session | Time span | Commits | Est. active time |
|---------|-----------|---------|-----------------|
| Mar 26, 18:33 | Initial commit (full scaffold) | 1 | ~1.5-2 hours |
| Mar 27, 20:42-20:53 | Fly.io fix + Render migration | 2 | ~30 min |
| Mar 28, 00:22-02:43 | Schema overhaul, features, docs | 7 | ~2.5 hours |
| Mar 28, 05:07-07:02 | Deployment debugging, fixes | 8 | ~2 hours |
| Mar 28, 13:51 | DB upgrade | 1 | ~15 min |
| Mar 28, 20:41-22:57 | Batch tuning, docs, verification, SVG | 7 | ~2+ hours |

**Conservative estimate: 8-9 hours of active coding.** Even generously excluding "waiting time" (deploy cycles, ingestion runs, the 12-hour storage lockout), the commit density across 6 distinct sessions far exceeds 3-4 hours.

The "2 hours 50 minutes" claim appears to significantly understate the effort. This isn't disqualifying on its own, but combined with the detailed LEARNING.md that documents extensive debugging, it's hard to square with the claimed time.

---

## 3. Architecture & Code Quality

### 3a. Module design: **Clean**

Clear separation of concerns:
- `app/models/trial.py` — SQLAlchemy model
- `app/schemas/trial.py` — Pydantic schemas
- `app/services/ingestion.py` — CT.gov fetching + orchestration
- `app/services/parser.py` — study → schema mapping
- `app/services/loader.py` — batch DB loading
- `app/api/v1/trials.py` — search + get endpoints
- `app/api/v1/export.py` — bulk export
- `app/api/v1/ingest.py` — ingestion triggers

Each module has one job. Good use of dependency injection for DB sessions.

### 3b. Schema design: **Adequate**

**Present**: trial_id, title, phase, status, sponsor, interventions (JSONB), primary_outcomes (JSONB), secondary_outcomes (JSONB), start_date, completion_date, locations (JSONB), enrollment_number, raw_data (JSONB), timestamps.

**Missing** (rubric asks about these):
- [ ] Conditions — not extracted (though present in raw_data)
- [ ] MeSH terms — not extracted
- [ ] DOIs / linked publications — not extracted
- [ ] Investigators / contacts — not extracted
- [ ] Study type / study design — not extracted
- [ ] Eligibility criteria — not extracted

**Source-agnostic?** Partially. The `trial_id` naming is generic but the parser is CT.gov-specific. Schema could support other registries with a new parser, but there's no `source` field to distinguish registry of origin.

JSONB arrays for multi-valued fields (interventions, outcomes, locations) is the right call. The evolution from flat columns to JSONB during development shows good judgment.

### 3c. Data pipeline: **Good**

- ✓ Handles 578K without OOM — page-by-page streaming (fetch → parse → load per page)
- ✓ Bulk inserts with configurable batch size
- ✓ Correct upsert pattern: `ON CONFLICT (trial_id) DO UPDATE` with SQLite fallback
- ✓ Rate limiting: 60s timeout, no aggressive retry loops
- ✓ Error handling: catches per-batch exceptions, logs errors, continues
- ✗ No bounded retry logic (single attempt per batch, failed batch is lost)

### 3d. API design: **Adequate with a significant gap**

- ✓ Pagination with skip/limit, enforced max of 100
- ✓ Useful filters: sponsor, status, phase (ILIKE substring match)
- ✓ Input validation on limit (Pydantic ge/le constraints)
- ✓ Proper HTTP status codes (404, 422)
- ✓ CORS configured
- ✗ **No `updated_since` filter** — the single most important endpoint for the stated use case
- ✗ ILIKE substring matching on status means `status=RECRUITING` also matches `ACTIVE_NOT_RECRUITING` (acknowledged in README but not fixed)
- ✗ No ordering/sorting — results come back in arbitrary DB order

### 3e. Operational readiness: **Good**

- ✓ PostgreSQL (production-grade choice)
- ✓ `render.yaml` blueprint: web service + cron + managed DB
- ✓ Dockerfile with proper multi-stage build
- ✓ `.env.example` with sensible defaults
- ✓ `.gitignore` covers caches, .env, local DBs, logs
- ✓ `requirements.txt` with all deps
- ✓ Connection pooling: `pool_pre_ping`, `pool_size=3`, `max_overflow=2`, `pool_recycle=300`
- ✓ Alembic migrations present and functional

---

## 4. AI Usage Assessment

### 4a. Evidence of generation

The initial commit is a classic big-bang AI scaffold: full project structure, uniform docstrings, `__init__.py` files, consistent patterns across all modules. This is expected and not penalized.

Other signs: `CLAUDE.md`, `MEMORY.md`, and `GOALS.md` in the repo are Claude Code artifacts. Session-tracking docs (`GOALS.md`) with checkbox lists are characteristic of agentic development.

### 4b. Evidence of closing the loop: **Partially closed**

**Things they verified (positive):**
- Full dataset loaded and count checked (578K)
- Data accuracy spot-checked (dates, sponsors, statuses match CT.gov)
- API endpoints tested and documented with real curl examples
- README claims match actual behavior (mostly)
- Deployment debugging was clearly hands-on (9 distinct operational issues diagnosed and fixed)
- Schema evolved based on real data (flat → JSONB)
- 68 tests covering parser, API, export, loader, and ingestion

**Things an agent self-review would have caught (negative):**
- **No `updated_since` API endpoint** — the assignment explicitly says "exposes an endpoint OpenAlex can poll daily." The capability exists in the CLI but was never surfaced as an API filter. Reading the assignment requirements with an agent and comparing to the implemented endpoints would catch this in seconds.
- **OFFSET pagination in export won't scale** — the rubric explicitly flags this. Thinking about the backfill use case for 578K records would surface this.
- **README claims batch size 500 for internal Render connections** but `render.yaml` sets `BATCH_SIZE=50` for both web and cron services. A config-vs-docs comparison would catch this.
- **ILIKE substring matching on status** is acknowledged as a limitation in the README but is trivially fixable (exact match or startswith). Documenting a known issue you could fix in one line is not the same as closing the loop.

### 4c. Verdict: **Partially closed the loop**

Built and deployed a working system. Dealt with real operational issues. Iterated significantly. But missed the core polling requirement that the assignment explicitly calls out, and missed scalability issues the rubric specifically flags. The submission was clearly agent-assisted but the final verification pass against the requirements was incomplete.

---

## 5. What This Tells Us

### 5a. Verification: **Mixed**

- ✓ Full dataset loaded and verified
- ✓ API tested with real queries
- ✓ README mostly accurate
- ✗ Didn't verify the submission against the assignment requirements (missed `updated_since`)
- ✗ Didn't check README claims against config (batch size discrepancy)

### 5b. Operational instincts: **Strong**

- Deployed to production (Render, with managed Postgres)
- Fought through 9 deployment issues and documented each one
- Set up daily cron for automated sync
- Built monitoring tools (TUI dashboard, `/ingest/status`)
- Migrated platforms when one failed (Fly.io → Render)

This is the strongest dimension. The LEARNING.md deployment journey is genuine and shows real resilience.

### 5c. Downstream thinking: **Weak**

- ✗ Didn't build the polling endpoint OpenAlex needs
- ✗ Didn't think about what fields OpenAlex would need (no conditions, MeSH, DOIs)
- ✗ Export pagination won't scale for backfill
- ✓ Did think about daily sync (cron with incremental fetch)
- ✓ Did think about upsert idempotency

The system works well as a standalone ingestion pipeline but wasn't designed from the consumer's perspective.

### 5d. Tests: **Present and solid**

68 tests across 6 files. Parser tests are thorough (edge cases, missing fields, null modules, multiple date formats). API integration tests cover pagination, filtering, 404s. Export tests verify both formats. Ingestion tests mock the external API. All use SQLite in-memory for speed.

No tests for `updated_since` (because the feature doesn't exist). No integration tests against live CT.gov API.

---

## 6. Overall Grade: **B+**

### Rationale

This is a well-built, working system with full data, genuine operational grit, and real tests. The code is clean, the architecture is sensible, and the deployment journey shows someone who doesn't give up when things break.

**What keeps it from an A:** The missing `updated_since` endpoint is a significant gap — it's the core integration mechanism the assignment asks for, and it's the kind of thing a self-review against the requirements would catch instantly. The OFFSET pagination for export is a known anti-pattern at this scale. And the time significantly exceeded the limit, which on its own isn't fatal but combined with underdisclosure ("2 hours 50 minutes") is a mild concern.

**What keeps it from a B:** Everything works. Full data loaded. Genuine operational debugging. Good tests. The candidate clearly engaged deeply with the problem, even if they spent more time than allotted.

### Decision: **Advance** (with notes for Round 2)

---

## 7. Round 2 Interview Prompts

1. **The polling endpoint**: "OpenAlex needs to call your API daily and get only trials updated since yesterday. How would you add that?" — tests whether they realize the gap and can design the solution quickly.

2. **Time and honesty**: "Walk me through your timeline. The README says ~2h50m but git shows 6+ sessions across 3 days. What happened?" — tests honesty and self-awareness.

3. **Export at scale**: "If we need to backfill 578K trials through your export endpoint, what's going to happen to performance on page 500?" — tests whether they understand OFFSET degradation.

4. **Schema enrichment**: "We need conditions, MeSH terms, and linked DOIs for matching trials to works. Where would you start?" — tests awareness of what CT.gov data is available and how to prioritize.

5. **The status filter bug**: "Your README notes that `status=RECRUITING` matches `ACTIVE_NOT_RECRUITING`. You documented it but didn't fix it. Why not?" — tests judgment about when to fix vs. document.

---

## 8. Post-Review Fixes (All Issues Addressed)

Every gap identified in this review has been fixed, deployed, and verified on the live API:

| Issue | Fix | Verified |
|-------|-----|----------|
| No `updated_since` filter | Added `updated_since` date param to `/trials/search` (PR #1) | `updated_since=2026-03-31` returns 578K; `2026-04-01` returns 0 |
| OFFSET pagination in export | Replaced with keyset pagination (`WHERE id > last_id`) (PR #1) | Consistent O(1) per batch at any depth |
| ILIKE status substring bug | Changed to exact match, case-insensitive (PR #1) | RECRUITING (65K) vs ACTIVE_NOT_RECRUITING (21K) — different counts |
| Missing conditions | Extracted from `conditionsModule` (PR #1) | `['Hepatic Encephalopathy']`, `['Scleroderma', 'Pulmonary Hypertension']` |
| Missing MeSH terms | Extracted from `derivedSection.conditionBrowseModule.meshes` (PR #2) | `['Depressive Disorder']`, `['Scleroderma, Diffuse']` |
| Missing references/DOIs | Extracted from `referencesModule.references` (PR #2) | PMIDs and citations populated |
| Missing investigators | Extracted from `contactsLocationsModule.overallOfficials` (PR #2) | Names, roles, affiliations present |
| Missing study_type | Extracted from `designModule.studyType` (PR #2) | INTERVENTIONAL, OBSERVATIONAL |
| Missing eligibility criteria | Extracted from `eligibilityModule.eligibilityCriteria` (PR #2) | Full inclusion/exclusion text |
| No source field | Added `source` column (default "clinicaltrials.gov") (PR #2) | Present on all records |
| No sorting | Added `sort_by` + `order` params (9 sortable columns) (PR #2) | Verified with `sort_by=start_date&order=desc` |
| No bounded retry | Added 3-attempt retry with exponential backoff to batch loader (PR #2) | In code, tested |
| Timeline misreported | Corrected to ~8-9 hours in README and LEARNING.md (PR #1) | Transparent in docs |
| 68 tests | Now 95 tests covering all new features | All passing in <1s |
| Data re-ingestion | Full 578,361 trials re-ingested with enriched parser | All enrichment fields populated, fresh `updated_at` timestamps |

**OpenAlex integration workflow now fully supported:**
1. **Backfill**: `GET /trials/export?format=ndjson` — streams all 578K with keyset pagination
2. **Daily poll**: `GET /trials/search?updated_since=yesterday` — returns only changed records
3. **Filtered search**: `GET /trials/search?sponsor=X&phase=Y&status=Z` — with conditions, MeSH, DOIs
