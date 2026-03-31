# Test Plan — Clinical Trials ETL Pipeline

> Run all tests: `pytest tests/ -v --tb=short`
> Run with coverage: `pytest tests/ -v --cov=app --cov-report=term-missing`

## Test Summary

| Suite | File | Tests | Status |
|-------|------|-------|--------|
| Health | `tests/test_health.py` | 2 | Pass |
| Parser (dates + studies + enrichment) | `tests/test_parser.py` | 47 | Pass |
| Loader | `tests/test_loader.py` | 6 | Pass |
| Ingestion | `tests/test_ingestion.py` | 8 | Pass |
| Trials API (search + filters + sorting) | `tests/test_trials_api.py` | 24 | Pass |
| Export (NDJSON + CSV) | `tests/test_export.py` | 8 | Pass |
| **Total** | | **95** | **All Pass** |

---

## Unit Tests (no external dependencies)

### Date Parser (`tests/test_parser.py::TestParseDate`)

| Test | Input | Expected | Verifies |
|------|-------|----------|----------|
| `test_iso_full_date` | `"2018-11-29"` | `date(2018,11,29)` | ISO 8601 |
| `test_year_month` | `"2015-10"` | `date(2015,10,1)` | YYYY-MM format |
| `test_month_year_text` | `"January 2024"` | `date(2024,1,1)` | Text month+year |
| `test_month_day_year_text` | `"January 15, 2024"` | `date(2024,1,15)` | Full text date |
| `test_none_input` | `None` | `None` | Null handling |
| `test_empty_string` | `""` | `None` | Empty string |
| `test_whitespace_only` | `"   "` | `None` | Whitespace |
| `test_invalid_string` | `"not a date"` | `None` | Garbage input |
| `test_iso_with_whitespace` | `"  2023-06-01  "` | `date(2023,6,1)` | Trimming |
| `test_various_months` | `"March 2023"` | `date(2023,3,1)` | Multiple months |
| `test_full_text_various` | `"December 31, 2020"` | `date(2020,12,31)` | Multiple months |

### Study Parser (`tests/test_parser.py::TestParseStudy`)

| Test | Scenario | Verifies |
|------|----------|----------|
| `test_complete_study` | All fields populated | Full field mapping |
| `test_interventions_full_array` | 2 interventions | JSONB array stores all items |
| `test_primary_outcomes_full_array` | 1 primary outcome | JSONB array for outcomes |
| `test_secondary_outcomes_full_array` | 2 secondary outcomes | Secondary outcomes parsed |
| `test_locations_full_array` | 2 locations | JSONB array for locations |
| `test_missing_interventions_module` | No armsInterventionsModule | Returns None |
| `test_missing_outcomes_module` | No outcomesModule | primary + secondary both None |
| `test_missing_locations_module` | No contactsLocationsModule | Returns None |
| `test_empty_phases_list` | `phases: []` | Empty array → None |
| `test_missing_enrollment` | No enrollmentInfo | Returns None |
| `test_missing_date_structs` | No date structs | Null dates |
| `test_null_modules` | Modules set to `None` | None vs missing |
| `test_raw_data_preserved` | Full study | raw_data identity |
| `test_empty_study` | `{}` | Defaults for missing data |
| `test_empty_interventions_list` | `interventions: []` | Empty array → None |
| `test_empty_primary_outcomes_list` | `primaryOutcomes: []` | Empty array → None |
| `test_empty_secondary_outcomes_list` | `secondaryOutcomes: []` | Empty array → None |
| `test_year_month_date_format` | Mixed date formats | YYYY-MM + text |

### Health Endpoint (`tests/test_health.py`)

| Test | Verifies |
|------|----------|
| `test_health_returns_200` | Returns `{"status":"ok","version":"0.1.0"}` |
| `test_health_no_db_dependency` | Works without DB initialization |

---

## Integration Tests (SQLite in-memory via aiosqlite)

### Loader (`tests/test_loader.py`)

| Test | Scenario | Verifies |
|------|----------|----------|
| `test_insert_new_trials` | Insert 2 new records | Basic insert |
| `test_upsert_existing_trial` | Insert then update same trial_id | Upsert behavior |
| `test_batch_size_respected` | 15 trials with batch_size=5 | Batching works |
| `test_empty_list` | Empty input | Returns 0 |
| `test_load_trials_returns_counts` | 3 trials | Return tuple (loaded, errors) |
| `test_jsonb_fields_persisted` | JSONB arrays in/out | interventions, outcomes, locations stored correctly |

### Ingestion (`tests/test_ingestion.py`)

| Test | Scenario | Verifies |
|------|----------|----------|
| `test_fetch_studies_page_returns_studies_and_token` | Mock CT.gov response | Parses studies + nextPageToken |
| `test_fetch_studies_page_no_next_token_on_last_page` | Last page | Returns None token |
| `test_fetch_studies_page_passes_params` | Query params | pageSize, pageToken, query.term, format |
| `test_fetch_studies_page_passes_filter_advanced` | Incremental filter | `filter.advanced` with `LastUpdatePostDate` |
| `test_fetch_studies_page_raises_on_http_error` | 500 response | Raises HTTPStatusError |
| `test_validate_and_parse_valid_studies` | Valid studies | All parse successfully |
| `test_validate_and_parse_preserves_jsonb_arrays` | JSONB fields | interventions, outcomes, locations preserved |
| `test_validate_and_parse_captures_errors` | Defensive parsing | Errors captured |

### Trials API (`tests/test_trials_api.py`)

| Test | Scenario | Verifies |
|------|----------|----------|
| `test_search_trials_empty_db` | No data | Returns empty list + meta |
| `test_search_trials_returns_data` | 5 seeded trials | Returns all records |
| `test_search_trials_pagination` | `?skip=0&limit=2` | Pagination + has_more |
| `test_search_trials_skip_offset` | `?skip=3&limit=50` | Offset works |
| `test_search_trials_limit_max_100` | `?limit=200` | Returns 422 |
| `test_filter_by_sponsor` | `?sponsor=pfizer` | Case-insensitive ILIKE |
| `test_filter_by_status` | `?status=completed` | Status filter |
| `test_filter_by_phase` | `?phase=phase3` | Phase filter |
| `test_combined_filters` | `?sponsor=pfizer&status=recruiting` | Multiple filters |
| `test_combined_filters_with_phase` | `?sponsor=pfizer&phase=phase1` | Three-way filter |
| `test_get_trial_by_id` | `/trials/NCT00000001` | Returns single trial |
| `test_get_trial_not_found` | `/trials/NCT_INVALID` | 404 with detail |
| `test_pagination_meta_structure` | Pagination response | Meta has all fields |
| `test_response_includes_jsonb_fields` | JSONB arrays in response | interventions, outcomes, locations present |
| `test_response_null_jsonb_fields` | Null JSONB fields | None values handled |

### Export (`tests/test_export.py`)

| Test | Scenario | Verifies |
|------|----------|----------|
| `test_export_ndjson_format` | 5 seeded trials | Valid JSON per line, includes JSONB fields |
| `test_export_ndjson_content_type` | Content-Type header | application/x-ndjson |
| `test_export_ndjson_empty_db` | No data | Empty response |
| `test_export_csv_format` | 5 seeded trials | Header + 5 data rows |
| `test_export_csv_content_type` | Content-Type header | text/csv |
| `test_export_csv_header_fields` | CSV header | Contains all fields including JSONB columns |
| `test_export_invalid_format` | `?format=xml` | Returns 422 |
| `test_export_default_format_is_ndjson` | No format param | Defaults to NDJSON |

---

## E2E Verification Checklist (manual, against running stack)

Run these after `docker-compose up` or against deployed URL:

- [x] `curl localhost:8000/health` returns `{"status":"ok","version":"0.1.0"}`
- [x] `curl localhost:8000/trials/search?limit=5` returns 5 trials with meta
- [x] `curl localhost:8000/trials/search?sponsor=pfizer` returns Pfizer trials
- [x] `curl localhost:8000/trials/search?phase=phase3` returns Phase 3 trials
- [x] `curl localhost:8000/trials/NCT<valid-id>` returns single trial with JSONB arrays
- [x] `curl localhost:8000/trials/INVALID` returns 404
- [x] `curl localhost:8000/trials/export?format=ndjson | head -3` returns 3 JSON lines
- [x] `curl localhost:8000/trials/export?format=csv | head -3` returns header + 2 rows
- [x] `localhost:8000/docs` shows Swagger UI with all endpoints
- [x] `docker build -t clinical-trials-api .` builds successfully
- [x] `docker-compose up` runs full stack (API + DB)
- [x] `python -m scripts.run_ingestion --max-pages 1` ingests real data
- [x] `python -m scripts.run_ingestion --since yesterday` incremental update works
- [x] Ingested records appear in API response
- [x] 578,109 unique trials verified (0 duplicates)

---

## GOALS.md Verification Map

| Goal | Test(s) That Verify It |
|------|----------------------|
| S1: /health returns 200 | `test_health_returns_200`, `test_health_no_db_dependency` |
| S1: Parser maps CT.gov JSON | `TestParseStudy::test_complete_study`, `test_interventions_full_array`, `test_secondary_outcomes_full_array`, `test_locations_full_array` |
| S2: Date parser handles formats | `TestParseDate` (11 tests) |
| S2: Nullable fields handled | `test_missing_*`, `test_null_modules`, `test_empty_*` |
| S2: Loader upserts correctly | `test_insert_new_trials`, `test_upsert_existing_trial` |
| S2: Batch size max 500 | `test_batch_size_respected` |
| S2: JSONB fields persisted | `test_jsonb_fields_persisted` |
| S2: Validation errors logged | `test_validate_and_parse_captures_errors` |
| S3: Paginated trial search | `test_search_trials_pagination`, `test_search_trials_skip_offset` |
| S3: Filter by sponsor | `test_filter_by_sponsor` |
| S3: Filter by status | `test_filter_by_status` |
| S3: Filter by phase | `test_filter_by_phase`, `test_combined_filters_with_phase` |
| S3: Single trial by ID | `test_get_trial_by_id` |
| S3: 404 for missing trial | `test_get_trial_not_found` |
| S3: NDJSON export | `test_export_ndjson_format` |
| S3: CSV export | `test_export_csv_format` |
| S3: limit max 100 | `test_search_trials_limit_max_100` |
| S3: JSONB fields in response | `test_response_includes_jsonb_fields`, `test_response_null_jsonb_fields` |
| Incremental ingestion | `test_fetch_studies_page_passes_filter_advanced` |
| S4: Docker builds | E2E checklist |
