"""Repository pattern for database access.

Provides clean abstraction layer between business logic and database operations.
Follows async patterns for FastAPI integration.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Conversation, Message


class ConversationRepository:
    """Repository for conversation-related database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(
        self,
        user_id: str,
        model_used: str,
        trip_id: str | None = None,
        ab_test_variant: str | None = None,
    ) -> Conversation:
        """Create a new conversation.

        Args:
            user_id: ID of the user who owns this conversation
            model_used: LLM model being used for this conversation
            trip_id: Optional ID of associated trip
            ab_test_variant: Optional A/B test variant identifier

        Returns:
            Newly created Conversation instance
        """
        conversation = Conversation(
            user_id=user_id,
            model_used=model_used,
            trip_id=trip_id,
            ab_test_variant=ab_test_variant,
            message_count=0,
        )
        self.session.add(conversation)
        await self.session.flush()  # Get ID without committing transaction
        return conversation

    async def get_by_id(
        self, conversation_id: uuid.UUID, load_messages: bool = False
    ) -> Conversation | None:
        """Retrieve a conversation by ID.

        Args:
            conversation_id: UUID of the conversation to retrieve
            load_messages: Whether to eagerly load messages relationship

        Returns:
            Conversation instance if found, None otherwise
        """
        query = select(Conversation).where(Conversation.id == conversation_id)

        if load_messages:
            query = query.options(selectinload(Conversation.messages))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> list[Conversation]:
        """Retrieve conversations for a specific user.

        Args:
            user_id: ID of the user
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip

        Returns:
            List of Conversation instances ordered by created_at descending
        """
        query = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_trip(self, trip_id: str) -> list[Conversation]:
        """Retrieve all conversations associated with a trip.

        Args:
            trip_id: ID of the trip

        Returns:
            List of Conversation instances ordered by created_at ascending
        """
        query = (
            select(Conversation)
            .where(Conversation.trip_id == trip_id)
            .order_by(Conversation.created_at.asc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_message_count(
        self, conversation_id: uuid.UUID, increment: int = 1
    ) -> None:
        """Update the message count for a conversation.

        Args:
            conversation_id: UUID of the conversation
            increment: Amount to increment message count by (default 1)
        """
        conversation = await self.get_by_id(conversation_id)
        if conversation:
            conversation.message_count += increment

    async def delete(self, conversation_id: uuid.UUID) -> bool:
        """Delete a conversation and all associated messages.

        Args:
            conversation_id: UUID of the conversation to delete

        Returns:
            True if conversation was deleted, False if not found
        """
        conversation = await self.get_by_id(conversation_id)
        if conversation:
            await self.session.delete(conversation)
            return True
        return False


class MessageRepository:
    """Repository for message-related database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        timestamp: datetime | None = None,
        sources: list[dict[str, Any]] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Create a new message.

        Args:
            conversation_id: UUID of the conversation this message belongs to
            role: Role of the message sender (user, assistant, system)
            content: Message text content
            timestamp: Message timestamp (defaults to now if not provided)
            sources: Optional list of data sources used for this message
            extra_metadata: Optional additional metadata

        Returns:
            Newly created Message instance
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=timestamp or datetime.now(),
            sources=sources,
            extra_metadata=extra_metadata or {},
        )
        self.session.add(message)
        await self.session.flush()  # Get ID without committing transaction
        return message

    async def get_by_id(self, message_id: uuid.UUID) -> Message | None:
        """Retrieve a message by ID.

        Args:
            message_id: UUID of the message to retrieve

        Returns:
            Message instance if found, None otherwise
        """
        query = select(Message).where(Message.id == message_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_conversation(
        self,
        conversation_id: uuid.UUID,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Message]:
        """Retrieve messages for a specific conversation.

        Args:
            conversation_id: UUID of the conversation
            limit: Maximum number of messages to return (None for all)
            offset: Number of messages to skip

        Returns:
            List of Message instances ordered by timestamp ascending
        """
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc())
            .offset(offset)
        )

        if limit is not None:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent_messages(
        self, conversation_id: uuid.UUID, limit: int = 10
    ) -> list[Message]:
        """Retrieve the most recent messages from a conversation.

        Args:
            conversation_id: UUID of the conversation
            limit: Maximum number of recent messages to return

        Returns:
            List of Message instances ordered by timestamp descending
        """
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        # Reverse to get chronological order
        return list(reversed(list(result.scalars().all())))

    async def count_by_conversation(self, conversation_id: uuid.UUID) -> int:
        """Count total messages in a conversation.

        Args:
            conversation_id: UUID of the conversation

        Returns:
            Total number of messages
        """
        messages = await self.get_by_conversation(conversation_id)
        return len(messages)

    async def delete(self, message_id: uuid.UUID) -> bool:
        """Delete a specific message.

        Args:
            message_id: UUID of the message to delete

        Returns:
            True if message was deleted, False if not found
        """
        message = await self.get_by_id(message_id)
        if message:
            await self.session.delete(message)
            return True
        return False
