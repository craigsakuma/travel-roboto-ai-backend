"""
LLM factory for creating model instances with A/B testing support.

Provides:
- Model creation based on provider and model name
- A/B testing assignment at conversation level
- Warm-up utilities for reducing first-request latency
- Unified interface across providers
"""

from typing import Literal

from config import Settings, get_settings
from models.base import BaseLLM
from models.providers.anthropic import AnthropicLLM
from models.providers.google import GoogleLLM
from models.providers.openai import OpenAILLM
from utils.logging import get_agent_logger
from utils.secrets import secret_to_str

logger = get_agent_logger("llm_factory")

ProviderType = Literal["openai", "anthropic", "google"]


class LLMFactory:
    """
    Factory for creating LLM instances across multiple providers.

    Handles:
    - Provider-specific initialization
    - API key management
    - Default model selection
    - Error handling for missing credentials
    """

    def __init__(self, settings: Settings | None = None):
        """
        Initialize LLM factory.

        Args:
            settings: Application settings (if None, uses get_settings())
        """
        self.settings = settings or get_settings()
        self._validate_api_keys()

    def _validate_api_keys(self) -> None:
        """Log warnings for missing API keys."""
        if not secret_to_str(self.settings.openai_api_key):
            logger.logger.warning("OPENAI_API_KEY not set - OpenAI models unavailable")

        if not secret_to_str(self.settings.anthropic_api_key):
            logger.logger.warning("ANTHROPIC_API_KEY not set - Anthropic models unavailable")

        if not secret_to_str(self.settings.google_api_key):
            logger.logger.warning("GOOGLE_API_KEY not set - Google models unavailable")

    def create(
        self,
        provider: ProviderType,
        model: str | None = None,
        temperature: float | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> BaseLLM:
        """
        Create an LLM instance for the specified provider.

        Args:
            provider: LLM provider ('openai', 'anthropic', 'google')
            model: Model name (if None, uses provider's default)
            temperature: Sampling temperature (if None, uses 0.2)
            timeout: Request timeout (if None, uses settings.llm_timeout_seconds)
            max_retries: Retry attempts (if None, uses 2)

        Returns:
            BaseLLM: Configured LLM instance

        Raises:
            ValueError: If API key is missing or provider is invalid
        """
        # Set defaults
        temperature = temperature if temperature is not None else 0.2
        timeout = timeout if timeout is not None else self.settings.llm_timeout_seconds
        max_retries = max_retries if max_retries is not None else 2

        # Create provider-specific instance
        if provider == "openai":
            api_key = secret_to_str(self.settings.openai_api_key)
            if not api_key:
                raise ValueError("OPENAI_API_KEY is not set. Configure it in your .env file.")

            return OpenAILLM(
                model=model or "gpt-4o",
                temperature=temperature,
                timeout=timeout,
                max_retries=max_retries,
                api_key=api_key,
            )

        elif provider == "anthropic":
            api_key = secret_to_str(self.settings.anthropic_api_key)
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY is not set. Configure it in your .env file.")

            return AnthropicLLM(
                model=model or "claude-sonnet-4-20250514",
                temperature=temperature,
                timeout=timeout,
                max_retries=max_retries,
                api_key=api_key,
            )

        elif provider == "google":
            api_key = secret_to_str(self.settings.google_api_key)
            if not api_key:
                raise ValueError("GOOGLE_API_KEY is not set. Configure it in your .env file.")

            return GoogleLLM(
                model=model or "gemini-2.0-flash-exp",
                temperature=temperature,
                timeout=timeout,
                max_retries=max_retries,
                api_key=api_key,
            )

        else:
            raise ValueError(
                f"Unknown provider: {provider}. Must be one of: openai, anthropic, google"
            )

    def create_default(self) -> BaseLLM:
        """
        Create LLM using default provider from settings.

        Returns:
            BaseLLM: Configured LLM with default settings
        """
        return self.create(
            provider=self.settings.default_model_provider,
            model=self.settings.default_model_name,
        )


async def warm_up_models(settings: Settings | None = None) -> None:
    """
    Warm up model clients to reduce first-request latency.

    Makes a simple test call to each configured provider to:
    - Initialize HTTP connections
    - Validate API keys
    - Cache any necessary metadata

    Args:
        settings: Application settings (if None, uses get_settings())
    """
    settings = settings or get_settings()
    factory = LLMFactory(settings)

    logger.logger.info("Warming up LLM providers...")

    # Test messages
    from langchain_core.messages import HumanMessage

    test_messages = [HumanMessage(content="Hello")]

    providers_to_warm: list[ProviderType] = []

    if secret_to_str(settings.openai_api_key):
        providers_to_warm.append("openai")
    if secret_to_str(settings.anthropic_api_key):
        providers_to_warm.append("anthropic")
    if secret_to_str(settings.google_api_key):
        providers_to_warm.append("google")

    for provider in providers_to_warm:
        try:
            llm = factory.create(provider)
            await llm.agenerate(test_messages)
            logger.logger.info(f"Warmed up {provider} provider")
        except Exception as e:
            logger.logger.warning(f"Failed to warm up {provider}: {e}")

    logger.logger.info("Model warm-up complete")


def get_llm_factory(settings: Settings | None = None) -> LLMFactory:
    """
    Get LLM factory instance (convenience function).

    Args:
        settings: Application settings (if None, uses get_settings())

    Returns:
        LLMFactory: Factory instance
    """
    return LLMFactory(settings)
