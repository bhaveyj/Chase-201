"""Isolated browser-test server. Never imported by the deployable application.

Uses its own SQLite file and a fake token exchange; browser tests intercept Google's
authorization redirect. The production callback, cookies, state and claiming run unchanged.
"""

import asyncio
import os
import tempfile
from pathlib import Path

if os.environ.get("ENVIRONMENT") == "production":
    raise RuntimeError("The E2E test server must never run in production")
os.environ["ENVIRONMENT"] = "test"
os.environ["CATALOG_VERSION"] = "fictional-v4"
scratch = tempfile.TemporaryDirectory(prefix="chase201-e2e-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(Path(scratch.name) / 'e2e.db').as_posix()}"
os.environ["API_URL"] = "http://localhost:8001"
os.environ["GOOGLE_CLIENT_ID"] = "e2e-client"
os.environ["GOOGLE_CLIENT_SECRET"] = "e2e-secret"
os.environ["SECRET_KEY"] = "isolated-e2e-test-server-secret-key-only"

from chase201 import auth  # noqa: E402
from chase201.catalog import seed_fictional  # noqa: E402
from chase201.db import SessionFactory, engine  # noqa: E402
from chase201.main import app  # noqa: E402
from chase201.models import Base  # noqa: E402


async def exchange(code, attempt):
    if code != "e2e-google-code":
        raise ValueError("Invalid test authorization code")
    return {"sub": f"e2e-{attempt.guest_id}", "name": "Test Captain"}


async def prepare():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionFactory() as db, db.begin():
        await seed_fictional(db)
    await engine.dispose()


if __name__ == "__main__":
    import uvicorn

    auth.exchange_google = exchange
    asyncio.run(prepare())
    uvicorn.run(app, host="127.0.0.1", port=8001)
