from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def dispose_engine() -> None:
    await engine.dispose()
