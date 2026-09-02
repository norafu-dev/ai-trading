import os

import pytest
from sqlalchemy import text

from apps.api.app.database import build_engine


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to test the configured PostgreSQL instance",
)
async def test_postgresql_connection() -> None:
    engine = build_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT 1")) == 1
    finally:
        await engine.dispose()
