"""Pytest configuration and shared fixtures.

Provides common fixtures and configuration for all test modules.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import JSON

# Patch JSONB before any models are imported
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

postgresql.JSONB = JSON

from config import Settings
from db.base import Base
from db.models import Message, Trip, User
from db.session import get_db
from main import create_app


@pytest.fixture(scope="session")
def test_settings():
    """Create test-specific settings."""
    return Settings(
        app_env="test",
        postgres_host="localhost",
        postgres_port=5432,
        postgres_user="postgres",
        postgres_password="postgres",
        postgres_db="travelroboto_test",
        log_level="ERROR",  # Reduce noise in tests
        mock_llm_responses=True,  # Don't hit real LLM APIs in tests
        ab_testing_enabled=False,  # Disable A/B testing in tests
    )


@pytest_asyncio.fixture
async def async_engine(test_settings):
    """Create an async database engine for testing.

    Uses a test database to avoid polluting production data.
    """
    engine = create_async_engine(
        f"postgresql+asyncpg://{test_settings.postgres_user}:{test_settings.postgres_password}@{test_settings.postgres_host}:{test_settings.postgres_port}/{test_settings.postgres_db}",
        echo=False,
        pool_pre_ping=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # Clean slate
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing.

    Each test gets a fresh session that rolls back on completion.
    """
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_client(async_engine, db_session, test_settings):
    """Create a FastAPI test client with database override."""
    app = create_app()
    app.state.settings = test_settings
    app.state.db_engine = async_engine

    # Override the get_db dependency to use our test session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# --- Test Data Factories ---


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "phone": "+1-555-0100",
        "home_city": "San Francisco, CA",
    }


@pytest.fixture
def sample_trip_data(sample_user_data):
    """Sample trip data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "name": "SF Fall Trip",
        "destination": "San Francisco, CA",
        "start_date": "2026-09-04",
        "end_date": "2026-10-05",
        "created_by_user_id": sample_user_data["id"],
    }


@pytest.fixture
def sample_trip_member_data(sample_user_data):
    """Sample trip member data for testing."""
    return {
        "user_id": sample_user_data["id"],
        "role": "traveler",
    }


@pytest.fixture
def sample_message_feedback_data():
    """Sample message feedback data for testing."""
    return {"feedback": "up"}


@pytest_asyncio.fixture
async def created_user(db_session: AsyncSession, sample_user_data):
    """Create a user in the database for testing."""
    user = User(
        id=uuid.UUID(sample_user_data["id"]),
        email=sample_user_data["email"],
        first_name=sample_user_data["first_name"],
        last_name=sample_user_data["last_name"],
        phone=sample_user_data["phone"],
        home_city=sample_user_data["home_city"],
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def created_trip(db_session: AsyncSession, created_user, sample_trip_data):
    """Create a trip in the database for testing."""
    trip = Trip(
        id=uuid.UUID(sample_trip_data["id"]),
        name=sample_trip_data["name"],
        destination=sample_trip_data["destination"],
        start_date=date.fromisoformat(sample_trip_data["start_date"]),
        end_date=date.fromisoformat(sample_trip_data["end_date"]),
        created_by_user_id=created_user.id,
        structured_data={},
        raw_extractions=[],
    )
    db_session.add(trip)
    await db_session.commit()
    await db_session.refresh(trip)
    return trip


@pytest_asyncio.fixture
async def created_message(db_session: AsyncSession, created_trip):
    """Create a message in the database for testing."""
    # First create a conversation for the message
    from db.models import Conversation

    conversation = Conversation(
        trip_id=created_trip.id,
        model_used="claude-sonnet-4",
        message_count=0,
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="Hello! How can I help you plan your trip?",
        timestamp=datetime.now(),
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)
    return message
