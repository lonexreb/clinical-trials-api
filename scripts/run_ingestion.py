"""CLI entry point for running the ingestion pipeline.

Usage:
    # Full ingestion
    python -m scripts.run_ingestion

    # Daily incremental update (records updated since yesterday)
    python -m scripts.run_ingestion --since yesterday

    # Incremental from a specific date
    python -m scripts.run_ingestion --since 2024-01-15

    # With search filter and page limit (for development)
    python -m scripts.run_ingestion --query cancer --max-pages 5
"""

import argparse
import asyncio
import datetime
import logging

from app.core.config import get_settings
from app.db.session import get_session_factory, init_db
from app.services.ingestion import run_full_ingestion


def _parse_since(value: str) -> datetime.date:
    """Parse --since argument: 'yesterday', 'today', or ISO date."""
    if value == "yesterday":
        return datetime.date.today() - datetime.timedelta(days=1)
    if value == "today":
        return datetime.date.today()
    return datetime.date.fromisoformat(value)


async def main(query: str | None, max_pages: int | None, since: datetime.date | None) -> None:
    settings = get_settings()
    init_db(settings.database_url)
    factory = get_session_factory()

    async with factory() as session:
        loaded, parse_errors, load_errors = await run_full_ingestion(
            settings,
            session,
            query_term=query,
            max_pages=max_pages,
            since_date=since,
            session_factory=factory,
        )
        print("\nIngestion complete:")
        print(f"  Loaded:       {loaded}")
        print(f"  Parse errors: {parse_errors}")
        print(f"  Load errors:  {load_errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run clinical trials ingestion")
    parser.add_argument("--query", default=None, help="Search term (e.g., 'cancer')")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit pages fetched (for dev/testing)")
    parser.add_argument(
        "--since",
        default=None,
        help="Only fetch trials updated since this date (YYYY-MM-DD, 'yesterday', or 'today')",
    )
    args = parser.parse_args()

    since_date = _parse_since(args.since) if args.since else None

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main(args.query, args.max_pages, since_date))
