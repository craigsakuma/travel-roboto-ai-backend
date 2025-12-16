"""
Base interface for LLM providers.

Defines the common interface that all LLM providers (OpenAI, Anthropic, Google) must implement.
This abstraction enables A/B testing and easy provider switching.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable


@dataclass
class LLMCallMetrics:
    """Metrics captured from an LLM API call."""

    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None

    @property
    def total_cost_estimate(self) -> float | None:
        """Rough cost estimate in USD (provider-specific, override in subclasses)."""
        return None


class BaseLLM(ABC):
    """
    Abstract base class for LLM providers.

    All providers (OpenAI, Anthropic, Google) implement this interface to enable:
    - Unified API across providers
    - A/B testing at conversation level
    - Consistent metrics collection
    - Easy provider switching
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.2,
        timeout: int = 30,
        max_retries: int = 2,
    ):
        """
        Initialize base LLM provider.

        Args:
            model: Model name (provider-specific, e.g., "gpt-4o", "claude-sonnet-4")
            temperature: Sampling temperature (0.0-2.0, lower = more deterministic)
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts on failure
        """
        self.model = model
        self.temperature = self._validate_temperature(temperature)
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_metrics: LLMCallMetrics | None = None

    @staticmethod
    def _validate_temperature(temperature: float) -> float:
        """Validate temperature is in valid range."""
        if not (0.0 <= temperature <= 2.0):
            raise ValueError(f"temperature must be between 0.0 and 2.0, got {temperature}")
        return temperature

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic', 'google')."""
        pass

    @abstractmethod
    def get_runnable(self) -> Runnable:
        """
        Return a LangChain Runnable for this LLM.

        This allows integration with LCEL (LangChain Expression Language) chains:
        chain = prompt | llm.get_runnable() | output_parser

        Returns:
            Runnable: LangChain-compatible runnable
        """
        pass

    @abstractmethod
    async def agenerate(self, messages: list[BaseMessage], **kwargs: Any) -> str:
        """
        Async generate completion from messages.

        Args:
            messages: List of LangChain messages (SystemMessage, HumanMessage, AIMessage)
            **kwargs: Provider-specific parameters

        Returns:
            str: Generated text response
        """
        pass

    def get_last_metrics(self) -> LLMCallMetrics | None:
        """Get metrics from the last API call."""
        return self._last_metrics

    def _record_metrics(
        self,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        latency_ms: float | None = None,
    ) -> None:
        """Record metrics from an API call."""
        self._last_metrics = LLMCallMetrics(
            model=self.model,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=(
                (prompt_tokens or 0) + (completion_tokens or 0)
                if prompt_tokens is not None and completion_tokens is not None
                else None
            ),
            latency_ms=latency_ms,
        )

    async def generate_with_metrics(
        self, messages: list[BaseMessage], **kwargs: Any
    ) -> tuple[str, LLMCallMetrics]:
        """
        Generate completion and return both response and metrics.

        Useful for evaluation and monitoring.

        Args:
            messages: List of LangChain messages
            **kwargs: Provider-specific parameters

        Returns:
            tuple[str, LLMCallMetrics]: Generated text and call metrics
        """
        start_time = time.time()
        response = await self.agenerate(messages, **kwargs)
        latency_ms = (time.time() - start_time) * 1000

        # Metrics should have been recorded by agenerate
        if self._last_metrics:
            self._last_metrics.latency_ms = latency_ms

        return response, self._last_metrics or LLMCallMetrics(
            model=self.model,
            provider=self.provider_name,
            latency_ms=latency_ms,
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"model={self.model}, "
            f"temperature={self.temperature}, "
            f"timeout={self.timeout})"
        )
