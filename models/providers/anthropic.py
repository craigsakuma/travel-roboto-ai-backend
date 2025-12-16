"""
Anthropic LLM provider implementation.

Supports Claude models via LangChain.
"""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable

from models.base import BaseLLM
from utils.logging import get_agent_logger

logger = get_agent_logger("anthropic_provider")


class AnthropicLLM(BaseLLM):
    """
    Anthropic (Claude) provider implementation.

    Supports models: claude-sonnet-4, claude-opus-4, claude-haiku-4
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-20250514",
        temperature: float = 0.2,
        timeout: int = 30,
        max_retries: int = 2,
        api_key: str | None = None,
    ):
        """
        Initialize Anthropic LLM provider.

        Args:
            model: Claude model name
            temperature: Sampling temperature (0.0-1.0 for Claude)
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            api_key: Anthropic API key (if None, uses ANTHROPIC_API_KEY env var)
        """
        super().__init__(model, temperature, timeout, max_retries)

        if not api_key:
            raise ValueError(
                "Anthropic API key is required. Set ANTHROPIC_API_KEY env var or pass api_key parameter."
            )

        self._client = ChatAnthropic(
            model=model,
            temperature=temperature,
            anthropic_api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

        logger.logger.debug(
            f"Initialized Anthropic provider: model={model}, temperature={temperature}"
        )

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def get_runnable(self) -> Runnable:
        """
        Return LangChain Runnable for use in LCEL chains.

        Example:
            chain = prompt | llm.get_runnable() | StrOutputParser()
        """
        return self._client | StrOutputParser()

    async def agenerate(self, messages: list[BaseMessage], **kwargs: Any) -> str:
        """
        Generate completion from messages asynchronously.

        Args:
            messages: List of LangChain messages
            **kwargs: Additional Anthropic parameters (e.g., max_tokens, stop_sequences)

        Returns:
            str: Generated text response
        """
        try:
            # Invoke the LangChain client
            response = await self._client.ainvoke(messages, **kwargs)

            # Extract usage metadata if available
            if hasattr(response, "response_metadata"):
                usage = response.response_metadata.get("usage", {})
                self._record_metrics(
                    prompt_tokens=usage.get("input_tokens"),
                    completion_tokens=usage.get("output_tokens"),
                )

            # Extract text content
            if hasattr(response, "content"):
                return response.content
            return str(response)

        except Exception as e:
            logger.error(e, context="agenerate_failed", model=self.model)
            raise

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate cost in USD based on Anthropic pricing (as of Dec 2024).

        Pricing (per 1M tokens):
        - claude-sonnet-4: $3.00 input, $15.00 output
        - claude-opus-4: $15.00 input, $75.00 output
        - claude-haiku-4: $0.25 input, $1.25 output
        """
        pricing = {
            "claude-sonnet-4-20250514": (3.00, 15.00),
            "claude-opus-4-20250514": (15.00, 75.00),
            "claude-haiku-4-20250514": (0.25, 1.25),
        }

        # Default to sonnet pricing if model not found
        input_price, output_price = pricing.get(self.model, (3.00, 15.00))

        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price

        return input_cost + output_cost
