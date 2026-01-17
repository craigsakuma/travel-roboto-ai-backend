"""
Message schemas for feedback and management.

Defines data models for message operations from Supabase.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageFeedbackRequest(BaseModel):
    """Request schema for updating message feedback."""

    feedback: Literal["up", "down"] = Field(
        description="User feedback: 'up' or 'down'",
        examples=["up"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"feedback": "up"},
                {"feedback": "down"},
            ]
        }
    )


class MessageFeedbackResponse(BaseModel):
    """Response schema for message feedback operations."""

    success: bool = Field(
        description="Whether the feedback was updated successfully",
        examples=[True],
    )
    message_id: str = Field(
        description="Message UUID that was updated",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "message_id": "123e4567-e89b-12d3-a456-426614174000",
                }
            ]
        }
    )
