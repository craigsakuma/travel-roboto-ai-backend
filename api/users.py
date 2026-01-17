"""
Users API endpoints.

Provides endpoints for user profile synchronization from Supabase.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
from db.session import get_db
from schemas.user import UserSyncRequest, UserSyncResponse
from utils.logging import get_agent_logger

router = APIRouter(tags=["Users"])
logger = get_agent_logger("api.users")


@router.post("/sync", status_code=status.HTTP_200_OK, response_model=UserSyncResponse)
async def sync_user(
    user_data: UserSyncRequest,
    db: AsyncSession = Depends(get_db),
) -> UserSyncResponse:
    """
    Sync user profile data from Supabase to backend database.

    This endpoint is called by the frontend after user signup or profile update.
    Uses upsert pattern to handle both creation and updates idempotently.

    **Request Body:**
    ```json
    {
      "id": "6b2e069d-ce69-45dc-96b2-b570680f56b7",
      "email": "user@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "phone": "+1234567890",
      "home_city": "San Francisco"
    }
    ```

    **Response:**
    ```json
    {
      "success": true,
      "user_id": "6b2e069d-ce69-45dc-96b2-b570680f56b7"
    }
    ```
    """
    logger.logger.info(
        "Syncing user from Supabase",
        extra={
            "user_id": user_data.id,
            "email": user_data.email,
        },
    )

    try:
        # Convert string UUID to UUID object
        user_id = uuid.UUID(user_data.id)

        # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE (upsert)
        stmt = insert(User).values(
            id=user_id,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            home_city=user_data.home_city,
        )

        # On conflict, update all fields except id and created_at
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "email": stmt.excluded.email,
                "first_name": stmt.excluded.first_name,
                "last_name": stmt.excluded.last_name,
                "phone": stmt.excluded.phone,
                "home_city": stmt.excluded.home_city,
            },
        )

        await db.execute(stmt)
        await db.commit()

        logger.logger.info(
            "User synced successfully",
            extra={"user_id": str(user_id), "email": user_data.email},
        )

        return UserSyncResponse(success=True, user_id=str(user_id))

    except ValueError as e:
        logger.error(
            e,
            context="user_sync_validation_error",
            user_id=user_data.id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    except Exception as e:
        await db.rollback()
        logger.error(
            e,
            context="user_sync_error",
            user_id=user_data.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync user data",
        )
