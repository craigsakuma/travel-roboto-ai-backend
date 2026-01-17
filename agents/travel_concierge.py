"""
Travel Concierge Agent - Conversational travel assistant.

Handles user-facing chat interactions about trips with tool calling support.
"""

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import BaseLLM
from tools import ToolRegistry
from utils.logging import get_agent_logger

logger = get_agent_logger("travel_concierge")


class TravelConciergeAgent:
    """
    Travel Concierge agent for conversational trip planning.

    Handles natural language conversations about trips, with tool calling
    for retrieving trip details and other travel information.
    """

    def __init__(
        self,
        llm: BaseLLM,
        tool_registry: ToolRegistry,
        db: AsyncSession,
        prompts_dir: Path | None = None,
    ):
        """
        Initialize Travel Concierge agent.

        Args:
            llm: LLM instance to use for generation
            tool_registry: Registry of available tools
            db: Database session for tool execution
            prompts_dir: Directory containing prompt templates (defaults to agents/prompts/travel_concierge)
        """
        self.llm = llm
        self.tool_registry = tool_registry
        self.db = db

        # Load system prompt
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent / "prompts" / "travel_concierge"
        self.prompts_dir = prompts_dir
        self.system_prompt = self._load_system_prompt()

        logger.logger.info(
            f"Initialized TravelConciergeAgent with {len(tool_registry)} tools"
        )

    def _load_system_prompt(self) -> str:
        """
        Load the active system prompt version.

        Returns:
            System prompt text

        Raises:
            FileNotFoundError: If prompt files don't exist
        """
        # Read active version
        active_path = self.prompts_dir / "active.json"
        with open(active_path) as f:
            active_config = json.load(f)

        version = active_config["version"]
        logger.logger.debug(f"Loading prompt version: {version}")

        # Read prompt file
        prompt_path = self.prompts_dir / f"{version}_system.txt"
        with open(prompt_path) as f:
            prompt = f.read()

        return prompt

    async def chat(
        self,
        user_message: str,
        conversation_history: list[BaseMessage] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Process a user message and generate a response.

        Args:
            user_message: User's message text
            conversation_history: Previous messages in the conversation

        Returns:
            Tuple of (response_text, metadata) where metadata includes:
            - tool_calls: List of tools called
            - model_info: Model provider and name
            - tokens: Token usage information
        """
        logger.logger.info("Processing chat message", extra={"user_message": user_message})

        # Build message list
        messages: list[BaseMessage] = []

        # Add system message
        messages.append(SystemMessage(content=self.system_prompt))

        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)

        # Add user message
        messages.append(HumanMessage(content=user_message))

        # Generate response with tool calling support
        response_text, tool_calls = await self._generate_with_tools(messages)

        # Get metrics
        metrics = self.llm.get_last_metrics()

        metadata = {
            "tool_calls": tool_calls,
            "model_info": {
                "provider": self.llm.provider_name,
                "model": self.llm.model,
            },
            "tokens": {
                "prompt": metrics.prompt_tokens if metrics else None,
                "completion": metrics.completion_tokens if metrics else None,
                "total": metrics.total_tokens if metrics else None,
            },
        }

        logger.logger.info(
            "Generated response",
            extra={
                "response_length": len(response_text),
                "tool_calls_count": len(tool_calls),
            },
        )

        return response_text, metadata

    async def _generate_with_tools(
        self, messages: list[BaseMessage]
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Generate response with tool calling support.

        Implements a simple tool calling loop:
        1. Call LLM
        2. If tool calls requested, execute tools and feed results back
        3. Repeat until LLM responds without tool calls

        Args:
            messages: Conversation messages

        Returns:
            Tuple of (final_response, tool_calls_made)
        """
        tool_calls_made: list[dict[str, Any]] = []
        max_iterations = 5  # Prevent infinite loops

        for iteration in range(max_iterations):
            logger.logger.debug(f"Tool calling iteration {iteration + 1}")

            # Generate response
            # Note: Full tool calling integration requires provider-specific handling
            # For Phase 1 MVP, we'll use a simplified approach
            response = await self.llm.agenerate(messages)

            # Check if response contains tool call requests
            # This is a simplified implementation - full version would parse
            # structured tool calls from the LLM response
            tool_call_pattern = "get_trip_details"
            if tool_call_pattern not in response.lower():
                # No tool calls, return final response
                return response, tool_calls_made

            # For Phase 1 MVP: If we detect a tool call pattern, this is where
            # we would execute tools and continue the loop
            # TODO: Implement full tool calling in Phase 2
            logger.logger.warning(
                "Tool call detected but full tool calling not yet implemented"
            )
            return response, tool_calls_made

        # Max iterations reached
        logger.logger.warning(f"Max tool calling iterations ({max_iterations}) reached")
        return response, tool_calls_made
