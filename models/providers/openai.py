"""
OpenAI LLM provider implementation.

Supports GPT-5, GPT-4o, and other OpenAI models via LangChain.
"""

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from models.base import BaseLLM
from utils.logging import get_agent_logger

logger = get_agent_logger("openai_provider")


class OpenAILLM(BaseLLM):
    """
    OpenAI provider implementation.

    Supports models: gpt-5, gpt-5-mini (default), gpt-5-nano, gpt-4o, gpt-4o-mini
    """

    def __init__(
        self,
        model: str = "gpt-5-mini",
        temperature: float = 0.2,
        timeout: int = 30,
        max_retries: int = 2,
        api_key: str | None = None,
    ):
        """
        Initialize OpenAI LLM provider.

        Args:
            model: OpenAI model name
            temperature: Sampling temperature (0.0-2.0)
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            api_key: OpenAI API key (if None, uses OPENAI_API_KEY env var)
        """
        super().__init__(model, temperature, timeout, max_retries)

        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY env var or pass api_key parameter."
            )

        self._client = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

        logger.logger.debug(
            f"Initialized OpenAI provider: model={model}, temperature={temperature}"
        )

    @property
    def provider_name(self) -> str:
        return "openai"

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
            **kwargs: Additional OpenAI parameters (e.g., max_tokens, stop)

        Returns:
            str: Generated text response
        """
        try:
            # Invoke the LangChain client
            response = await self._client.ainvoke(messages, **kwargs)

            # Extract usage metadata if available
            if hasattr(response, "response_metadata"):
                usage = response.response_metadata.get("token_usage", {})
                self._record_metrics(
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
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
        Estimate cost in USD based on OpenAI pricing (as of Dec 2025).

        Pricing (per 1M tokens):
        GPT-5 Models (latest, most capable):
        - gpt-5: $1.25 input, $10.00 output
        - gpt-5-mini: $0.25 input, $2.00 output (default - most economical)
        - gpt-5-nano: $0.05 input, $0.40 output

        GPT-4o Models (legacy):
        - gpt-4o: $2.50 input, $10.00 output
        - gpt-4o-mini: $0.15 input, $0.60 output

        Note: All GPT-5 models include 90% discount on cached tokens.
        """
        pricing = {
            # GPT-5 models (2025)
            "gpt-5": (1.25, 10.00),
            "gpt-5-mini": (0.25, 2.00),
            "gpt-5-nano": (0.05, 0.40),
            # GPT-4o models (legacy)
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            # Older models
            "gpt-4-turbo": (10.00, 30.00),
            "gpt-3.5-turbo": (0.50, 1.50),
        }

        # Default to gpt-5-mini pricing (most economical)
        input_price, output_price = pricing.get(self.model, (0.25, 2.00))

        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price

        return input_cost + output_cost
