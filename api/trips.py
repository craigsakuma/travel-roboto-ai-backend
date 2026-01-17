"""
Trips API endpoints.

Provides endpoints for trip data synchronization and querying.
"""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sql_delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Trip, TripTraveler
from db.session import get_db
from schemas.trip import (
    TripDeleteResponse,
    TripMemberRemoveResponse,
    TripMemberSyncRequest,
    TripMemberSyncResponse,
    TripSyncRequest,
    TripSyncResponse,
)
from utils.logging import get_agent_logger

router = APIRouter(tags=["Trips"])
logger = get_agent_logger("api.trips")


@router.post("/sync", status_code=status.HTTP_200_OK, response_model=TripSyncResponse)
async def sync_trip(
    trip_data: TripSyncRequest,
    db: AsyncSession = Depends(get_db),
) -> TripSyncResponse:
    """
    Sync trip data from Supabase to backend database.

    This endpoint is called by the frontend after creating or updating a trip
    in Supabase. Uses upsert pattern to handle both creation and updates idempotently.

    **Request Body:**
    ```json
    {
      "id": "62a88f76-e87d-4084-a89e-fd897b3e4592",
      "name": "SF Fall Trip",
      "destination": "San Francisco, CA",
      "start_date": "2026-09-04",
      "end_date": "2026-10-05",
      "created_by_user_id": "6b2e069d-ce69-45dc-96b2-b570680f56b7"
    }
    ```

    **Response:**
    ```json
    {
      "success": true,
      "trip_id": "62a88f76-e87d-4084-a89e-fd897b3e4592"
    }
    ```
    """
    logger.logger.info(
        "Syncing trip from Supabase",
        extra={
            "trip_id": trip_data.id,
            "trip_name": trip_data.name,
            "created_by": trip_data.created_by_user_id,
        },
    )

    try:
        # Convert string UUIDs to UUID objects
        trip_id = uuid.UUID(trip_data.id)
        created_by_user_id = uuid.UUID(trip_data.created_by_user_id)

        # Parse dates
        def parse_date(date_str: str) -> date:
            """Parse date from YYYY-MM-DD or ISO 8601 format."""
            try:
                # Try ISO 8601 datetime format first
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return dt.date()
            except ValueError:
                # Fall back to simple date format
                return datetime.strptime(date_str, "%Y-%m-%d").date()

        start_date = parse_date(trip_data.start_date)
        end_date = parse_date(trip_data.end_date)

        # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE (upsert)
        stmt = insert(Trip).values(
            id=trip_id,
            name=trip_data.name,
            destination=trip_data.destination,
            start_date=start_date,
            end_date=end_date,
            created_by_user_id=created_by_user_id,
            structured_data={},
            raw_extractions=[],
            summary=None,
        )

        # On conflict, update all fields except id, created_at, structured_data, raw_extractions
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": stmt.excluded.name,
                "destination": stmt.excluded.destination,
                "start_date": stmt.excluded.start_date,
                "end_date": stmt.excluded.end_date,
            },
        )

        await db.execute(stmt)
        await db.commit()

        logger.logger.info(
            "Trip synced successfully",
            extra={"trip_id": str(trip_id), "trip_name": trip_data.name},
        )

        return TripSyncResponse(success=True, trip_id=str(trip_id))

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            e,
            context="trip_sync_integrity_error",
            trip_id=trip_data.id,
            created_by=trip_data.created_by_user_id,
        )

        # Check if it's a foreign key violation (user doesn't exist)
        if "foreign key" in str(e).lower() and "users" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {trip_data.created_by_user_id} not found. Please sync user first.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database integrity error: {str(e)}",
            )

    except ValueError as e:
        logger.error(
            e,
            context="trip_sync_validation_error",
            trip_id=trip_data.id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    except Exception as e:
        await db.rollback()
        logger.error(
            e,
            context="trip_sync_error",
            trip_id=trip_data.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync trip",
        )


@router.delete("/{trip_id}", status_code=status.HTTP_200_OK, response_model=TripDeleteResponse)
async def delete_trip(
    trip_id: str,
    db: AsyncSession = Depends(get_db),
) -> TripDeleteResponse:
    """
    Delete trip from backend database when deleted in Supabase.

    This endpoint is idempotent - returns success even if trip doesn't exist.
    Related records (conversations, messages, trip_travelers) are cascade deleted.

    **Response:**
    ```json
    {
      "success": true
    }
    ```
    """
    logger.logger.info(
        "Deleting trip from backend",
        extra={"trip_id": trip_id},
    )

    try:
        # Convert string UUID to UUID object
        trip_uuid = uuid.UUID(trip_id)

        # Delete trip (cascade deletes related records via foreign key constraints)
        stmt = sql_delete(Trip).where(Trip.id == trip_uuid)
        await db.execute(stmt)
        await db.commit()

        logger.logger.info(
            "Trip deleted successfully",
            extra={"trip_id": trip_id},
        )

        return TripDeleteResponse(success=True)

    except ValueError as e:
        logger.error(
            e,
            context="trip_delete_validation_error",
            trip_id=trip_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid trip_id format: {trip_id}",
        )

    except Exception as e:
        await db.rollback()
        logger.error(
            e,
            context="trip_delete_error",
            trip_id=trip_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete trip",
        )


@router.post(
    "/{trip_id}/members/sync",
    status_code=status.HTTP_200_OK,
    response_model=TripMemberSyncResponse,
)
async def sync_trip_member(
    trip_id: str,
    member_data: TripMemberSyncRequest,
    db: AsyncSession = Depends(get_db),
) -> TripMemberSyncResponse:
    """
    Sync trip member/traveler data from Supabase to backend database.

    This endpoint is called when a user is invited to or joins a trip.
    Uses upsert pattern to handle both creation and updates idempotently.

    **Request Body:**
    ```json
    {
      "user_id": "6b2e069d-ce69-45dc-96b2-b570680f56b7",
      "role": "traveler"
    }
    ```

    **Response:**
    ```json
    {
      "success": true,
      "trip_id": "62a88f76-e87d-4084-a89e-fd897b3e4592",
      "user_id": "6b2e069d-ce69-45dc-96b2-b570680f56b7"
    }
    ```
    """
    logger.logger.info(
        "Syncing trip member from Supabase",
        extra={
            "trip_id": trip_id,
            "user_id": member_data.user_id,
            "role": member_data.role,
        },
    )

    try:
        # Convert string UUIDs to UUID objects
        trip_uuid = uuid.UUID(trip_id)
        user_uuid = uuid.UUID(member_data.user_id)

        # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE (upsert)
        stmt = insert(TripTraveler).values(
            trip_id=trip_uuid,
            user_id=user_uuid,
            role=member_data.role,
        )

        # On conflict, update role
        stmt = stmt.on_conflict_do_update(
            index_elements=["trip_id", "user_id"],
            set_={"role": stmt.excluded.role},
        )

        await db.execute(stmt)
        await db.commit()

        logger.logger.info(
            "Trip member synced successfully",
            extra={
                "trip_id": trip_id,
                "user_id": member_data.user_id,
                "role": member_data.role,
            },
        )

        return TripMemberSyncResponse(
            success=True,
            trip_id=trip_id,
            user_id=member_data.user_id,
        )

    except IntegrityError as e:
        await db.rollback()
        logger.error(
            e,
            context="trip_member_sync_integrity_error",
            trip_id=trip_id,
            user_id=member_data.user_id,
        )

        # Check if it's a foreign key violation
        error_str = str(e).lower()
        if "foreign key" in error_str:
            if "users" in error_str:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User {member_data.user_id} not found. Please sync user first.",
                )
            elif "trips" in error_str:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Trip {trip_id} not found. Please sync trip first.",
                )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database integrity error: {str(e)}",
        )

    except ValueError as e:
        logger.error(
            e,
            context="trip_member_sync_validation_error",
            trip_id=trip_id,
            user_id=member_data.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    except Exception as e:
        await db.rollback()
        logger.error(
            e,
            context="trip_member_sync_error",
            trip_id=trip_id,
            user_id=member_data.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync trip member",
        )


@router.delete(
    "/{trip_id}/members/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=TripMemberRemoveResponse,
)
async def remove_trip_member(
    trip_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> TripMemberRemoveResponse:
    """
    Remove trip member from backend database when removed in Supabase.

    This endpoint is idempotent - returns success even if membership doesn't exist.

    **Response:**
    ```json
    {
      "success": true
    }
    ```
    """
    logger.logger.info(
        "Removing trip member from backend",
        extra={"trip_id": trip_id, "user_id": user_id},
    )

    try:
        # Convert string UUIDs to UUID objects
        trip_uuid = uuid.UUID(trip_id)
        user_uuid = uuid.UUID(user_id)

        # Delete trip traveler record
        stmt = sql_delete(TripTraveler).where(
            TripTraveler.trip_id == trip_uuid,
            TripTraveler.user_id == user_uuid,
        )
        await db.execute(stmt)
        await db.commit()

        logger.logger.info(
            "Trip member removed successfully",
            extra={"trip_id": trip_id, "user_id": user_id},
        )

        return TripMemberRemoveResponse(success=True)

    except ValueError as e:
        logger.error(
            e,
            context="trip_member_remove_validation_error",
            trip_id=trip_id,
            user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid UUID format",
        )

    except Exception as e:
        await db.rollback()
        logger.error(
            e,
            context="trip_member_remove_error",
            trip_id=trip_id,
            user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove trip member",
        )
