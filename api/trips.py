"""
Trips API endpoints.

Provides endpoints for trip data synchronization and querying.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/trips", tags=["trips"])

# TODO: Implement trip sync endpoints in Phase 1
# - POST /users/sync - Sync user profile from frontend
# - POST /trips/sync - Sync trip data from frontend
# - DELETE /trips/{id} - Delete trip
