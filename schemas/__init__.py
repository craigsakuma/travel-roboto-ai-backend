"""
Pydantic schemas for Travel Agent API.

Provides data models for:
- Chat messages and conversation metadata
- Trip data and travel information
- Tool execution inputs and outputs
- Common types and utilities
"""

# Common types and base classes
from schemas.common import MessageRole, Source, SourceType, Timestamp

# Message schemas
from schemas.messages import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationMetadata,
)

# Trip data schemas
from schemas.trip import (
    ActivityInfo,
    FlightInfo,
    HotelInfo,
    TripData,
    TripMetadata,
)

# Tool execution schemas
from schemas.tool_calls import (
    ConflictResolverInput,
    ConflictResolverOutput,
    DocumentExtractorInput,
    DocumentExtractorOutput,
    EmailParserInput,
    EmailParserOutput,
    ToolInput,
    ToolOutput,
)

__all__ = [
    # Common
    "MessageRole",
    "Source",
    "SourceType",
    "Timestamp",
    # Messages
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ConversationMetadata",
    # Trip
    "ActivityInfo",
    "FlightInfo",
    "HotelInfo",
    "TripData",
    "TripMetadata",
    # Tools
    "ConflictResolverInput",
    "ConflictResolverOutput",
    "DocumentExtractorInput",
    "DocumentExtractorOutput",
    "EmailParserInput",
    "EmailParserOutput",
    "ToolInput",
    "ToolOutput",
]
