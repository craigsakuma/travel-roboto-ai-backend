"""
Google AI LLM provider implementation.

Supports Gemini models via LangChain.
"""

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI

from models.base import BaseLLM
from utils.logging import get_agent_logger

logger = get_agent_logger("google_provider")


class GoogleLLM(BaseLLM):
    """
    Google AI (Gemini) provider implementation.

    Supports models: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
    """

    def __init__(
        self,
        model: str = "gemini-2.0-flash-exp",
        temperature: float = 0.2,
        timeout: int = 30,
        max_retries: int = 2,
        api_key: str | None = None,
    ):
        """
        Initialize Google AI LLM provider.

        Args:
            model: Gemini model name
            temperature: Sampling temperature (0.0-2.0)
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            api_key: Google API key (if None, uses GOOGLE_API_KEY env var)
        """
        super().__init__(model, temperature, timeout, max_retries)

        if not api_key:
            raise ValueError(
                "Google API key is required. Set GOOGLE_API_KEY env var or pass api_key parameter."
            )

        self._client = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

        logger.logger.debug(
            f"Initialized Google provider: model={model}, temperature={temperature}"
        )

    @property
    def provider_name(self) -> str:
        return "google"

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
            **kwargs: Additional Google parameters (e.g., max_output_tokens, stop_sequences)

        Returns:
            str: Generated text response
        """
        try:
            # Invoke the LangChain client
            response = await self._client.ainvoke(messages, **kwargs)

            # Extract usage metadata if available
            if hasattr(response, "response_metadata"):
                usage = response.response_metadata.get("usage_metadata", {})
                self._record_metrics(
                    prompt_tokens=usage.get("prompt_token_count"),
                    completion_tokens=usage.get("candidates_token_count"),
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
        Estimate cost in USD based on Google AI pricing (as of Dec 2024).

        Pricing (per 1M tokens):
        - gemini-2.0-flash: $0.075 input, $0.30 output (up to 128k context)
        - gemini-1.5-pro: $1.25 input, $5.00 output (up to 128k context)
        - gemini-1.5-flash: $0.075 input, $0.30 output (up to 128k context)
        """
        pricing = {
            "gemini-2.0-flash-exp": (0.075, 0.30),
            "gemini-1.5-pro": (1.25, 5.00),
            "gemini-1.5-flash": (0.075, 0.30),
        }

        # Default to flash pricing if model not found
        input_price, output_price = pricing.get(self.model, (0.075, 0.30))

        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price

        return input_cost + output_cost
