from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.AppConfig import AppConfig


class Base(DeclarativeBase):
    pass


class PostgresManager:

    engine = create_async_engine(AppConfig.POSTGRES_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    @classmethod
    async def getSession(cls) -> AsyncGenerator[AsyncSession, None]:
        """Yields an asynchronous PostgreSQL database session per request and manages its transaction.

        Yields:
            AsyncGenerator[AsyncSession, None]: Active SQLAlchemy async session.
        """
        async with cls.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @classmethod
    async def initModels(cls) -> None:
        """Creates all registered SQLAlchemy tables in PostgreSQL if they do not exist."""
        async with cls.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @classmethod
    async def close(cls) -> None:
        """Disposes the PostgreSQL connection pool."""
        await cls.engine.dispose()
