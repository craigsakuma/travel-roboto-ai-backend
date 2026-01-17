"""Tests for Travel Concierge agent.

Tests agent initialization, chat functionality, and tool integration.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents import TravelConciergeAgent
from db.base import Base
from models.base import LLMCallMetrics
from tools import ToolRegistry, register_trip_tools


@pytest_asyncio.fixture
async def async_engine():
    """Create an in-memory async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    llm = MagicMock()
    llm.model = "test-model"
    llm.provider_name = "test-provider"
    llm.temperature = 0.7

    # Mock agenerate to return a simple response
    async def mock_agenerate(messages, **kwargs):
        return "This is a test response from the LLM."

    llm.agenerate = AsyncMock(side_effect=mock_agenerate)

    # Mock metrics
    llm.get_last_metrics.return_value = LLMCallMetrics(
        model="test-model",
        provider="test-provider",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=500,
    )

    return llm


@pytest.fixture
def tool_registry():
    """Create a tool registry with trip tools."""
    registry = ToolRegistry()
    register_trip_tools(registry)
    return registry


class TestTravelConciergeAgent:
    """Test Travel Concierge agent functionality."""

    def test_initialization(self, mock_llm, tool_registry, session):
        """Test agent initialization."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        assert agent.llm == mock_llm
        assert agent.tool_registry == tool_registry
        assert agent.db == session
        assert agent.system_prompt is not None
        assert len(agent.system_prompt) > 0

    def test_load_system_prompt(self, mock_llm, tool_registry, session):
        """Test loading system prompt from file."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        # Check that system prompt was loaded
        assert "travel assistant" in agent.system_prompt.lower()
        assert "helpful" in agent.system_prompt.lower() or "help" in agent.system_prompt.lower()

    def test_custom_prompts_dir(self, mock_llm, tool_registry, session):
        """Test initializing with custom prompts directory."""
        # Get the default prompts directory
        prompts_dir = Path(__file__).parent.parent / "agents" / "prompts" / "travel_concierge"

        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
            prompts_dir=prompts_dir,
        )

        assert agent.prompts_dir == prompts_dir
        assert agent.system_prompt is not None

    @pytest.mark.asyncio
    async def test_chat_simple_message(self, mock_llm, tool_registry, session):
        """Test simple chat without conversation history."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        response, metadata = await agent.chat(
            user_message="Hello, how are you?",
            conversation_history=None,
        )

        # Verify response
        assert isinstance(response, str)
        assert len(response) > 0
        assert response == "This is a test response from the LLM."

        # Verify metadata
        assert "tool_calls" in metadata
        assert "model_info" in metadata
        assert "tokens" in metadata
        assert metadata["model_info"]["provider"] == "test-provider"
        assert metadata["model_info"]["model"] == "test-model"
        assert metadata["tokens"]["prompt"] == 100
        assert metadata["tokens"]["completion"] == 50
        assert metadata["tokens"]["total"] == 150

        # Verify LLM was called
        mock_llm.agenerate.assert_called_once()
        call_args = mock_llm.agenerate.call_args[0][0]

        # Should have system message and user message
        assert len(call_args) >= 2
        assert isinstance(call_args[0], SystemMessage)
        assert isinstance(call_args[-1], HumanMessage)
        assert call_args[-1].content == "Hello, how are you?"

    @pytest.mark.asyncio
    async def test_chat_with_conversation_history(self, mock_llm, tool_registry, session):
        """Test chat with existing conversation history."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        # Create conversation history
        history = [
            HumanMessage(content="What's the weather like?"),
            AIMessage(content="I don't have access to weather information."),
        ]

        response, metadata = await agent.chat(
            user_message="Can you help me with my trip?",
            conversation_history=history,
        )

        assert isinstance(response, str)
        assert len(response) > 0

        # Verify all messages were included
        call_args = mock_llm.agenerate.call_args[0][0]

        # Should have: system message + 2 history messages + new user message
        assert len(call_args) >= 4
        assert isinstance(call_args[0], SystemMessage)
        assert isinstance(call_args[1], HumanMessage)
        assert call_args[1].content == "What's the weather like?"
        assert isinstance(call_args[2], AIMessage)
        assert call_args[2].content == "I don't have access to weather information."
        assert isinstance(call_args[3], HumanMessage)
        assert call_args[3].content == "Can you help me with my trip?"

    @pytest.mark.asyncio
    async def test_chat_metadata_structure(self, mock_llm, tool_registry, session):
        """Test that metadata has correct structure."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        response, metadata = await agent.chat(
            user_message="Test message",
            conversation_history=None,
        )

        # Verify metadata structure
        assert isinstance(metadata, dict)
        assert "tool_calls" in metadata
        assert "model_info" in metadata
        assert "tokens" in metadata

        # Check model_info structure
        assert "provider" in metadata["model_info"]
        assert "model" in metadata["model_info"]

        # Check tokens structure
        assert "prompt" in metadata["tokens"]
        assert "completion" in metadata["tokens"]
        assert "total" in metadata["tokens"]

    @pytest.mark.asyncio
    async def test_chat_with_empty_message(self, mock_llm, tool_registry, session):
        """Test chat with empty user message."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        # Empty messages should still be processed
        response, metadata = await agent.chat(
            user_message="",
            conversation_history=None,
        )

        assert isinstance(response, str)
        # LLM was still called even with empty message
        mock_llm.agenerate.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_error_propagation(self, mock_llm, tool_registry, session):
        """Test that LLM errors are propagated."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        # Make LLM raise an error
        mock_llm.agenerate.side_effect = Exception("LLM API error")

        with pytest.raises(Exception, match="LLM API error"):
            await agent.chat(
                user_message="Test message",
                conversation_history=None,
            )

    @pytest.mark.asyncio
    async def test_tool_calling_detection(self, mock_llm, tool_registry, session):
        """Test detection of tool calls in LLM response."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        # Mock response with tool call pattern
        async def mock_with_tool_call(messages, **kwargs):
            return "I'll use get_trip_details to fetch that information."

        mock_llm.agenerate = AsyncMock(side_effect=mock_with_tool_call)

        response, metadata = await agent.chat(
            user_message="What's my trip to Tokyo?",
            conversation_history=None,
        )

        # Response should contain the tool call text
        assert "get_trip_details" in response.lower()

    @pytest.mark.asyncio
    async def test_tool_registry_integration(self, mock_llm, tool_registry, session):
        """Test that agent has access to registered tools."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        # Verify tool registry is accessible
        assert agent.tool_registry is not None
        assert len(agent.tool_registry) > 0
        assert "get_trip_details" in agent.tool_registry

    @pytest.mark.asyncio
    async def test_multiple_chats_same_agent(self, mock_llm, tool_registry, session):
        """Test multiple chat calls with same agent instance."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        # First chat
        response1, metadata1 = await agent.chat(
            user_message="First message",
            conversation_history=None,
        )

        # Second chat
        response2, metadata2 = await agent.chat(
            user_message="Second message",
            conversation_history=None,
        )

        # Both should succeed
        assert isinstance(response1, str)
        assert isinstance(response2, str)

        # LLM should have been called twice
        assert mock_llm.agenerate.call_count == 2

    @pytest.mark.asyncio
    async def test_system_prompt_included(self, mock_llm, tool_registry, session):
        """Test that system prompt is included in every chat."""
        agent = TravelConciergeAgent(
            llm=mock_llm,
            tool_registry=tool_registry,
            db=session,
        )

        await agent.chat(
            user_message="Test",
            conversation_history=None,
        )

        call_args = mock_llm.agenerate.call_args[0][0]

        # First message should be system message
        assert isinstance(call_args[0], SystemMessage)
        assert call_args[0].content == agent.system_prompt
