"""
Common types and base classes for schema definitions.

Provides shared types, enums, and models used across multiple schema modules.
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

# Type alias for UTC timestamps
Timestamp = datetime


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SourceType(str, Enum):
    """Type of data source."""

    EMAIL = "email"
    DOCUMENT = "document"
    USER_INPUT = "user_input"
    API = "api"
    MANUAL = "manual"


class Source(BaseModel):
    """
    Tracks the provenance of information.

    Used to attribute data to its original source (e.g., email, document, user input).
    Critical for transparency and debugging data conflicts.
    """

    type: SourceType = Field(description="Type of source (email, document, etc.)")
    description: str = Field(
        description="Human-readable description of the source",
        examples=["United Airlines confirmation email 12/1/25"],
    )
    timestamp: Timestamp = Field(
        description="When this source was ingested",
        default_factory=lambda: datetime.now(UTC),
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional source metadata (e.g., email_id, file_path)",
        examples=[{"email_id": "msg_abc123", "sender": "confirmations@united.com"}],
    )

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        """Ensure description is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError("Source description cannot be empty")
        return v.strip()

    @field_validator("timestamp")
    @classmethod
    def timestamp_has_timezone(cls, v: datetime) -> datetime:
        """Ensure timestamp has timezone info (prefer UTC)."""
        if v.tzinfo is None:
            # Assume UTC if no timezone provided
            return v.replace(tzinfo=UTC)
        return v

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "email",
                    "description": "United Airlines confirmation email",
                    "timestamp": "2025-12-01T10:30:00Z",
                    "metadata": {
                        "email_id": "msg_abc123",
                        "sender": "confirmations@united.com",
                    },
                }
            ]
        }
