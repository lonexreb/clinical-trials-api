#!/bin/sh
# Initial full load — run once to populate the database with all ~500K+ trials.
# Uses the parallel ingestion script with 6 concurrent workers.
#
# On Render: trigger this as a one-off job from the dashboard, or run manually:
#   render jobs create --service clinical-trials-ingest --command "sh scripts/initial_load.sh"
#
# Locally:
#   ./scripts/initial_load.sh

set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting parallel ingestion (6 workers, 12 year-range shards)..."
python -m scripts.demo_parallel --workers 6

echo "Initial load complete."
