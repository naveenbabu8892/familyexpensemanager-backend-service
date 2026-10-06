import os
from collections.abc import AsyncGenerator

# Configure tests to strictly use the isolated test database
os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "family_expense_manager_test")
os.environ["ENVIRONMENT"] = "testing"
os.environ.pop("DATABASE_URL", None)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
get_settings.cache_clear()

from app.core.database import AsyncSessionLocal, engine
from app.main import app
from app.scripts.seed_categories import seed_default_categories


@pytest.fixture(autouse=True)
async def setup_and_clean_database():
    """Ensure test database has default categories seeded, and clean after each test."""
    async with AsyncSessionLocal() as session:
        await seed_default_categories(session)
    yield
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE TABLE refresh_tokens, expenses, incomes, budgets, "
                    "family_invitations, family_members, categories, families, users CASCADE;"
                )
            )
    except Exception:
        pass


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client using httpx ASGITransport."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
