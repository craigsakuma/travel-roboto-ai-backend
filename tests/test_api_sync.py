"""Integration tests for API sync endpoints.

Tests all sync endpoints with real database integration following industry best practices:
- AAA pattern (Arrange, Act, Assert)
- Comprehensive error scenario coverage
- Idempotency testing
- Database state verification
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Trip, TripTraveler


class TestUserSync:
    """Test POST /api/users/sync endpoint."""

    def test_sync_user_create_success(self, test_client: TestClient, sample_user_data):
        """Test creating a new user via sync endpoint."""
        # Arrange - data already in sample_user_data

        # Act
        response = test_client.post("/api/users/sync", json=sample_user_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user_id"] == sample_user_data["id"]

    def test_sync_user_update_success(
        self, test_client: TestClient, sample_user_data, created_user
    ):
        """Test updating an existing user via sync endpoint (upsert)."""
        # Arrange - user already exists via created_user fixture
        updated_data = sample_user_data.copy()
        updated_data["first_name"] = "Updated"
        updated_data["last_name"] = "Name"
        updated_data["home_city"] = "Los Angeles, CA"

        # Act
        response = test_client.post("/api/users/sync", json=updated_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user_id"] == sample_user_data["id"]

    def test_sync_user_idempotent(
        self, test_client: TestClient, sample_user_data, created_user
    ):
        """Test that syncing the same user multiple times is idempotent."""
        # Arrange - user already exists

        # Act - sync same data twice
        response1 = test_client.post("/api/users/sync", json=sample_user_data)
        response2 = test_client.post("/api/users/sync", json=sample_user_data)

        # Assert - both succeed with same result
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()

    def test_sync_user_invalid_uuid(self, test_client: TestClient, sample_user_data):
        """Test sync with invalid UUID format."""
        # Arrange
        invalid_data = sample_user_data.copy()
        invalid_data["id"] = "not-a-uuid"

        # Act
        response = test_client.post("/api/users/sync", json=invalid_data)

        # Assert
        assert response.status_code == 422

    def test_sync_user_invalid_email(self, test_client: TestClient, sample_user_data):
        """Test sync with invalid email format."""
        # Arrange
        invalid_data = sample_user_data.copy()
        invalid_data["email"] = "not-an-email"

        # Act
        response = test_client.post("/api/users/sync", json=invalid_data)

        # Assert
        assert response.status_code == 422

    def test_sync_user_missing_required_field(
        self, test_client: TestClient, sample_user_data
    ):
        """Test sync with missing required field (email)."""
        # Arrange
        incomplete_data = sample_user_data.copy()
        del incomplete_data["email"]

        # Act
        response = test_client.post("/api/users/sync", json=incomplete_data)

        # Assert
        assert response.status_code == 422


class TestTripSync:
    """Test POST /api/trips/sync endpoint."""

    def test_sync_trip_create_success(
        self, test_client: TestClient, sample_trip_data, created_user
    ):
        """Test creating a new trip via sync endpoint."""
        # Arrange - user exists, trip data ready

        # Act
        response = test_client.post("/api/trips/sync", json=sample_trip_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["trip_id"] == sample_trip_data["id"]

    def test_sync_trip_update_success(
        self, test_client: TestClient, sample_trip_data, created_trip
    ):
        """Test updating an existing trip via sync endpoint (upsert)."""
        # Arrange - trip already exists
        updated_data = sample_trip_data.copy()
        updated_data["name"] = "Updated Trip Name"
        updated_data["destination"] = "New York, NY"

        # Act
        response = test_client.post("/api/trips/sync", json=updated_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_sync_trip_idempotent(
        self, test_client: TestClient, sample_trip_data, created_trip
    ):
        """Test that syncing the same trip multiple times is idempotent."""
        # Arrange - trip already exists

        # Act - sync same data twice
        response1 = test_client.post("/api/trips/sync", json=sample_trip_data)
        response2 = test_client.post("/api/trips/sync", json=sample_trip_data)

        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()

    def test_sync_trip_nonexistent_user(
        self, test_client: TestClient, sample_trip_data
    ):
        """Test sync trip with non-existent user (foreign key violation)."""
        # Arrange - user doesn't exist (created_user fixture not used)

        # Act
        response = test_client.post("/api/trips/sync", json=sample_trip_data)

        # Assert
        assert response.status_code == 404
        assert "User" in response.json()["detail"]

    def test_sync_trip_invalid_date_format(
        self, test_client: TestClient, sample_trip_data, created_user
    ):
        """Test sync with invalid date format."""
        # Arrange
        invalid_data = sample_trip_data.copy()
        invalid_data["start_date"] = "invalid-date"

        # Act
        response = test_client.post("/api/trips/sync", json=invalid_data)

        # Assert
        assert response.status_code == 422

    def test_sync_trip_iso_datetime_format(
        self, test_client: TestClient, sample_trip_data, created_user
    ):
        """Test sync with ISO 8601 datetime format (should parse to date)."""
        # Arrange
        iso_data = sample_trip_data.copy()
        iso_data["start_date"] = "2026-09-04T00:00:00Z"
        iso_data["end_date"] = "2026-10-05T00:00:00Z"

        # Act
        response = test_client.post("/api/trips/sync", json=iso_data)

        # Assert
        assert response.status_code == 200


class TestTripDelete:
    """Test DELETE /api/trips/{trip_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_trip_success(
        self, test_client: TestClient, created_trip, db_session: AsyncSession
    ):
        """Test deleting a trip."""
        # Arrange
        trip_id = str(created_trip.id)

        # Act
        response = test_client.delete(f"/api/trips/{trip_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify trip is actually deleted
        result = await db_session.execute(
            select(Trip).where(Trip.id == created_trip.id)
        )
        deleted_trip = result.scalar_one_or_none()
        assert deleted_trip is None

    def test_delete_trip_idempotent(self, test_client: TestClient, created_trip):
        """Test that deleting the same trip twice is idempotent."""
        # Arrange
        trip_id = str(created_trip.id)

        # Act - delete twice
        response1 = test_client.delete(f"/api/trips/{trip_id}")
        response2 = test_client.delete(f"/api/trips/{trip_id}")

        # Assert - both succeed
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["success"] is True
        assert response2.json()["success"] is True

    def test_delete_trip_nonexistent(self, test_client: TestClient):
        """Test deleting a non-existent trip (should still return success)."""
        # Arrange
        nonexistent_id = str(uuid.uuid4())

        # Act
        response = test_client.delete(f"/api/trips/{nonexistent_id}")

        # Assert - idempotent, returns success
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_trip_invalid_uuid(self, test_client: TestClient):
        """Test delete with invalid UUID format."""
        # Arrange
        invalid_id = "not-a-uuid"

        # Act
        response = test_client.delete(f"/api/trips/{invalid_id}")

        # Assert
        assert response.status_code == 422


class TestTripMemberSync:
    """Test POST /api/trips/{trip_id}/members/sync endpoint."""

    def test_sync_member_create_success(
        self,
        test_client: TestClient,
        created_trip,
        created_user,
        sample_trip_member_data,
    ):
        """Test adding a member to a trip."""
        # Arrange
        trip_id = str(created_trip.id)

        # Act
        response = test_client.post(
            f"/api/trips/{trip_id}/members/sync", json=sample_trip_member_data
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["trip_id"] == trip_id
        assert data["user_id"] == sample_trip_member_data["user_id"]

    def test_sync_member_update_role(
        self,
        test_client: TestClient,
        created_trip,
        created_user,
        sample_trip_member_data,
    ):
        """Test updating a member's role via upsert."""
        # Arrange - create member first
        trip_id = str(created_trip.id)
        test_client.post(
            f"/api/trips/{trip_id}/members/sync", json=sample_trip_member_data
        )

        # Update role
        updated_data = sample_trip_member_data.copy()
        updated_data["role"] = "organizer"

        # Act
        response = test_client.post(
            f"/api/trips/{trip_id}/members/sync", json=updated_data
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_sync_member_idempotent(
        self,
        test_client: TestClient,
        created_trip,
        created_user,
        sample_trip_member_data,
    ):
        """Test that syncing the same member multiple times is idempotent."""
        # Arrange
        trip_id = str(created_trip.id)

        # Act - sync twice
        response1 = test_client.post(
            f"/api/trips/{trip_id}/members/sync", json=sample_trip_member_data
        )
        response2 = test_client.post(
            f"/api/trips/{trip_id}/members/sync", json=sample_trip_member_data
        )

        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()

    def test_sync_member_nonexistent_user(
        self, test_client: TestClient, created_trip, sample_trip_member_data
    ):
        """Test sync with non-existent user."""
        # Arrange - user doesn't exist
        trip_id = str(created_trip.id)
        invalid_data = sample_trip_member_data.copy()
        invalid_data["user_id"] = str(uuid.uuid4())

        # Act
        response = test_client.post(
            f"/api/trips/{trip_id}/members/sync", json=invalid_data
        )

        # Assert
        assert response.status_code == 404
        assert "User" in response.json()["detail"]

    def test_sync_member_nonexistent_trip(
        self, test_client: TestClient, created_user, sample_trip_member_data
    ):
        """Test sync with non-existent trip."""
        # Arrange
        nonexistent_trip_id = str(uuid.uuid4())

        # Act
        response = test_client.post(
            f"/api/trips/{nonexistent_trip_id}/members/sync",
            json=sample_trip_member_data,
        )

        # Assert
        assert response.status_code == 404
        assert "Trip" in response.json()["detail"]


class TestTripMemberRemove:
    """Test DELETE /api/trips/{trip_id}/members/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_remove_member_success(
        self,
        test_client: TestClient,
        created_trip,
        created_user,
        sample_trip_member_data,
        db_session: AsyncSession,
    ):
        """Test removing a member from a trip."""
        # Arrange - add member first
        trip_id = str(created_trip.id)
        user_id = sample_trip_member_data["user_id"]
        test_client.post(
            f"/api/trips/{trip_id}/members/sync", json=sample_trip_member_data
        )

        # Act
        response = test_client.delete(f"/api/trips/{trip_id}/members/{user_id}")

        # Assert
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify membership is actually deleted
        result = await db_session.execute(
            select(TripTraveler).where(
                TripTraveler.trip_id == created_trip.id,
                TripTraveler.user_id == created_user.id,
            )
        )
        membership = result.scalar_one_or_none()
        assert membership is None

    def test_remove_member_idempotent(
        self,
        test_client: TestClient,
        created_trip,
        created_user,
        sample_trip_member_data,
    ):
        """Test that removing the same member twice is idempotent."""
        # Arrange - add member first
        trip_id = str(created_trip.id)
        user_id = sample_trip_member_data["user_id"]
        test_client.post(
            f"/api/trips/{trip_id}/members/sync", json=sample_trip_member_data
        )

        # Act - remove twice
        response1 = test_client.delete(f"/api/trips/{trip_id}/members/{user_id}")
        response2 = test_client.delete(f"/api/trips/{trip_id}/members/{user_id}")

        # Assert - both succeed
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["success"] is True
        assert response2.json()["success"] is True

    def test_remove_member_nonexistent(self, test_client: TestClient, created_trip):
        """Test removing a non-existent member (should still succeed)."""
        # Arrange
        trip_id = str(created_trip.id)
        nonexistent_user_id = str(uuid.uuid4())

        # Act
        response = test_client.delete(
            f"/api/trips/{trip_id}/members/{nonexistent_user_id}"
        )

        # Assert - idempotent, returns success
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_remove_member_invalid_uuid(self, test_client: TestClient, created_trip):
        """Test remove with invalid UUID format."""
        # Arrange
        trip_id = str(created_trip.id)
        invalid_user_id = "not-a-uuid"

        # Act
        response = test_client.delete(f"/api/trips/{trip_id}/members/{invalid_user_id}")

        # Assert
        assert response.status_code == 422


class TestMessageFeedback:
    """Test PATCH /api/messages/{message_id}/feedback endpoint."""

    def test_update_feedback_success(
        self, test_client: TestClient, created_message, sample_message_feedback_data
    ):
        """Test updating message feedback."""
        # Arrange
        message_id = str(created_message.id)

        # Act
        response = test_client.patch(
            f"/api/messages/{message_id}/feedback", json=sample_message_feedback_data
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message_id"] == message_id

    def test_update_feedback_thumbs_down(
        self, test_client: TestClient, created_message
    ):
        """Test updating feedback to thumbs down."""
        # Arrange
        message_id = str(created_message.id)
        feedback_data = {"feedback": "down"}

        # Act
        response = test_client.patch(
            f"/api/messages/{message_id}/feedback", json=feedback_data
        )

        # Assert
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_update_feedback_toggle(
        self, test_client: TestClient, created_message, sample_message_feedback_data
    ):
        """Test toggling feedback (up -> down -> up)."""
        # Arrange
        message_id = str(created_message.id)

        # Act - set to up
        response1 = test_client.patch(
            f"/api/messages/{message_id}/feedback", json=sample_message_feedback_data
        )

        # Toggle to down
        response2 = test_client.patch(
            f"/api/messages/{message_id}/feedback", json={"feedback": "down"}
        )

        # Toggle back to up
        response3 = test_client.patch(
            f"/api/messages/{message_id}/feedback", json=sample_message_feedback_data
        )

        # Assert - all succeed
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

    def test_update_feedback_nonexistent_message(self, test_client: TestClient):
        """Test updating feedback for non-existent message."""
        # Arrange
        nonexistent_id = str(uuid.uuid4())
        feedback_data = {"feedback": "up"}

        # Act
        response = test_client.patch(
            f"/api/messages/{nonexistent_id}/feedback", json=feedback_data
        )

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_feedback_invalid_value(
        self, test_client: TestClient, created_message
    ):
        """Test updating with invalid feedback value."""
        # Arrange
        message_id = str(created_message.id)
        invalid_data = {"feedback": "invalid"}

        # Act
        response = test_client.patch(
            f"/api/messages/{message_id}/feedback", json=invalid_data
        )

        # Assert
        assert response.status_code == 422

    def test_update_feedback_invalid_uuid(self, test_client: TestClient):
        """Test update with invalid UUID format."""
        # Arrange
        invalid_id = "not-a-uuid"
        feedback_data = {"feedback": "up"}

        # Act
        response = test_client.patch(
            f"/api/messages/{invalid_id}/feedback", json=feedback_data
        )

        # Assert
        assert response.status_code == 422
