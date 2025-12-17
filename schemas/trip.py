"""
Trip data and travel information schemas.

Defines data models for:
- Trip metadata
- Flight information
- Hotel reservations
- Activities and itinerary
- Consolidated trip data
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.common import Source, Timestamp


class TripMetadata(BaseModel):
    """
    Basic trip information and metadata.

    High-level trip details including participants, dates, and destination.
    """

    trip_id: str = Field(description="Unique trip identifier", examples=["trip_tokyo2025"])
    name: str = Field(
        description="Human-readable trip name", examples=["Tokyo Christmas Vacation 2025"]
    )
    destination: str = Field(
        description="Primary destination(s)", examples=["Tokyo, Japan", "Paris and London"]
    )
    start_date: datetime | None = Field(
        default=None, description="Trip start date (departure)"
    )
    end_date: datetime | None = Field(default=None, description="Trip end date (return)")
    participants: list[str] = Field(
        default_factory=list,
        description="List of trip participants (names or user IDs)",
        examples=[["John Doe", "Jane Smith"]],
    )
    created_at: Timestamp = Field(
        description="When the trip was created",
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: Timestamp = Field(
        description="Last update timestamp",
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @field_validator("trip_id")
    @classmethod
    def trip_id_not_empty(cls, v: str) -> str:
        """Ensure trip_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Trip ID cannot be empty")
        return v.strip()

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Ensure trip name is not empty."""
        if not v or not v.strip():
            raise ValueError("Trip name cannot be empty")
        return v.strip()

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: datetime | None, info) -> datetime | None:
        """Ensure end_date is after start_date if both are provided."""
        if v is not None and "start_date" in info.data:
            start_date = info.data.get("start_date")
            if start_date is not None and v < start_date:
                raise ValueError("Trip end_date must be after start_date")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "trip_id": "trip_tokyo2025",
                    "name": "Tokyo Christmas Vacation 2025",
                    "destination": "Tokyo, Japan",
                    "start_date": "2025-12-20T00:00:00Z",
                    "end_date": "2025-12-28T00:00:00Z",
                    "participants": ["John Doe", "Jane Smith"],
                    "created_at": "2025-12-01T10:00:00Z",
                    "updated_at": "2025-12-16T14:30:00Z",
                }
            ]
        }
    )


class FlightInfo(BaseModel):
    """
    Flight information extracted from confirmations or bookings.

    Represents a single flight segment with all relevant details.
    """

    airline: str = Field(description="Airline name", examples=["United Airlines", "ANA"])
    flight_number: str = Field(description="Flight number", examples=["UA 123", "NH 7"])
    departure_airport: str = Field(
        description="Departure airport code or name", examples=["SFO", "San Francisco (SFO)"]
    )
    arrival_airport: str = Field(
        description="Arrival airport code or name", examples=["NRT", "Tokyo Narita (NRT)"]
    )
    departure_time: datetime = Field(description="Scheduled departure date and time")
    arrival_time: datetime = Field(description="Scheduled arrival date and time")
    passenger: str = Field(
        description="Passenger name on this flight", examples=["John Doe"]
    )
    confirmation_code: str | None = Field(
        default=None, description="Airline confirmation code", examples=["ABC123"]
    )
    seat: str | None = Field(default=None, description="Seat assignment", examples=["12A"])
    source: Source = Field(description="Source of this flight information")

    @field_validator("airline", "passenger")
    @classmethod
    def string_not_empty(cls, v: str) -> str:
        """Ensure required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("arrival_time")
    @classmethod
    def arrival_after_departure(cls, v: datetime, info) -> datetime:
        """Ensure arrival_time is after departure_time."""
        if "departure_time" in info.data:
            departure_time = info.data.get("departure_time")
            if departure_time is not None and v <= departure_time:
                raise ValueError("Arrival time must be after departure time")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "airline": "United Airlines",
                    "flight_number": "UA 123",
                    "departure_airport": "San Francisco (SFO)",
                    "arrival_airport": "Tokyo Narita (NRT)",
                    "departure_time": "2025-12-20T19:00:00Z",
                    "arrival_time": "2025-12-21T15:45:00Z",
                    "passenger": "John Doe",
                    "confirmation_code": "ABC123",
                    "seat": "12A",
                    "source": {
                        "type": "email",
                        "description": "United Airlines confirmation email",
                        "timestamp": "2025-12-15T10:00:00Z",
                        "metadata": {"email_id": "msg_abc123"},
                    },
                }
            ]
        }
    )


class HotelInfo(BaseModel):
    """
    Hotel reservation information.

    Represents a hotel booking with check-in/check-out details.
    """

    name: str = Field(
        description="Hotel name", examples=["Park Hyatt Tokyo", "Hotel Okura"]
    )
    address: str | None = Field(
        default=None,
        description="Hotel address",
        examples=["3-7-1-2 Nishi-Shinjuku, Shinjuku-ku, Tokyo"],
    )
    check_in: datetime = Field(description="Check-in date and time")
    check_out: datetime = Field(description="Check-out date and time")
    guest: str = Field(description="Primary guest name", examples=["John Doe"])
    confirmation_code: str | None = Field(
        default=None, description="Hotel confirmation code", examples=["HOTEL123"]
    )
    room_type: str | None = Field(
        default=None, description="Room type", examples=["Deluxe King Room"]
    )
    source: Source = Field(description="Source of this hotel information")

    @field_validator("name", "guest")
    @classmethod
    def string_not_empty(cls, v: str) -> str:
        """Ensure required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("check_out")
    @classmethod
    def checkout_after_checkin(cls, v: datetime, info) -> datetime:
        """Ensure check_out is after check_in."""
        if "check_in" in info.data:
            check_in = info.data.get("check_in")
            if check_in is not None and v <= check_in:
                raise ValueError("Check-out time must be after check-in time")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Park Hyatt Tokyo",
                    "address": "3-7-1-2 Nishi-Shinjuku, Shinjuku-ku, Tokyo",
                    "check_in": "2025-12-20T15:00:00Z",
                    "check_out": "2025-12-25T11:00:00Z",
                    "guest": "John Doe",
                    "confirmation_code": "HOTEL123",
                    "room_type": "Deluxe King Room",
                    "source": {
                        "type": "email",
                        "description": "Hyatt confirmation email",
                        "timestamp": "2025-12-10T14:00:00Z",
                        "metadata": {"email_id": "msg_hotel456"},
                    },
                }
            ]
        }
    )


class ActivityInfo(BaseModel):
    """
    Planned activity or event information.

    Represents a scheduled activity, tour, or event during the trip.
    """

    name: str = Field(
        description="Activity name",
        examples=["TeamLab Borderless Museum", "Tsukiji Fish Market Tour"],
    )
    description: str | None = Field(
        default=None,
        description="Activity description",
        examples=["Interactive digital art museum experience"],
    )
    date: datetime | None = Field(
        default=None, description="Activity date (and optional time)"
    )
    location: str | None = Field(
        default=None, description="Activity location", examples=["Odaiba, Tokyo"]
    )
    participants: list[str] = Field(
        default_factory=list,
        description="Activity participants",
        examples=[["John Doe", "Jane Smith"]],
    )
    confirmation_code: str | None = Field(
        default=None, description="Booking confirmation code", examples=["ACT789"]
    )
    source: Source = Field(description="Source of this activity information")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Ensure activity name is not empty."""
        if not v or not v.strip():
            raise ValueError("Activity name cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "TeamLab Borderless Museum",
                    "description": "Interactive digital art museum experience",
                    "date": "2025-12-22T14:00:00Z",
                    "location": "Odaiba, Tokyo",
                    "participants": ["John Doe", "Jane Smith"],
                    "confirmation_code": "ACT789",
                    "source": {
                        "type": "email",
                        "description": "Viator booking confirmation",
                        "timestamp": "2025-12-12T09:00:00Z",
                        "metadata": {"email_id": "msg_act789"},
                    },
                }
            ]
        }
    )


class TripData(BaseModel):
    """
    Consolidated trip information.

    Aggregates all trip-related data including metadata, flights,
    hotels, and activities. This is the primary data structure
    persisted to Firestore for each trip.
    """

    metadata: TripMetadata = Field(description="Trip metadata and basic information")
    flights: list[FlightInfo] = Field(
        default_factory=list, description="All flight segments for this trip"
    )
    hotels: list[HotelInfo] = Field(
        default_factory=list, description="All hotel reservations for this trip"
    )
    activities: list[ActivityInfo] = Field(
        default_factory=list, description="All planned activities for this trip"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "metadata": {
                        "trip_id": "trip_tokyo2025",
                        "name": "Tokyo Christmas Vacation 2025",
                        "destination": "Tokyo, Japan",
                        "start_date": "2025-12-20T00:00:00Z",
                        "end_date": "2025-12-28T00:00:00Z",
                        "participants": ["John Doe", "Jane Smith"],
                        "created_at": "2025-12-01T10:00:00Z",
                        "updated_at": "2025-12-16T14:30:00Z",
                    },
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
                            "seat": "12A",
                            "source": {
                                "type": "email",
                                "description": "United confirmation",
                                "timestamp": "2025-12-15T10:00:00Z",
                                "metadata": {},
                            },
                        }
                    ],
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
                                "type": "email",
                                "description": "Hyatt confirmation",
                                "timestamp": "2025-12-10T14:00:00Z",
                                "metadata": {},
                            },
                        }
                    ],
                    "activities": [],
                }
            ]
        }
    )
