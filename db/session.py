"""
Async SQLAlchemy session management.

Provides async database engine, session factory, and FastAPI dependency
for database access.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import Settings

logger = logging.getLogger(__name__)

# Global engine and session factory (initialized in init_db)
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings) -> AsyncEngine:
    """
    Initialize async database engine and session factory.

    Should be called once during application startup (in main.py lifespan).

    Args:
        settings: Application settings containing database configuration

    Returns:
        AsyncEngine: The initialized database engine

    Example:
        ```python
        # In main.py lifespan
        engine = init_db(settings)
        app.state.db_engine = engine
        ```
    """
    global _engine, _async_session_factory

    logger.info(
        "Initializing database connection",
        extra={
            "host": settings.postgres_host,
            "port": settings.postgres_port,
            "database": settings.postgres_db,
            "pool_size": settings.postgres_pool_size,
        },
    )

    # Create async engine with connection pooling
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.is_dev,  # Log SQL in development
        pool_size=settings.postgres_pool_size,
        max_overflow=settings.postgres_max_overflow,
        pool_timeout=settings.postgres_pool_timeout,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,  # Recycle connections after 1 hour
    )

    # Create session factory
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Don't expire objects after commit
        autoflush=False,  # Manual flush for better control
        autocommit=False,
    )

    logger.info("Database connection initialized successfully")
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.

    Automatically handles session lifecycle (commit/rollback/close).

    Yields:
        AsyncSession: Database session for the request

    Example:
        ```python
        @app.post("/chat")
        async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
            # Use db session
            conversation = await db.get(Conversation, conversation_id)
        ```
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() in application startup.")

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """
    Close database engine and cleanup connections.

    Should be called during application shutdown (in main.py lifespan).
    """
    global _engine

    if _engine is not None:
        logger.info("Closing database connection")
        await _engine.dispose()
        _engine = None
        logger.info("Database connection closed")


def get_engine() -> AsyncEngine:
    """
    Get the current database engine.

    Returns:
        AsyncEngine: The active database engine

    Raises:
        RuntimeError: If database is not initialized
    """
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() in application startup.")
    return _engine
