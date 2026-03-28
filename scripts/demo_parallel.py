"""Parallel ingestion demo: split by year ranges, fetch concurrently.

ClinicalTrials.gov's pageToken is sequential, so a single pagination stream
can't be parallelized. Instead we split the dataset into year-based shards
and run multiple ingestion streams concurrently.

Usage:
    python -m scripts.demo_parallel
    python -m scripts.demo_parallel --workers 4
    python -m scripts.demo_parallel --workers 4 --max-pages-per-shard 10
"""

import argparse
import asyncio
import logging
import ssl as _ssl
import time

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.trial import Trial
from app.services.ingestion import (
    fetch_studies_page,
    validate_and_parse_studies,
    log_ingestion_errors,
)
from app.services.loader import load_trials

# Year ranges to shard across — covers all CT.gov data
YEAR_SHARDS = [
    (1999, 2005),
    (2006, 2009),
    (2010, 2012),
    (2013, 2015),
    (2016, 2017),
    (2018, 2019),
    (2020, 2020),
    (2021, 2021),
    (2022, 2022),
    (2023, 2023),
    (2024, 2024),
    (2025, 2026),
]


def _make_engine(database_url: str):
    """Create a fresh async engine with SSL if needed and aggressive pool recycling."""
    connect_args: dict = {}
    if "render.com" in database_url:
        ssl_ctx = _ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = _ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=120,
        connect_args=connect_args,
    )


def _date_filter(start_year: int, end_year: int) -> str:
    start = f"01/01/{start_year}"
    end = f"12/31/{end_year}"
    return f"AREA[StudyFirstPostDate]RANGE[{start},{end}]"


async def ingest_shard(
    shard_id: int,
    start_year: int,
    end_year: int,
    settings,
    database_url: str,
    max_pages: int | None,
    semaphore: asyncio.Semaphore,
) -> tuple[int, int, int, float]:
    """Ingest a single year-range shard with its own DB engine."""
    async with semaphore:
        label = f"Shard {shard_id} ({start_year}-{end_year})"
        logging.info("%s: starting", label)
        start = time.time()

        # Each shard gets its own engine — no shared connection pool contention
        engine = _make_engine(database_url)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        filter_adv = _date_filter(start_year, end_year)
        total_loaded = 0
        total_parse_errors = 0
        total_load_errors = 0
        page_token = None
        page_count = 0

        try:
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
                        async with factory() as session:
                            loaded, load_errors = await load_trials(
                                session, valid_trials,
                                batch_size=settings.batch_size,
                                session_factory=factory,
                            )
                            total_loaded += loaded
                            total_load_errors += load_errors

                    logging.info(
                        "%s page %d: +%d loaded (total: %d)",
                        label, page_count, len(valid_trials), total_loaded,
                    )

                    if not next_token or (max_pages and page_count >= max_pages):
                        break
                    page_token = next_token
        finally:
            await engine.dispose()

        elapsed = time.time() - start
        print(f"  {label}: {total_loaded:,} loaded in {elapsed:.0f}s ({page_count} pages)")
        return total_loaded, total_parse_errors, total_load_errors, elapsed


async def main(workers: int, max_pages: int | None) -> None:
    settings = get_settings()
    database_url = settings.database_url

    # Quick count check with a temporary engine
    engine = _make_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        start_count = await session.scalar(select(func.count()).select_from(Trial)) or 0
    await engine.dispose()

    print(f"\n{'='*60}")
    print(f"  Parallel Ingestion Demo")
    print(f"  Workers: {workers} concurrent | Shards: {len(YEAR_SHARDS)}")
    print(f"  Batch size: {settings.batch_size}")
    print(f"  Starting DB count: {start_count:,}")
    if max_pages:
        print(f"  Max pages per shard: {max_pages}")
    print(f"{'='*60}\n")

    semaphore = asyncio.Semaphore(workers)
    overall_start = time.time()

    tasks = [
        ingest_shard(i + 1, s, e, settings, database_url, max_pages, semaphore)
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

    # Final count
    engine = _make_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        final_count = await session.scalar(select(func.count()).select_from(Trial)) or 0
    await engine.dispose()

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
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers (default: 4)")
    parser.add_argument("--max-pages-per-shard", type=int, default=None, help="Limit pages per shard (for testing)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    asyncio.run(main(args.workers, args.max_pages_per_shard))
