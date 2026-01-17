"""
Anthropic Claude provider implementation.

Uses Anthropic SDK directly, wrapped to match the BaseLLM interface.
"""

import os
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from models.base import BaseLLM, LLMCallMetrics

# Lazy import to avoid requiring anthropic if not used
try:
    import anthropic
except ImportError:
    anthropic = None


class ClaudeProvider(BaseLLM):
    """
    Anthropic Claude provider.

    Supports Claude 3.5 Sonnet and other Anthropic models.
    """

    # Pricing per 1M tokens (as of Jan 2025)
    PRICING = {
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    }

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: str | None = None,
        temperature: float = 0.7,
        timeout: int = 30,
        max_retries: int = 2,
        max_tokens: int = 4096,
    ):
        """
        Initialize Claude provider.

        Args:
            model: Claude model name
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            temperature: Sampling temperature
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            max_tokens: Maximum tokens to generate
        """
        super().__init__(model, temperature, timeout, max_retries)

        if anthropic is None:
            raise ImportError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY env var "
                "or pass api_key parameter."
            )

        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(
            api_key=self.api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def get_runnable(self) -> Runnable:
        """
        Return a simple runnable that calls agenerate.

        For more advanced LangChain integration, could return ChatAnthropic,
        but this keeps dependencies minimal.
        """
        # Simple wrapper to make this compatible with LangChain chains
        from langchain_core.runnables import RunnableLambda

        async def _invoke(messages: list[BaseMessage]) -> str:
            return await self.agenerate(messages)

        return RunnableLambda(_invoke)

    async def agenerate(self, messages: list[BaseMessage], **kwargs: Any) -> str:
        """
        Generate completion from Claude.

        Args:
            messages: List of LangChain messages
            **kwargs: Additional parameters (system, tools, etc.)

        Returns:
            Generated text response
        """
        # Convert LangChain messages to Anthropic format
        anthropic_messages, system_prompt = self._convert_messages(messages)

        # Prepare request parameters
        request_params = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        # Add system prompt if present
        if system_prompt:
            request_params["system"] = system_prompt

        # Add tools if provided
        if "tools" in kwargs:
            request_params["tools"] = kwargs["tools"]

        # Call Anthropic API
        response = await self.client.messages.create(**request_params)

        # Record metrics
        self._record_metrics(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        )

        # Extract text content
        content_blocks = [
            block.text for block in response.content if hasattr(block, "text")
        ]
        return "\n".join(content_blocks) if content_blocks else ""

    def _convert_messages(
        self, messages: list[BaseMessage]
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Convert LangChain messages to Anthropic format.

        Anthropic requires:
        - System messages separate from conversation
        - Messages must alternate user/assistant
        - First message must be from user

        Returns:
            tuple: (anthropic_messages, system_prompt)
        """
        system_prompt = None
        anthropic_messages = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                # Anthropic uses separate system parameter
                system_prompt = msg.content
            elif isinstance(msg, HumanMessage):
                anthropic_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                anthropic_messages.append({"role": "assistant", "content": msg.content})
            else:
                # For other message types, treat as user message
                anthropic_messages.append({"role": "user", "content": msg.content})

        return anthropic_messages, system_prompt

    def calculate_cost(self, usage: LLMCallMetrics) -> float:
        """
        Calculate cost for this request using Anthropic pricing.

        Args:
            usage: Metrics with token counts

        Returns:
            Cost in USD
        """
        if self.model not in self.PRICING:
            # Unknown model, return 0
            return 0.0

        pricing = self.PRICING[self.model]
        input_cost = (usage.prompt_tokens or 0) / 1_000_000 * pricing["input"]
        output_cost = (usage.completion_tokens or 0) / 1_000_000 * pricing["output"]

        return input_cost + output_cost

    def __repr__(self) -> str:
        return (
            f"ClaudeProvider("
            f"model={self.model}, "
            f"temperature={self.temperature}, "
            f"max_tokens={self.max_tokens})"
        )
