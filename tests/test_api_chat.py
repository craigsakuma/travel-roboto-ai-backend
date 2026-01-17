"""Tests for chat API endpoint.

Tests the POST /api/chat endpoint for Travel Concierge agent.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import Settings
from db.base import Base
from db.models import Conversation, Message, User
from main import create_app


@pytest_asyncio.fixture
async def async_engine():
    """Create an in-memory async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def session(async_engine):
    """Create a database session for testing."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        app_env="test",
        mock_llm_responses=True,
        openai_api_key="test-openai-key",
        anthropic_api_key="test-anthropic-key",
        google_api_key="test-google-key",
        default_model_provider="anthropic",
        default_model_name="claude-3-5-sonnet-20241022",
        postgres_host="localhost",
        postgres_port=5432,
        postgres_db="test_db",
        postgres_user="test_user",
        postgres_password="test_password",
    )


@pytest.fixture
def mock_agent():
    """Create a mock TravelConciergeAgent."""
    agent = MagicMock()

    # Mock chat method
    async def mock_chat(user_message, conversation_history=None):
        return (
            "This is a test response from the agent.",
            {
                "tool_calls": [],
                "model_info": {
                    "provider": "anthropic",
                    "model": "claude-3-5-sonnet-20241022",
                },
                "tokens": {
                    "prompt": 150,
                    "completion": 75,
                    "total": 225,
                },
            },
        )

    agent.chat = AsyncMock(side_effect=mock_chat)

    return agent


class TestChatAPI:
    """Test chat API endpoint."""

    @pytest.mark.asyncio
    async def test_chat_new_conversation(self, async_engine, session):
        """Test creating a new conversation via chat endpoint."""
        # Create test user
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com")
        session.add(user)
        await session.commit()

        # Mock the agent and database dependencies
        with patch("api.chat.TravelConciergeAgent") as mock_agent_class, \
             patch("api.chat.get_llm_factory"), \
             patch("db.session._engine", async_engine):

            mock_agent = MagicMock()
            async def mock_chat(user_message, conversation_history=None):
                return (
                    "Test response",
                    {
                        "tool_calls": [],
                        "model_info": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"},
                        "tokens": {"prompt": 100, "completion": 50, "total": 150},
                    },
                )
            mock_agent.chat = AsyncMock(side_effect=mock_chat)
            mock_agent_class.return_value = mock_agent

            # Create app and test client
            app = create_app()
            app.state.db_engine = async_engine

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": "Hello, I need help planning my trip",
                        "user_id": str(user_id),
                        "trip_id": None,
                        "conversation_id": None,
                    },
                )

            # Verify response
            assert response.status_code == 200
            data = response.json()

            assert "message" in data
            assert "conversation_id" in data
            assert "timestamp" in data
            assert "model_used" in data
            assert "metadata" in data

            assert data["message"] == "Test response"
            assert "anthropic" in data["model_used"]

    @pytest.mark.asyncio
    async def test_chat_existing_conversation(self, async_engine, session):
        """Test continuing an existing conversation."""
        # Create test user and conversation
        user_id = uuid.uuid4()
        conversation_id = uuid.uuid4()

        user = User(id=user_id, email="test@example.com")
        conversation = Conversation(
            id=conversation_id,
            user_id=user_id,
            conversation_type="user_chat",
            next_turn_number=3,
        )
        message1 = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role="user",
            content="Previous user message",
            turn_number=1,
        )
        message2 = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role="assistant",
            content="Previous assistant response",
            turn_number=2,
        )

        session.add_all([user, conversation, message1, message2])
        await session.commit()

        with patch("api.chat.TravelConciergeAgent") as mock_agent_class, \
             patch("api.chat.get_llm_factory"), \
             patch("db.session._engine", async_engine):

            mock_agent = MagicMock()
            async def mock_chat(user_message, conversation_history=None):
                # Verify conversation history was passed
                assert conversation_history is not None
                assert len(conversation_history) == 2
                return (
                    "Continuing the conversation",
                    {
                        "tool_calls": [],
                        "model_info": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"},
                        "tokens": {"prompt": 200, "completion": 100, "total": 300},
                    },
                )
            mock_agent.chat = AsyncMock(side_effect=mock_chat)
            mock_agent_class.return_value = mock_agent

            app = create_app()
            app.state.db_engine = async_engine

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": "What were we talking about?",
                        "user_id": str(user_id),
                        "trip_id": None,
                        "conversation_id": str(conversation_id),
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["conversation_id"] == str(conversation_id)

    @pytest.mark.asyncio
    async def test_chat_invalid_conversation_id(self, async_engine, session):
        """Test chat with non-existent conversation ID."""
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com")
        session.add(user)
        await session.commit()

        with patch("db.session._engine", async_engine):
            app = create_app()
            app.state.db_engine = async_engine

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": "Test message",
                        "user_id": str(user_id),
                        "trip_id": None,
                        "conversation_id": str(uuid.uuid4()),  # Non-existent
                    },
                )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_chat_malformed_conversation_id(self, async_engine, session):
        """Test chat with malformed conversation ID."""
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com")
        session.add(user)
        await session.commit()

        with patch("db.session._engine", async_engine):
            app = create_app()
            app.state.db_engine = async_engine

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": "Test message",
                        "user_id": str(user_id),
                        "trip_id": None,
                        "conversation_id": "not-a-uuid",
                    },
                )

            assert response.status_code == 400
            assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_chat_messages_saved_to_database(self, async_engine, session):
        """Test that messages are saved to database."""
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com")
        session.add(user)
        await session.commit()

        with patch("api.chat.TravelConciergeAgent") as mock_agent_class, \
             patch("api.chat.get_llm_factory"), \
             patch("db.session._engine", async_engine):

            mock_agent = MagicMock()
            async def mock_chat(user_message, conversation_history=None):
                return (
                    "Agent response",
                    {
                        "tool_calls": [],
                        "model_info": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"},
                        "tokens": {"prompt": 100, "completion": 50, "total": 150},
                    },
                )
            mock_agent.chat = AsyncMock(side_effect=mock_chat)
            mock_agent_class.return_value = mock_agent

            app = create_app()
            app.state.db_engine = async_engine

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": "Test user message",
                        "user_id": str(user_id),
                        "trip_id": None,
                        "conversation_id": None,
                    },
                )

            assert response.status_code == 200

            # Verify messages were saved
            from sqlalchemy import select
            result = await session.execute(select(Message))
            messages = result.scalars().all()

            # Should have 2 messages: user + assistant
            assert len(messages) == 2
            assert messages[0].role == "user"
            assert messages[0].content == "Test user message"
            assert messages[1].role == "assistant"
            assert messages[1].content == "Agent response"

    @pytest.mark.asyncio
    async def test_chat_metadata_in_response(self, async_engine, session):
        """Test that response includes metadata."""
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com")
        session.add(user)
        await session.commit()

        with patch("api.chat.TravelConciergeAgent") as mock_agent_class, \
             patch("api.chat.get_llm_factory"), \
             patch("db.session._engine", async_engine):

            mock_agent = MagicMock()
            async def mock_chat(user_message, conversation_history=None):
                return (
                    "Response",
                    {
                        "tool_calls": [{"name": "get_trip_details", "args": {"trip_id": "123"}}],
                        "model_info": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"},
                        "tokens": {"prompt": 250, "completion": 125, "total": 375},
                    },
                )
            mock_agent.chat = AsyncMock(side_effect=mock_chat)
            mock_agent_class.return_value = mock_agent

            app = create_app()
            app.state.db_engine = async_engine

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": "Test",
                        "user_id": str(user_id),
                        "trip_id": None,
                        "conversation_id": None,
                    },
                )

            data = response.json()
            assert "metadata" in data
            assert "tokens" in data["metadata"]
            assert "tool_calls" in data["metadata"]
            assert data["metadata"]["tokens"]["prompt"] == 250
            assert data["metadata"]["tokens"]["completion"] == 125
            assert len(data["metadata"]["tool_calls"]) == 1

    @pytest.mark.asyncio
    async def test_chat_with_trip_id(self, async_engine, session):
        """Test chat with associated trip ID."""
        user_id = uuid.uuid4()
        trip_id = uuid.uuid4()

        user = User(id=user_id, email="test@example.com")
        session.add(user)
        await session.commit()

        with patch("api.chat.TravelConciergeAgent") as mock_agent_class, \
             patch("api.chat.get_llm_factory"), \
             patch("db.session._engine", async_engine):

            mock_agent = MagicMock()
            async def mock_chat(user_message, conversation_history=None):
                return (
                    "Trip-related response",
                    {
                        "tool_calls": [],
                        "model_info": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"},
                        "tokens": {"prompt": 100, "completion": 50, "total": 150},
                    },
                )
            mock_agent.chat = AsyncMock(side_effect=mock_chat)
            mock_agent_class.return_value = mock_agent

            app = create_app()
            app.state.db_engine = async_engine

            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/chat",
                    json={
                        "message": "Tell me about my Tokyo trip",
                        "user_id": str(user_id),
                        "trip_id": str(trip_id),
                        "conversation_id": None,
                    },
                )

            assert response.status_code == 200

            # Verify conversation was created with trip_id
            from sqlalchemy import select
            result = await session.execute(select(Conversation))
            conversations = result.scalars().all()

            assert len(conversations) == 1
            assert conversations[0].trip_id == trip_id
