import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from chase201.config import get_settings
from chase201.models import Base


def run_sync(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    settings = get_settings()
    url = settings.migration_database_url
    engine = create_async_engine(
        url, connect_args=settings.connect_args_for(url)
    )
    async with engine.connect() as connection:
        await connection.run_sync(run_sync)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=get_settings().migration_database_url, target_metadata=Base.metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
