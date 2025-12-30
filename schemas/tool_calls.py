"""
Tool execution schemas for agent function calling.

Defines data models for:
- Generic tool input/output
- Email parsing
- Document extraction
- Conflict resolution (future)
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.trip import ActivityInfo, FlightInfo, HotelInfo


class ToolInput(BaseModel):
    """
    Generic tool input schema.

    Used when agents need to call tools/functions with arbitrary parameters.
    """

    tool_name: str = Field(
        description="Name of the tool to execute",
        examples=["email_parser", "document_extractor", "conflict_resolver"],
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific parameters as key-value pairs",
        examples=[{"email_content": "Your flight confirmation...", "trip_id": "trip_abc"}],
    )

    @field_validator("tool_name")
    @classmethod
    def tool_name_not_empty(cls, v: str) -> str:
        """Ensure tool_name is not empty."""
        if not v or not v.strip():
            raise ValueError("Tool name cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tool_name": "email_parser",
                    "parameters": {
                        "email_content": "Flight confirmation for UA 123...",
                        "trip_id": "trip_tokyo2025",
                    },
                }
            ]
        }
    )


class ToolOutput(BaseModel):
    """
    Generic tool output schema.

    Standard response format for all tool executions.
    """

    success: bool = Field(description="Whether the tool execution succeeded")
    result: Any = Field(
        default=None,
        description="Tool execution result (type depends on tool)",
    )
    error: str | None = Field(default=None, description="Error message if execution failed")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the execution",
        examples=[{"execution_time_ms": 1200, "items_processed": 3}],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "result": {"flights": 2, "hotels": 1, "activities": 0},
                    "error": None,
                    "metadata": {"execution_time_ms": 1200},
                }
            ]
        }
    )


class EmailParserInput(BaseModel):
    """
    Input for email parsing tool.

    Used by Trip Coordinator Agent to extract travel data from forwarded
    confirmation emails (flights, hotels, activities).
    """

    email_content: str = Field(
        description="Raw email content (text or HTML)",
        max_length=100000,
        examples=["Flight Confirmation\nUnited Airlines\nFlight UA 123..."],
    )
    trip_id: str = Field(
        description="Trip ID to associate extracted data with",
        examples=["trip_tokyo2025"],
    )
    sender: str | None = Field(
        default=None,
        description="Email sender address (helps identify source type)",
        examples=["confirmations@united.com"],
    )
    subject: str | None = Field(
        default=None,
        description="Email subject line",
        examples=["Your United Airlines Flight Confirmation"],
    )

    @field_validator("email_content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Ensure email content is not empty."""
        if not v or not v.strip():
            raise ValueError("Email content cannot be empty")
        return v

    @field_validator("trip_id")
    @classmethod
    def trip_id_not_empty(cls, v: str) -> str:
        """Ensure trip_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Trip ID cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email_content": "Flight Confirmation\n\nUnited Airlines\nFlight: UA 123\nFrom: San Francisco (SFO)\nTo: Tokyo Narita (NRT)\nDeparture: Dec 20, 2025 7:00 PM\nArrival: Dec 21, 2025 3:45 PM\nPassenger: John Doe\nConfirmation: ABC123",
                    "trip_id": "trip_tokyo2025",
                    "sender": "confirmations@united.com",
                    "subject": "Your United Airlines Flight Confirmation",
                }
            ]
        }
    )


class EmailParserOutput(BaseModel):
    """
    Output from email parsing tool.

    Contains extracted travel data (flights, hotels, activities)
    from confirmation emails.
    """

    success: bool = Field(description="Whether parsing succeeded")
    flights: list[FlightInfo] = Field(
        default_factory=list, description="Extracted flight information"
    )
    hotels: list[HotelInfo] = Field(
        default_factory=list, description="Extracted hotel reservations"
    )
    activities: list[ActivityInfo] = Field(
        default_factory=list, description="Extracted activity bookings"
    )
    error: str | None = Field(default=None, description="Error message if parsing failed")
    confidence: float | None = Field(
        default=None,
        description="Confidence score for extraction quality (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "flights": [
                        {
                            "airline": "United Airlines",
                            "flight_number": "UA 123",
                            "departure_airport": "SFO",
                            "arrival_airport": "NRT",
                            "departure_time": "2025-12-20T19:00:00Z",
                            "arrival_time": "2025-12-21T15:45:00Z",
                            "passenger": "John Doe",
                            "confirmation_code": "ABC123",
                            "seat": None,
                            "source": {
                                "type": "email",
                                "description": "United Airlines confirmation email",
                                "timestamp": "2025-12-16T14:30:00Z",
                                "metadata": {"sender": "confirmations@united.com"},
                            },
                        }
                    ],
                    "hotels": [],
                    "activities": [],
                    "error": None,
                    "confidence": 0.95,
                }
            ]
        }
    )


class DocumentExtractorInput(BaseModel):
    """
    Input for document extraction tool.

    Used to extract text and structured data from PDFs, images,
    or other document formats (e.g., screenshots of confirmations).
    """

    file_path: str | None = Field(
        default=None,
        description="Path to document file (for local files)",
        examples=["/tmp/flight_confirmation.pdf"],
    )
    file_url: str | None = Field(
        default=None,
        description="URL to document (for remote files)",
        examples=["https://example.com/confirmation.pdf"],
    )
    file_content: bytes | None = Field(
        default=None, description="Raw file content (alternative to path/url)"
    )
    trip_id: str = Field(
        description="Trip ID to associate extracted data with",
        examples=["trip_tokyo2025"],
    )
    document_type: str | None = Field(
        default=None,
        description="Expected document type hint (pdf, image, etc.)",
        examples=["pdf", "png", "jpeg"],
    )

    @field_validator("trip_id")
    @classmethod
    def trip_id_not_empty(cls, v: str) -> str:
        """Ensure trip_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Trip ID cannot be empty")
        return v.strip()

    def model_post_init(self, __context: Any) -> None:
        """Ensure at least one file source is provided."""
        if not any([self.file_path, self.file_url, self.file_content]):
            raise ValueError("Must provide file_path, file_url, or file_content")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_path": "/tmp/hotel_confirmation.pdf",
                    "file_url": None,
                    "file_content": None,
                    "trip_id": "trip_tokyo2025",
                    "document_type": "pdf",
                }
            ]
        }
    )


class DocumentExtractorOutput(BaseModel):
    """
    Output from document extraction tool.

    Contains extracted text and structured travel data from documents.
    """

    success: bool = Field(description="Whether extraction succeeded")
    extracted_text: str | None = Field(
        default=None, description="Raw text extracted from document"
    )
    flights: list[FlightInfo] = Field(
        default_factory=list, description="Extracted flight information"
    )
    hotels: list[HotelInfo] = Field(
        default_factory=list, description="Extracted hotel reservations"
    )
    activities: list[ActivityInfo] = Field(
        default_factory=list, description="Extracted activity bookings"
    )
    error: str | None = Field(default=None, description="Error message if extraction failed")
    confidence: float | None = Field(
        default=None,
        description="Confidence score for extraction quality (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "extracted_text": "Hotel Confirmation\nPark Hyatt Tokyo...",
                    "flights": [],
                    "hotels": [
                        {
                            "name": "Park Hyatt Tokyo",
                            "address": "3-7-1-2 Nishi-Shinjuku",
                            "check_in": "2025-12-21T15:00:00Z",
                            "check_out": "2025-12-27T11:00:00Z",
                            "guest": "John Doe",
                            "confirmation_code": "HOTEL123",
                            "room_type": "Deluxe King",
                            "source": {
                                "type": "document",
                                "description": "Hotel confirmation PDF",
                                "timestamp": "2025-12-16T14:30:00Z",
                                "metadata": {"file_type": "pdf"},
                            },
                        }
                    ],
                    "activities": [],
                    "error": None,
                    "confidence": 0.92,
                }
            ]
        }
    )


class ConflictResolverInput(BaseModel):
    """
    Input for conflict resolution tool (future feature).

    Used when multiple sources provide conflicting information
    about the same travel element (e.g., different flight times).
    """

    trip_id: str = Field(description="Trip ID where conflict exists", examples=["trip_tokyo2025"])
    conflict_type: str = Field(
        description="Type of conflict (flight, hotel, activity)",
        examples=["flight", "hotel"],
    )
    conflicting_data: list[dict[str, Any]] = Field(
        description="List of conflicting data records with their sources",
        examples=[
            [
                {
                    "departure_time": "2025-12-20T19:00:00Z",
                    "source": "United email",
                },
                {
                    "departure_time": "2025-12-20T20:00:00Z",
                    "source": "User input",
                },
            ]
        ],
    )
    resolution_strategy: str | None = Field(
        default="most_recent",
        description="How to resolve conflicts (most_recent, user_input_priority, etc.)",
        examples=["most_recent", "user_input_priority", "manual"],
    )

    @field_validator("trip_id")
    @classmethod
    def trip_id_not_empty(cls, v: str) -> str:
        """Ensure trip_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Trip ID cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "trip_id": "trip_tokyo2025",
                    "conflict_type": "flight",
                    "conflicting_data": [
                        {
                            "departure_time": "2025-12-20T19:00:00Z",
                            "source": "United Airlines email",
                        },
                        {
                            "departure_time": "2025-12-20T20:00:00Z",
                            "source": "User manual input",
                        },
                    ],
                    "resolution_strategy": "user_input_priority",
                }
            ]
        }
    )


class ConflictResolverOutput(BaseModel):
    """
    Output from conflict resolution tool (future feature).

    Contains the resolved data and explanation of resolution logic.
    """

    success: bool = Field(description="Whether resolution succeeded")
    resolved_data: dict[str, Any] | None = Field(
        default=None, description="Resolved data after conflict resolution"
    )
    resolution_explanation: str | None = Field(
        default=None,
        description="Explanation of how conflict was resolved",
        examples=["User input prioritized over email due to manual correction"],
    )
    error: str | None = Field(default=None, description="Error message if resolution failed")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "resolved_data": {
                        "departure_time": "2025-12-20T20:00:00Z",
                        "source": "User manual input",
                    },
                    "resolution_explanation": "User input prioritized over email confirmation due to manual correction policy",
                    "error": None,
                }
            ]
        }
    )
