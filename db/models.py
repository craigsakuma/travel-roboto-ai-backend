"""
SQLAlchemy ORM models for Travel Roboto AI backend.

Comprehensive models for Phase 1:
- Users
- Trips and trip travelers
- Conversations and messages
- Observability (LLM requests, metrics)
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin


# ============================================================================
# Core Entity Models
# ============================================================================


class User(Base, TimestampMixin):
    """
    User accounts synced from frontend (Supabase).

    Stores user profile information needed for AI context and personalization.
    Primary key reuses Supabase user_id for simplicity.
    """

    __tablename__ = "users"

    # Primary key (reuses Supabase user_id)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        doc="User ID (reuses Supabase user_id)",
    )

    # Profile information
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="User email address",
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="User phone number",
    )

    home_city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="User home city for context",
    )

    first_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="User first name",
    )

    last_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="User last name",
    )

    # Relationships
    trips_created: Mapped[list["Trip"]] = relationship(
        "Trip",
        back_populates="creator",
        foreign_keys="Trip.created_by_user_id",
        doc="Trips created by this user",
    )

    trip_memberships: Mapped[list["TripTraveler"]] = relationship(
        "TripTraveler",
        back_populates="user",
        doc="Trip memberships for this user",
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        doc="Conversations owned by this user",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, name={self.first_name} {self.last_name})>"


class Trip(Base, TimestampMixin):
    """
    Trip metadata and itinerary information.

    Uses hybrid data model:
    - Structured fields for core data (name, dates, destination)
    - JSONB for flexible itinerary data (flights, hotels, activities)
    - Summary text for agent context
    """

    __tablename__ = "trips"

    # Primary key (reuses Supabase trip_id)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        doc="Trip ID (reuses Supabase trip_id)",
    )

    # Core trip information
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Trip name (e.g., 'Barcelona Summer 2025')",
    )

    destination: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Primary destination (e.g., 'Barcelona, Spain')",
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Trip start date",
    )

    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Trip end date",
    )

    # Creator
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User who created this trip",
    )

    # Structured itinerary data (JSONB for flexibility)
    structured_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        doc="Structured trip data: {flights: [...], hotels: [...], activities: [...]}",
    )

    # Raw extractions from emails/documents
    raw_extractions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        doc="Raw extraction data: [{source: 'email:123', data: {...}, confidence: 0.95}]",
    )

    # Agent-readable summary
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Human-readable trip summary for agent context",
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="trips_created",
        foreign_keys=[created_by_user_id],
        doc="User who created this trip",
    )

    travelers: Mapped[list["TripTraveler"]] = relationship(
        "TripTraveler",
        back_populates="trip",
        cascade="all, delete-orphan",
        doc="Travelers on this trip",
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="trip",
        cascade="all, delete-orphan",
        doc="Conversations about this trip",
    )

    # Indexes
    __table_args__ = (
        Index("ix_trips_created_by", "created_by_user_id"),
        Index("ix_trips_dates", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<Trip(id={self.id}, name={self.name}, destination={self.destination})>"


class TripTraveler(Base):
    """
    Many-to-many relationship between trips and users.

    Tracks which users are traveling on which trips, and their role
    (organizer vs regular traveler).
    """

    __tablename__ = "trip_travelers"

    # Composite primary key
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Trip ID",
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="User ID",
    )

    # Role
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="traveler",
        server_default="traveler",
        doc="User role: 'organizer' or 'traveler'",
    )

    # Metadata
    joined_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="NOW()",
        doc="When user joined this trip",
    )

    # Relationships
    trip: Mapped["Trip"] = relationship(
        "Trip",
        back_populates="travelers",
        doc="Trip this traveler is on",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="trip_memberships",
        doc="User traveling",
    )

    # Indexes
    __table_args__ = (Index("ix_trip_travelers_user", "user_id"),)

    def __repr__(self) -> str:
        return f"<TripTraveler(trip_id={self.trip_id}, user_id={self.user_id}, role={self.role})>"


# ============================================================================
# Conversation Models
# ============================================================================


class Conversation(Base, TimestampMixin):
    """
    Conversation between a user and the AI agent about a trip.

    Each user has their own conversation per trip (privacy by default).
    Tracks turn number for ordering messages.
    """

    __tablename__ = "conversations"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Conversation ID",
    )

    # Foreign keys
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Trip this conversation is about",
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User who owns this conversation",
    )

    # Metadata
    conversation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="chat",
        server_default="chat",
        doc="Type of conversation: 'chat', 'email_thread'",
    )

    next_turn_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        doc="Next turn number for ordering messages",
    )

    # Relationships
    trip: Mapped["Trip"] = relationship(
        "Trip",
        back_populates="conversations",
        doc="Trip this conversation is about",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="conversations",
        doc="User who owns this conversation",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.turn_number",
        doc="Messages in this conversation",
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("trip_id", "user_id", "conversation_type", name="uq_conversation_trip_user"),
        Index("ix_conversations_trip", "trip_id"),
        Index("ix_conversations_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, trip_id={self.trip_id}, user_id={self.user_id})>"


class Message(Base):
    """
    Individual message in a conversation.

    Stores user and assistant messages with full observability metadata:
    - Model used, prompt version
    - Token counts and cost
    - Tool calls executed
    - Latency metrics
    """

    __tablename__ = "messages"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Message ID",
    )

    # Foreign key
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Conversation this message belongs to",
    )

    # Message ownership
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User who sent this message (NULL for assistant/system messages)",
    )

    # Message content
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Message role: 'user', 'assistant', 'system', 'tool'",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Message content",
    )

    turn_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Turn number for ordering (user message and response share same turn)",
    )

    # AI metadata (for assistant messages)
    model_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Model provider: 'anthropic', 'openai'",
    )

    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Model name: 'claude-3-5-sonnet-20241022', 'gpt-4o'",
    )

    prompt_version: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Prompt version used: 'v1', 'v2'",
    )

    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Tool calls made: [{name: 'get_trip', input: {...}, output: {...}}]",
    )

    # Observability metrics
    tokens_input: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Input tokens used",
    )

    tokens_output: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Output tokens used",
    )

    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
        doc="Cost in USD",
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Response latency in milliseconds",
    )

    # User feedback
    feedback: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="User feedback: 'up', 'down'",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="NOW()",
        doc="Message creation timestamp",
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
        doc="Conversation this message belongs to",
    )

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name="ck_message_role",
        ),
        Index("ix_messages_conversation_turn", "conversation_id", "turn_number"),
        Index("ix_messages_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, role={self.role}, turn={self.turn_number}, content='{content_preview}')>"


# ============================================================================
# Observability Models
# ============================================================================


class LLMRequest(Base):
    """
    Complete LLM request/response logging for debugging and analysis.

    Stores full prompts, responses, and metadata for every LLM call.
    Critical for debugging agent behavior and replay functionality.
    """

    __tablename__ = "llm_requests"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Request ID",
    )

    # Foreign keys
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Conversation this request belongs to",
    )

    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Message this request generated",
    )

    # Request details
    model_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Model provider: 'anthropic', 'openai'",
    )

    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Model name",
    )

    full_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Complete prompt sent to LLM",
    )

    full_response: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Complete response from LLM",
    )

    # Tool calls
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Tool calls with execution details",
    )

    # Usage metrics
    tokens_input: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Input tokens",
    )

    tokens_output: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Output tokens",
    )

    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
        doc="Cost in USD",
    )

    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Latency in milliseconds",
    )

    # Response metadata
    finish_reason: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Finish reason: 'stop', 'length', 'tool_use', 'error'",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Error message if request failed",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="NOW()",
        index=True,
        doc="Request timestamp",
    )

    # Indexes
    __table_args__ = (
        Index("ix_llm_requests_conversation", "conversation_id"),
        Index("ix_llm_requests_created_at", "created_at"),
        Index("ix_llm_requests_model", "model_provider", "model_name"),
    )

    def __repr__(self) -> str:
        return f"<LLMRequest(id={self.id}, model={self.model_name}, tokens={self.tokens_input + self.tokens_output})>"


class Metric(Base):
    """
    Aggregated metrics for monitoring and analytics.

    Stores time-series data for dashboards and analysis:
    - Request counts, latencies, costs
    - Tool usage frequency
    - User engagement metrics
    """

    __tablename__ = "metrics"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Metric ID",
    )

    # Metric details
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Metric name: 'request_latency_ms', 'request_cost_usd', 'tool_calls'",
    )

    metric_value: Mapped[float] = mapped_column(
        nullable=False,
        doc="Metric value",
    )

    # Dimensions (JSONB for flexibility)
    dimensions: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        doc="Metric dimensions: {user_id: '...', model: 'claude', ...}",
    )

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        server_default="NOW()",
        doc="Metric timestamp",
    )

    # Indexes
    __table_args__ = (Index("ix_metrics_name_time", "metric_name", "timestamp"),)

    def __repr__(self) -> str:
        return f"<Metric(name={self.metric_name}, value={self.metric_value}, time={self.timestamp})>"
