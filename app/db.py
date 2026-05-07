from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.db_models import Base


def create_session_factory(
    database_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    return engine, session_factory


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_db(engine: AsyncEngine) -> None:
    await engine.dispose()
