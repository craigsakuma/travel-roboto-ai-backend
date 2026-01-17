"""Integration tests for PostgreSQL database layer.

Tests repository pattern, models, and database operations using
an in-memory SQLite database for fast, isolated testing.
"""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.repositories import ConversationRepository, MessageRepository


@pytest_asyncio.fixture
async def async_engine():
    """Create an in-memory async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
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


@pytest_asyncio.fixture
async def conversation_repo(session):
    """Create a ConversationRepository instance."""
    return ConversationRepository(session)


@pytest_asyncio.fixture
async def message_repo(session):
    """Create a MessageRepository instance."""
    return MessageRepository(session)


class TestConversationRepository:
    """Test ConversationRepository operations."""

    @pytest.mark.asyncio
    async def test_create_conversation(self, conversation_repo, session):
        """Test creating a new conversation."""
        conversation = await conversation_repo.create(
            user_id="user123",
            model_used="claude-sonnet-4",
            trip_id="trip456",
            ab_test_variant="variant_a",
        )

        assert conversation.id is not None
        assert conversation.user_id == "user123"
        assert conversation.model_used == "claude-sonnet-4"
        assert conversation.trip_id == "trip456"
        assert conversation.ab_test_variant == "variant_a"
        assert conversation.message_count == 0

    @pytest.mark.asyncio
    async def test_get_by_id(self, conversation_repo, session):
        """Test retrieving a conversation by ID."""
        # Create a conversation
        created = await conversation_repo.create(
            user_id="user123",
            model_used="gpt-4",
        )
        await session.commit()

        # Retrieve it
        retrieved = await conversation_repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.user_id == "user123"
        assert retrieved.model_used == "gpt-4"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, conversation_repo):
        """Test retrieving a non-existent conversation."""
        result = await conversation_repo.get_by_id(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_user(self, conversation_repo, session):
        """Test retrieving conversations by user ID."""
        # Create multiple conversations for the same user
        await conversation_repo.create(user_id="user123", model_used="model1")
        await conversation_repo.create(user_id="user123", model_used="model2")
        await conversation_repo.create(user_id="user456", model_used="model3")
        await session.commit()

        # Get conversations for user123
        conversations = await conversation_repo.get_by_user("user123")

        assert len(conversations) == 2
        assert all(c.user_id == "user123" for c in conversations)

    @pytest.mark.asyncio
    async def test_get_by_user_with_pagination(self, conversation_repo, session):
        """Test pagination when retrieving conversations."""
        # Create multiple conversations
        for i in range(5):
            await conversation_repo.create(user_id="user123", model_used=f"model{i}")
        await session.commit()

        # Get first 2
        page1 = await conversation_repo.get_by_user("user123", limit=2, offset=0)
        assert len(page1) == 2

        # Get next 2
        page2 = await conversation_repo.get_by_user("user123", limit=2, offset=2)
        assert len(page2) == 2

        # Ensure they're different conversations
        assert page1[0].id != page2[0].id

    @pytest.mark.asyncio
    async def test_get_by_trip(self, conversation_repo, session):
        """Test retrieving conversations by trip ID."""
        # Create conversations for different trips
        await conversation_repo.create(
            user_id="user1", model_used="model1", trip_id="trip1"
        )
        await conversation_repo.create(
            user_id="user2", model_used="model2", trip_id="trip1"
        )
        await conversation_repo.create(
            user_id="user3", model_used="model3", trip_id="trip2"
        )
        await session.commit()

        # Get conversations for trip1
        conversations = await conversation_repo.get_by_trip("trip1")

        assert len(conversations) == 2
        assert all(c.trip_id == "trip1" for c in conversations)

    @pytest.mark.asyncio
    async def test_update_message_count(self, conversation_repo, session):
        """Test updating message count."""
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )
        await session.commit()

        assert conversation.message_count == 0

        # Increment by 1
        await conversation_repo.update_message_count(conversation.id, increment=1)
        await session.commit()

        updated = await conversation_repo.get_by_id(conversation.id)
        assert updated.message_count == 1

        # Increment by 3 more
        await conversation_repo.update_message_count(conversation.id, increment=3)
        await session.commit()

        updated = await conversation_repo.get_by_id(conversation.id)
        assert updated.message_count == 4

    @pytest.mark.asyncio
    async def test_delete_conversation(self, conversation_repo, session):
        """Test deleting a conversation."""
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )
        await session.commit()

        conversation_id = conversation.id

        # Delete it
        result = await conversation_repo.delete(conversation_id)
        await session.commit()

        assert result is True

        # Verify it's gone
        retrieved = await conversation_repo.get_by_id(conversation_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self, conversation_repo, session):
        """Test deleting a non-existent conversation."""
        result = await conversation_repo.delete(uuid.uuid4())
        assert result is False


class TestMessageRepository:
    """Test MessageRepository operations."""

    @pytest.mark.asyncio
    async def test_create_message(self, conversation_repo, message_repo, session):
        """Test creating a new message."""
        # Create a conversation first
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )
        await session.commit()

        # Create a message
        timestamp = datetime.now(UTC)
        message = await message_repo.create(
            conversation_id=conversation.id,
            role="user",
            content="Hello, world!",
            timestamp=timestamp,
            sources=[{"type": "email", "id": "email123"}],
            extra_metadata={"tokens": 10},
        )

        assert message.id is not None
        assert message.conversation_id == conversation.id
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.timestamp == timestamp
        assert message.sources == [{"type": "email", "id": "email123"}]
        assert message.extra_metadata == {"tokens": 10}

    @pytest.mark.asyncio
    async def test_get_by_id(self, conversation_repo, message_repo, session):
        """Test retrieving a message by ID."""
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )
        created_message = await message_repo.create(
            conversation_id=conversation.id,
            role="assistant",
            content="Test message",
        )
        await session.commit()

        # Retrieve it
        retrieved = await message_repo.get_by_id(created_message.id)

        assert retrieved is not None
        assert retrieved.id == created_message.id
        assert retrieved.content == "Test message"

    @pytest.mark.asyncio
    async def test_get_by_conversation(self, conversation_repo, message_repo, session):
        """Test retrieving messages for a conversation."""
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )

        # Create multiple messages
        msg1 = await message_repo.create(
            conversation_id=conversation.id,
            role="user",
            content="First message",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        msg2 = await message_repo.create(
            conversation_id=conversation.id,
            role="assistant",
            content="Second message",
            timestamp=datetime(2024, 1, 1, 12, 1, 0, tzinfo=UTC),
        )
        await session.commit()

        # Retrieve all messages
        messages = await message_repo.get_by_conversation(conversation.id)

        assert len(messages) == 2
        # Should be ordered by timestamp ascending
        assert messages[0].id == msg1.id
        assert messages[1].id == msg2.id

    @pytest.mark.asyncio
    async def test_get_by_conversation_with_limit(
        self, conversation_repo, message_repo, session
    ):
        """Test retrieving messages with limit."""
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )

        # Create 5 messages
        for i in range(5):
            await message_repo.create(
                conversation_id=conversation.id,
                role="user",
                content=f"Message {i}",
            )
        await session.commit()

        # Get only 3 messages
        messages = await message_repo.get_by_conversation(conversation.id, limit=3)

        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_get_recent_messages(self, conversation_repo, message_repo, session):
        """Test retrieving recent messages."""
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )

        # Create messages with different timestamps
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        for i in range(5):
            await message_repo.create(
                conversation_id=conversation.id,
                role="user",
                content=f"Message {i}",
                timestamp=datetime(
                    2024, 1, 1, 12, i, 0, tzinfo=UTC
                ),  # Incrementing minutes
            )
        await session.commit()

        # Get 3 most recent messages
        recent = await message_repo.get_recent_messages(conversation.id, limit=3)

        assert len(recent) == 3
        # Should be in chronological order (oldest to newest of the recent ones)
        assert "Message 2" in recent[0].content
        assert "Message 3" in recent[1].content
        assert "Message 4" in recent[2].content

    @pytest.mark.asyncio
    async def test_count_by_conversation(
        self, conversation_repo, message_repo, session
    ):
        """Test counting messages in a conversation."""
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )

        # Initially 0
        count = await message_repo.count_by_conversation(conversation.id)
        assert count == 0

        # Add 3 messages
        for i in range(3):
            await message_repo.create(
                conversation_id=conversation.id, role="user", content=f"Message {i}"
            )
        await session.commit()

        count = await message_repo.count_by_conversation(conversation.id)
        assert count == 3

    @pytest.mark.asyncio
    async def test_delete_message(self, conversation_repo, message_repo, session):
        """Test deleting a message."""
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )
        message = await message_repo.create(
            conversation_id=conversation.id, role="user", content="Test"
        )
        await session.commit()

        message_id = message.id

        # Delete it
        result = await message_repo.delete(message_id)
        await session.commit()

        assert result is True

        # Verify it's gone
        retrieved = await message_repo.get_by_id(message_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_cascade_delete(self, conversation_repo, message_repo, session):
        """Test that deleting a conversation cascades to messages."""
        conversation = await conversation_repo.create(
            user_id="user123", model_used="model1"
        )
        message = await message_repo.create(
            conversation_id=conversation.id, role="user", content="Test"
        )
        await session.commit()

        conversation_id = conversation.id
        message_id = message.id

        # Delete the conversation
        await conversation_repo.delete(conversation_id)
        await session.commit()

        # Message should also be deleted (cascade)
        retrieved_message = await message_repo.get_by_id(message_id)
        assert retrieved_message is None
