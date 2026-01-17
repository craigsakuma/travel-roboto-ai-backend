"""Tests for tool registry and trip tools.

Tests tool registration, execution, and trip-related tools.
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Trip, TripTraveler, User
from tools import ToolRegistry, get_trip_details, register_trip_tools


@pytest_asyncio.fixture
async def async_engine():
    """Create an in-memory async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create only the tables needed for trip tools tests
    async with engine.begin() as conn:
        def create_tables(connection):
            User.__table__.create(connection, checkfirst=True)
            Trip.__table__.create(connection, checkfirst=True)
            TripTraveler.__table__.create(connection, checkfirst=True)

        await conn.run_sync(create_tables)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def session(async_engine):
    """Create a database session for testing."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


class TestToolRegistry:
    """Test ToolRegistry functionality."""

    def test_create_registry(self):
        """Test creating an empty tool registry."""
        registry = ToolRegistry()
        assert len(registry) == 0

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()

        async def my_tool(param1: str) -> str:
            return f"Result: {param1}"

        registry.register(
            name="my_tool",
            description="A test tool",
            parameters_schema={
                "type": "object",
                "properties": {"param1": {"type": "string"}},
                "required": ["param1"],
            },
            function=my_tool,
        )

        assert len(registry) == 1
        assert "my_tool" in registry

    def test_register_duplicate_tool(self):
        """Test that registering duplicate tool raises error."""
        registry = ToolRegistry()

        async def tool1():
            pass

        async def tool2():
            pass

        registry.register(
            name="duplicate",
            description="First tool",
            parameters_schema={},
            function=tool1,
        )

        with pytest.raises(ValueError, match="already registered"):
            registry.register(
                name="duplicate",
                description="Second tool",
                parameters_schema={},
                function=tool2,
            )

    def test_get_tool(self):
        """Test retrieving a registered tool."""
        registry = ToolRegistry()

        async def my_tool():
            pass

        registry.register(
            name="test_tool",
            description="Test tool",
            parameters_schema={},
            function=my_tool,
        )

        tool = registry.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"
        assert tool.description == "Test tool"

    def test_get_nonexistent_tool(self):
        """Test retrieving a tool that doesn't exist."""
        registry = ToolRegistry()
        tool = registry.get_tool("nonexistent")
        assert tool is None

    def test_get_all_tools(self):
        """Test retrieving all registered tools."""
        registry = ToolRegistry()

        async def tool1():
            pass

        async def tool2():
            pass

        registry.register("tool1", "First tool", {}, tool1)
        registry.register("tool2", "Second tool", {}, tool2)

        all_tools = registry.get_all_tools()
        assert len(all_tools) == 2
        assert {t.name for t in all_tools} == {"tool1", "tool2"}

    def test_get_tools_for_langchain(self):
        """Test getting tools in LangChain format."""
        registry = ToolRegistry()

        async def my_tool(param: str) -> str:
            return param

        registry.register(
            name="my_tool",
            description="A test tool",
            parameters_schema={
                "type": "object",
                "properties": {"param": {"type": "string"}},
                "required": ["param"],
            },
            function=my_tool,
        )

        langchain_tools = registry.get_tools_for_langchain()

        assert len(langchain_tools) == 1
        assert langchain_tools[0]["type"] == "function"
        assert langchain_tools[0]["function"]["name"] == "my_tool"
        assert langchain_tools[0]["function"]["description"] == "A test tool"
        assert "param" in langchain_tools[0]["function"]["parameters"]["properties"]

    def test_get_tools_for_anthropic(self):
        """Test getting tools in Anthropic format."""
        registry = ToolRegistry()

        async def my_tool(param: str) -> str:
            return param

        registry.register(
            name="my_tool",
            description="A test tool",
            parameters_schema={
                "type": "object",
                "properties": {"param": {"type": "string"}},
                "required": ["param"],
            },
            function=my_tool,
        )

        anthropic_tools = registry.get_tools_for_anthropic()

        assert len(anthropic_tools) == 1
        assert anthropic_tools[0]["name"] == "my_tool"
        assert anthropic_tools[0]["description"] == "A test tool"
        assert "param" in anthropic_tools[0]["input_schema"]["properties"]

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """Test executing a registered tool."""
        registry = ToolRegistry()

        async def add_numbers(a: int, b: int) -> int:
            return a + b

        registry.register(
            name="add",
            description="Add two numbers",
            parameters_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
            function=add_numbers,
        )

        result = await registry.execute_tool("add", a=5, b=3)
        assert result == 8

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """Test executing a tool that doesn't exist."""
        registry = ToolRegistry()

        with pytest.raises(ValueError, match="not found in registry"):
            await registry.execute_tool("nonexistent", param="value")


class TestTripTools:
    """Test trip-related tools."""

    def test_register_trip_tools(self):
        """Test registering trip tools in registry."""
        registry = ToolRegistry()
        register_trip_tools(registry)

        assert len(registry) > 0
        assert "get_trip_details" in registry

        tool = registry.get_tool("get_trip_details")
        assert tool is not None
        assert "trip" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_get_trip_details_success(self, session):
        """Test successfully retrieving trip details."""
        # Create test data
        user_id = uuid.uuid4()
        trip_id = uuid.uuid4()

        user = User(
            id=user_id,
            email="test@example.com",
            first_name="John",
            last_name="Doe",
        )
        session.add(user)

        trip = Trip(
            id=trip_id,
            name="Tokyo Adventure",
            destination="Tokyo, Japan",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 10),
            created_by_user_id=user_id,
            summary="A wonderful trip to Tokyo",
            structured_data={
                "flights": [
                    {
                        "airline": "United",
                        "flight_number": "UA123",
                        "departure": "SFO",
                        "arrival": "NRT",
                    }
                ],
                "hotels": [{"name": "Tokyo Grand Hotel", "nights": 9}],
            },
        )
        session.add(trip)

        traveler = TripTraveler(
            trip_id=trip_id,
            user_id=user_id,
            role="organizer",
        )
        session.add(traveler)

        await session.commit()

        # Test get_trip_details
        result = await get_trip_details(str(trip_id), session)

        assert result["id"] == str(trip_id)
        assert result["name"] == "Tokyo Adventure"
        assert result["destination"] == "Tokyo, Japan"
        assert result["start_date"] == "2025-06-01"
        assert result["end_date"] == "2025-06-10"
        assert result["summary"] == "A wonderful trip to Tokyo"
        assert len(result["travelers"]) == 1
        assert result["travelers"][0]["user_id"] == str(user_id)
        assert result["travelers"][0]["role"] == "organizer"
        assert "flights" in result["structured_data"]
        assert len(result["structured_data"]["flights"]) == 1

    @pytest.mark.asyncio
    async def test_get_trip_details_not_found(self, session):
        """Test retrieving non-existent trip."""
        trip_id = str(uuid.uuid4())

        with pytest.raises(ValueError, match="Trip not found"):
            await get_trip_details(trip_id, session)

    @pytest.mark.asyncio
    async def test_get_trip_details_invalid_uuid(self, session):
        """Test retrieving trip with invalid UUID format."""
        with pytest.raises(ValueError, match="Invalid trip_id format"):
            await get_trip_details("not-a-uuid", session)

    @pytest.mark.asyncio
    async def test_get_trip_details_with_multiple_travelers(self, session):
        """Test retrieving trip with multiple travelers."""
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        trip_id = uuid.uuid4()

        # Create users
        user1 = User(id=user1_id, email="user1@example.com")
        user2 = User(id=user2_id, email="user2@example.com")
        session.add_all([user1, user2])

        # Create trip
        trip = Trip(
            id=trip_id,
            name="Group Trip",
            destination="Paris, France",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 7),
            created_by_user_id=user1_id,
        )
        session.add(trip)

        # Create travelers
        traveler1 = TripTraveler(
            trip_id=trip_id,
            user_id=user1_id,
            role="organizer",
        )
        traveler2 = TripTraveler(
            trip_id=trip_id,
            user_id=user2_id,
            role="participant",
        )
        session.add_all([traveler1, traveler2])

        await session.commit()

        # Test get_trip_details
        result = await get_trip_details(str(trip_id), session)

        assert len(result["travelers"]) == 2
        traveler_roles = {t["role"] for t in result["travelers"]}
        assert "organizer" in traveler_roles
        assert "participant" in traveler_roles

    @pytest.mark.asyncio
    async def test_execute_get_trip_details_via_registry(self, session):
        """Test executing get_trip_details through the registry."""
        # Create test trip
        user_id = uuid.uuid4()
        trip_id = uuid.uuid4()

        user = User(id=user_id, email="test@example.com")
        trip = Trip(
            id=trip_id,
            name="Test Trip",
            destination="Test Destination",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            created_by_user_id=user_id,
        )
        session.add_all([user, trip])
        await session.commit()

        # Register tools and execute
        registry = ToolRegistry()
        register_trip_tools(registry)

        result = await registry.execute_tool("get_trip_details", trip_id=str(trip_id), db=session)

        assert result["name"] == "Test Trip"
        assert result["destination"] == "Test Destination"
