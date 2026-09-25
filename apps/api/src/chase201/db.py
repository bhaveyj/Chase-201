from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from chase201.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url, pool_pre_ping=True, connect_args=settings.database_connect_args
)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session, session.begin():
        yield session
