"""
Trip-related tools for LLM function calling.

Provides tools for querying and manipulating trip data.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Trip, TripTraveler
from tools.registry import ToolRegistry
from utils.logging import get_agent_logger

logger = get_agent_logger("trip_tools")


async def get_trip_details(trip_id: str, db: AsyncSession) -> dict[str, Any]:
    """
    Retrieve comprehensive trip details by ID.

    Args:
        trip_id: Trip UUID as string
        db: Database session

    Returns:
        Dictionary with trip details including:
        - Basic info (name, destination, dates)
        - Travelers list
        - Structured data (flights, hotels, activities)
        - Summary

    Raises:
        ValueError: If trip not found
    """
    logger.logger.info(f"Fetching trip details for {trip_id}")

    try:
        trip_uuid = uuid.UUID(trip_id)
    except ValueError:
        raise ValueError(f"Invalid trip_id format: {trip_id}")

    # Query trip with travelers
    result = await db.execute(
        select(Trip).where(Trip.id == trip_uuid)
    )
    trip = result.scalar_one_or_none()

    if not trip:
        raise ValueError(f"Trip not found: {trip_id}")

    # Query travelers for this trip
    travelers_result = await db.execute(
        select(TripTraveler).where(TripTraveler.trip_id == trip_uuid)
    )
    travelers = travelers_result.scalars().all()

    # Build response
    trip_data = {
        "id": str(trip.id),
        "name": trip.name,
        "destination": trip.destination,
        "start_date": trip.start_date.isoformat(),
        "end_date": trip.end_date.isoformat(),
        "summary": trip.summary,
        "travelers": [
            {
                "user_id": str(t.user_id),
                "role": t.role,
            }
            for t in travelers
        ],
        "structured_data": trip.structured_data or {},
        "created_at": trip.created_at.isoformat(),
        "updated_at": trip.updated_at.isoformat(),
    }

    logger.logger.debug(
        f"Retrieved trip: {trip.name}", extra={"trip_id": trip_id}
    )

    return trip_data


def register_trip_tools(registry: ToolRegistry) -> None:
    """
    Register all trip-related tools in the registry.

    Args:
        registry: ToolRegistry instance
    """
    # Register get_trip_details tool
    registry.register(
        name="get_trip_details",
        description=(
            "Retrieve comprehensive details about a trip by its ID. "
            "Returns trip information including destination, dates, travelers, "
            "and structured data (flights, hotels, activities)."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "string",
                    "description": "UUID of the trip to retrieve",
                }
            },
            "required": ["trip_id"],
        },
        function=get_trip_details,
    )

    logger.logger.info("Registered trip tools in registry")
