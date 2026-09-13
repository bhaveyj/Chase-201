import os

# Keep catalog tests independent of a developer's local catalog setting.
os.environ["CATALOG_VERSION"] = "fictional-v2"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from chase201.catalog import seed_fictional
from chase201.db import get_db
from chase201.main import app
from chase201.models import Base


@pytest.fixture
async def database(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    if url.startswith("postgresql") and not url.endswith("/chase201_test"):
        raise ValueError("TEST_DATABASE_URL must target the dedicated chase201_test database")
    engine = create_async_engine(url)
    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db, db.begin():
        await seed_fictional(db)

    async def override():
        async with factory() as db, db.begin():
            yield db

    app.dependency_overrides[get_db] = override
    yield factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def client(database):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        yield client
