"""Progressive ingestion demo: load trials in 5K increments up to 500K.

Usage:
    python -m scripts.demo_progressive
"""

import asyncio
import logging
import time

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory, init_db
from app.models.trial import Trial
from app.services.ingestion import run_full_ingestion

STEP_SIZE = 5000  # records per step
PAGES_PER_STEP = STEP_SIZE // 1000  # 5 pages (1000 records/page)
TARGET = 500_000
MAX_STEPS = TARGET // STEP_SIZE  # 100 steps


async def get_db_count(factory) -> int:
    async with factory() as session:
        count = await session.scalar(select(func.count()).select_from(Trial))
        return count or 0


async def main() -> None:
    settings = get_settings()
    init_db(settings.database_url)
    factory = get_session_factory()

    start_count = await get_db_count(factory)
    print(f"\n{'='*60}")
    print(f"  Progressive Ingestion Demo")
    print(f"  Target: {TARGET:,} trials in {STEP_SIZE:,} increments")
    print(f"  Starting DB count: {start_count:,}")
    print(f"{'='*60}\n")

    cumulative_pages = 0
    overall_start = time.time()

    for step in range(1, MAX_STEPS + 1):
        cumulative_pages += PAGES_PER_STEP
        target_records = step * STEP_SIZE

        step_start = time.time()
        print(f"--- Step {step}: ingesting up to {target_records:,} trials ({cumulative_pages} pages) ---")

        async with factory() as session:
            loaded, parse_errors, load_errors = await run_full_ingestion(
                settings,
                session,
                max_pages=cumulative_pages,
                session_factory=factory,
            )

        db_count = await get_db_count(factory)
        elapsed = time.time() - step_start
        total_elapsed = time.time() - overall_start

        print(f"  Step {step} complete in {elapsed:.1f}s")
        print(f"  DB total: {db_count:,} trials")
        print(f"  This step: +{loaded:,} loaded, {parse_errors} parse errors, {load_errors} load errors")
        print(f"  Rate: {db_count / total_elapsed:.0f} records/sec overall")
        print(f"  Total elapsed: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
        print()

        if db_count >= TARGET:
            print(f"  Reached target of {TARGET:,}! Stopping.")
            break

    final_count = await get_db_count(factory)
    total_time = time.time() - overall_start
    print(f"\n{'='*60}")
    print(f"  DEMO COMPLETE")
    print(f"  Final DB count: {final_count:,} trials")
    print(f"  Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"  Average rate: {final_count / total_time:.0f} records/sec")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Quiet down httpx and httpcore
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    asyncio.run(main())
