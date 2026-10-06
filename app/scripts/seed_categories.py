import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.repositories.category_repository import (
    ALL_SYSTEM_CATEGORIES,
    CategoryRepository,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed_categories")


async def seed_default_categories(session: AsyncSession | None = None) -> tuple[int, int]:
    """
    Idempotent seeding function for default system categories.
    Can be called directly from code or CLI.
    Returns (created_count, existing_count).
    """
    if session is not None:
        created, existing = await CategoryRepository.seed_system_default_categories(session)
        await session.commit()
        return created, existing

    async with AsyncSessionLocal() as new_session:
        created, existing = await CategoryRepository.seed_system_default_categories(new_session)
        await new_session.commit()
        return created, existing


async def run_seed() -> None:
    """Entry point for command line execution."""
    logger.info("Starting database category seeding...")
    try:
        created, existing = await seed_default_categories()
        total_target = len(ALL_SYSTEM_CATEGORIES)
        logger.info(
            f"Category seeding complete: {created} inserted, {existing} updated/verified "
            f"({created + existing}/{total_target} categories active)."
        )
    except Exception as e:
        logger.error(f"Error during category seeding: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_seed())
