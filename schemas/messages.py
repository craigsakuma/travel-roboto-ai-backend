"""
Chat message and conversation schemas.

Defines data models for:
- Individual chat messages
- Conversation metadata
- Chat API requests and responses
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.common import Source, Timestamp


class ChatMessage(BaseModel):
    """
    Individual message in a conversation.

    Represents a single message exchanged between user and assistant,
    including metadata for tracking and attribution.
    """

    role: Literal["user", "assistant", "system"] = Field(
        description="Role of the message sender"
    )
    content: str = Field(
        description="Message text content",
        max_length=50000,
        examples=["What time does my flight to Tokyo depart?"],
    )
    timestamp: Timestamp = Field(
        description="When the message was created",
        default_factory=lambda: datetime.now(UTC),
    )
    sources: list[Source] | None = Field(
        default=None,
        description="Data sources used to generate this message (for assistant responses)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional message metadata (e.g., model_used, tokens, latency)",
        examples=[{"model_used": "claude-sonnet-4", "tokens": 150, "latency_ms": 1200}],
    )

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Ensure content is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "role": "user",
                    "content": "What time does my flight to Tokyo depart?",
                    "timestamp": "2025-12-16T14:30:00Z",
                    "sources": None,
                    "metadata": {},
                },
                {
                    "role": "assistant",
                    "content": "Your flight UA 123 departs at 7:00 PM on December 20th.",
                    "timestamp": "2025-12-16T14:30:05Z",
                    "sources": [
                        {
                            "type": "email",
                            "description": "United Airlines confirmation email",
                            "timestamp": "2025-12-15T10:00:00Z",
                            "metadata": {"email_id": "msg_abc123"},
                        }
                    ],
                    "metadata": {"model_used": "claude-sonnet-4", "tokens": 150},
                },
            ]
        }
    )


class ConversationMetadata(BaseModel):
    """
    Metadata for a conversation thread.

    Tracks conversation-level information including participants,
    associated trip, model assignment, and A/B testing variants.
    """

    conversation_id: str = Field(description="Unique conversation identifier")
    trip_id: str | None = Field(
        default=None, description="Associated trip ID (if conversation is about a trip)"
    )
    user_id: str = Field(description="User who initiated the conversation")
    created_at: Timestamp = Field(
        description="When the conversation was created",
        default_factory=lambda: datetime.now(UTC),
    )
    updated_at: Timestamp = Field(
        description="Last message timestamp",
        default_factory=lambda: datetime.now(UTC),
    )
    model_used: str = Field(
        description="Primary LLM model used for this conversation",
        examples=["claude-sonnet-4", "gpt-5-mini", "gemini-2.0-flash"],
    )
    ab_test_variant: str | None = Field(
        default=None,
        description="A/B test variant assignment (e.g., 'control', 'variant_a')",
    )
    message_count: int = Field(default=0, description="Number of messages in conversation", ge=0)

    @field_validator("conversation_id", "user_id")
    @classmethod
    def ids_not_empty(cls, v: str) -> str:
        """Ensure IDs are not empty."""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "conversation_id": "conv_abc123xyz",
                    "trip_id": "trip_tokyo2025",
                    "user_id": "user_john_doe",
                    "created_at": "2025-12-16T14:00:00Z",
                    "updated_at": "2025-12-16T14:30:00Z",
                    "model_used": "claude-sonnet-4",
                    "ab_test_variant": "control",
                    "message_count": 5,
                }
            ]
        }
    )


class ChatRequest(BaseModel):
    """
    Request to the Travel Concierge Agent chat endpoint.

    Sent by frontend when user submits a message.
    """

    message: str = Field(
        description="User's message text",
        max_length=10000,
        examples=["What hotels are we staying at in Tokyo?"],
    )
    user_id: str = Field(description="User identifier", examples=["user_john_doe"])
    trip_id: str | None = Field(
        default=None,
        description="Trip ID if conversation is about a specific trip",
        examples=["trip_tokyo2025"],
    )
    conversation_id: str | None = Field(
        default=None,
        description="Existing conversation ID (if continuing a conversation)",
        examples=["conv_abc123xyz"],
    )

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        """Ensure message is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()

    @field_validator("user_id")
    @classmethod
    def user_id_not_empty(cls, v: str) -> str:
        """Ensure user_id is not empty."""
        if not v or not v.strip():
            raise ValueError("User ID cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "What time does my flight arrive?",
                    "user_id": "user_john_doe",
                    "trip_id": "trip_tokyo2025",
                    "conversation_id": "conv_abc123xyz",
                }
            ]
        }
    )


class ChatResponse(BaseModel):
    """
    Response from the Travel Concierge Agent chat endpoint.

    Contains the assistant's message along with attribution,
    conversation tracking, and metadata.
    """

    message: str = Field(
        description="Assistant's response message",
        examples=["Your flight arrives at Narita Airport at 3:45 PM local time."],
    )
    conversation_id: str = Field(
        description="Conversation ID (new or existing)", examples=["conv_abc123xyz"]
    )
    timestamp: Timestamp = Field(
        description="When the response was generated",
        default_factory=lambda: datetime.now(UTC),
    )
    sources: list[Source] | None = Field(
        default=None, description="Data sources used to generate the response"
    )
    model_used: str = Field(
        description="LLM model that generated the response",
        examples=["claude-sonnet-4", "gpt-5-mini"],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata (tokens, latency, etc.)",
        examples=[{"tokens": 150, "latency_ms": 1200, "tools_used": ["flight_lookup"]}],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "Your flight UA 123 arrives at 3:45 PM local time on December 20th.",
                    "conversation_id": "conv_abc123xyz",
                    "timestamp": "2025-12-16T14:30:05Z",
                    "sources": [
                        {
                            "type": "email",
                            "description": "United Airlines confirmation email",
                            "timestamp": "2025-12-15T10:00:00Z",
                            "metadata": {"email_id": "msg_abc123"},
                        }
                    ],
                    "model_used": "claude-sonnet-4",
                    "metadata": {"tokens": 150, "latency_ms": 1200},
                }
            ]
        }
    )
