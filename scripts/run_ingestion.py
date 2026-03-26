"""CLI entry point for running the ingestion pipeline.

Usage:
    python -m scripts.run_ingestion --query cancer --max-pages 5
"""

import argparse
import asyncio
import logging

from app.core.config import get_settings
from app.db.session import get_session_factory, init_db
from app.services.ingestion import run_full_ingestion


async def main(query: str | None, max_pages: int | None) -> None:
    settings = get_settings()
    init_db(settings.database_url)
    factory = get_session_factory()

    async with factory() as session:
        loaded, parse_errors, load_errors = await run_full_ingestion(
            settings, session, query_term=query, max_pages=max_pages
        )
        print("\nIngestion complete:")
        print(f"  Loaded:       {loaded}")
        print(f"  Parse errors: {parse_errors}")
        print(f"  Load errors:  {load_errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run clinical trials ingestion")
    parser.add_argument("--query", default=None, help="Search term (e.g., 'cancer')")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit pages fetched (for dev/testing)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main(args.query, args.max_pages))
