"""
SQLAlchemy ORM models for conversation memory.

Defines database models for storing chat conversations and messages
in PostgreSQL.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    """
    Conversation metadata and tracking.

    Stores conversation-level information including participants,
    associated trip, model assignment, and A/B testing variants.
    """

    __tablename__ = "conversations"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique conversation identifier",
    )

    # Foreign keys and associations
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="User who initiated the conversation",
    )

    trip_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Associated trip ID (if conversation is about a trip)",
    )

    # Model and A/B testing
    model_used: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Primary LLM model used for this conversation",
    )

    ab_test_variant: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="A/B test variant assignment (e.g., 'control', 'variant_a')",
    )

    # Conversation stats
    message_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        doc="Number of messages in conversation",
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.timestamp",
        doc="All messages in this conversation",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_conversations_user_created", "user_id", "created_at"),
        Index("ix_conversations_trip", "trip_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation(id={self.id}, user_id={self.user_id}, "
            f"message_count={self.message_count})>"
        )


class Message(Base, TimestampMixin):
    """
    Individual message in a conversation.

    Stores message content, role, and metadata for each exchange
    between user and assistant.
    """

    __tablename__ = "messages"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique message identifier",
    )

    # Foreign key to conversation
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Conversation this message belongs to",
    )

    # Message content
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Role of the message sender (user, assistant, system)",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Message text content",
    )

    # Message timestamp
    timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        doc="When the message was created",
    )

    # Flexible JSON fields for sources and metadata
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Data sources used to generate this message (for assistant responses)",
    )

    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        doc="Additional message metadata (e.g., model_used, tokens, latency)",
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
        doc="Conversation this message belongs to",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_messages_conversation_timestamp", "conversation_id", "timestamp"),
        Index("ix_messages_role", "role"),
    )

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, role={self.role}, content='{content_preview}')>"
