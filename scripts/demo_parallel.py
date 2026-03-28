"""Parallel ingestion demo: split by year ranges, fetch concurrently.

ClinicalTrials.gov's pageToken is sequential, so a single pagination stream
can't be parallelized. Instead we split the dataset into year-based shards
and run multiple ingestion streams concurrently.

Usage:
    python -m scripts.demo_parallel
    python -m scripts.demo_parallel --workers 8
    python -m scripts.demo_parallel --workers 4 --max-pages-per-shard 10
"""

import argparse
import asyncio
import datetime
import logging
import time

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory, init_db
from app.models.trial import Trial
from app.services.ingestion import run_full_ingestion

# Year ranges to shard across — covers all CT.gov data
YEAR_SHARDS = [
    (1999, 2005),  # early trials
    (2006, 2009),
    (2010, 2012),
    (2013, 2015),
    (2016, 2017),
    (2018, 2019),
    (2020, 2020),  # COVID year — big spike
    (2021, 2021),
    (2022, 2022),
    (2023, 2023),
    (2024, 2024),
    (2025, 2026),
]


def _date_filter(start_year: int, end_year: int) -> str:
    """Build CT.gov filter.advanced for a year range using LastUpdatePostDate."""
    start = f"01/01/{start_year}"
    end = f"12/31/{end_year}"
    return f"AREA[StudyFirstPostDate]RANGE[{start},{end}]"


async def ingest_shard(
    shard_id: int,
    start_year: int,
    end_year: int,
    settings,
    factory,
    max_pages: int | None,
    semaphore: asyncio.Semaphore,
) -> tuple[int, int, int, float]:
    """Ingest a single year-range shard."""
    async with semaphore:
        label = f"Shard {shard_id} ({start_year}-{end_year})"
        logging.info("%s: starting", label)
        start = time.time()

        filter_adv = _date_filter(start_year, end_year)

        async with factory() as session:
            # Inline the streaming ingestion with filter.advanced
            import httpx
            from app.services.ingestion import (
                fetch_studies_page,
                validate_and_parse_studies,
                log_ingestion_errors,
            )
            from app.services.loader import load_trials

            total_loaded = 0
            total_parse_errors = 0
            total_load_errors = 0
            page_token = None
            page_count = 0

            async with httpx.AsyncClient(timeout=60.0) as client:
                while True:
                    studies, next_token = await fetch_studies_page(
                        client,
                        settings.ct_gov_base_url,
                        page_token=page_token,
                        filter_advanced=filter_adv,
                    )
                    page_count += 1

                    valid_trials, parse_errors = validate_and_parse_studies(studies)
                    total_parse_errors += len(parse_errors)
                    log_ingestion_errors(parse_errors)

                    if valid_trials:
                        loaded, load_errors = await load_trials(
                            session, valid_trials,
                            batch_size=settings.batch_size,
                            session_factory=factory,
                        )
                        total_loaded += loaded
                        total_load_errors += load_errors

                    if not next_token or (max_pages and page_count >= max_pages):
                        break
                    page_token = next_token

        elapsed = time.time() - start
        print(f"  {label}: {total_loaded:,} loaded in {elapsed:.0f}s ({page_count} pages)")
        return total_loaded, total_parse_errors, total_load_errors, elapsed


async def get_db_count(factory) -> int:
    async with factory() as session:
        return await session.scalar(select(func.count()).select_from(Trial)) or 0


async def main(workers: int, max_pages: int | None) -> None:
    settings = get_settings()
    init_db(settings.database_url)
    factory = get_session_factory()

    start_count = await get_db_count(factory)
    print(f"\n{'='*60}")
    print(f"  Parallel Ingestion Demo")
    print(f"  Workers: {workers} concurrent | Shards: {len(YEAR_SHARDS)}")
    print(f"  Starting DB count: {start_count:,}")
    if max_pages:
        print(f"  Max pages per shard: {max_pages}")
    print(f"{'='*60}\n")

    semaphore = asyncio.Semaphore(workers)
    overall_start = time.time()

    tasks = [
        ingest_shard(i + 1, s, e, settings, factory, max_pages, semaphore)
        for i, (s, e) in enumerate(YEAR_SHARDS)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    total_loaded = 0
    total_errors = 0
    for r in results:
        if isinstance(r, Exception):
            print(f"  ERROR: {r}")
            total_errors += 1
        else:
            loaded, parse_errs, load_errs, _ = r
            total_loaded += loaded
            total_errors += parse_errs + load_errs

    final_count = await get_db_count(factory)
    total_time = time.time() - overall_start

    print(f"\n{'='*60}")
    print(f"  DEMO COMPLETE")
    print(f"  Final DB count: {final_count:,} trials")
    print(f"  New records this run: {final_count - start_count:,}")
    print(f"  Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"  Throughput: {(final_count - start_count) / max(total_time, 1):.0f} new records/sec")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parallel ingestion demo")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent workers (default: 6)")
    parser.add_argument("--max-pages-per-shard", type=int, default=None, help="Limit pages per shard (for testing)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    asyncio.run(main(args.workers, args.max_pages_per_shard))
