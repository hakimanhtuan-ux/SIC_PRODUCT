import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_using_postgres: bool = False


def is_postgres_active() -> bool:
    return _using_postgres


async def init_db() -> None:
    """Initialize PostgreSQL + pgvector, or fall back to local SQLite if configured."""
    global _engine, _session_factory, _using_postgres

    from app.models import entities  # noqa: F401 - register ORM models

    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql"):
        try:
            pg_engine = create_async_engine(
                db_url,
                echo=False,
                pool_pre_ping=True,
                connect_args={"timeout": 1.5},
            )

            async def _init_pg() -> None:
                async with pg_engine.begin() as conn:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    await conn.run_sync(Base.metadata.create_all)

            await asyncio.wait_for(_init_pg(), timeout=2.0)
            _engine = pg_engine
            _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
            _using_postgres = True
            logger.info("Connected to PostgreSQL with pgvector enabled.")
            return
        except Exception as exc:
            if not settings.ALLOW_SQLITE_FALLBACK:
                raise
            logger.warning(
                "PostgreSQL unavailable (%s). Falling back to local SQLite database.",
                exc,
            )

    sqlite_path = settings.STORAGE_DIR / "truecheck_local.db"
    sqlite_url = f"sqlite+aiosqlite:///{sqlite_path.as_posix()}"
    _engine = create_async_engine(sqlite_url, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    _using_postgres = False
    logger.info("Initialized local SQLite fallback at %s", sqlite_path)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        await init_db()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session

