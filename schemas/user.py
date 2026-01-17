"""
User profile schemas for synchronization.

Defines data models for user sync operations from Supabase.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSyncRequest(BaseModel):
    """
    Request schema for syncing user data from Supabase to backend.

    Used by POST /api/users/sync endpoint to sync user profile data.
    """

    id: str = Field(
        description="User UUID from Supabase (use as primary key)",
        examples=["6b2e069d-ce69-45dc-96b2-b570680f56b7"],
    )
    email: EmailStr = Field(
        description="User email address",
        examples=["user@example.com"],
    )
    first_name: str | None = Field(
        default=None,
        description="User first name",
        examples=["John"],
    )
    last_name: str | None = Field(
        default=None,
        description="User last name",
        examples=["Doe"],
    )
    phone: str | None = Field(
        default=None,
        description="User phone number",
        examples=["+1234567890"],
    )
    home_city: str | None = Field(
        default=None,
        description="User home city for context",
        examples=["San Francisco"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "6b2e069d-ce69-45dc-96b2-b570680f56b7",
                    "email": "user@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "phone": "+1234567890",
                    "home_city": "San Francisco",
                }
            ]
        }
    )


class UserSyncResponse(BaseModel):
    """Response schema for user sync operations."""

    success: bool = Field(
        description="Whether the sync was successful",
        examples=[True],
    )
    user_id: str = Field(
        description="User UUID that was synced",
        examples=["6b2e069d-ce69-45dc-96b2-b570680f56b7"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "user_id": "6b2e069d-ce69-45dc-96b2-b570680f56b7",
                }
            ]
        }
    )
