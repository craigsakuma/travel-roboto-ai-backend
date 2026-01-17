"""Tests for LLM model factory and providers.

Tests model factory, provider initialization, and LLM abstractions.
"""

import pytest

from config import Settings
from models.base import BaseLLM
from models.factory import LLMFactory
from models.providers.anthropic import AnthropicLLM
from models.providers.google import GoogleLLM
from models.providers.openai import OpenAILLM


@pytest.fixture
def test_settings():
    """Create test settings with mock API keys."""
    return Settings(
        app_env="test",
        mock_llm_responses=True,
        openai_api_key="test-openai-key",
        anthropic_api_key="test-anthropic-key",
        google_api_key="test-google-key",
        default_model_provider="anthropic",
        default_model_name="claude-3-5-sonnet-20241022",
    )


class TestLLMFactory:
    """Test LLM factory functionality."""

    def test_create_factory(self, test_settings):
        """Test creating an LLM factory instance."""
        factory = LLMFactory(test_settings)
        assert factory.settings == test_settings

    def test_create_anthropic_provider(self, test_settings):
        """Test creating Anthropic provider."""
        factory = LLMFactory(test_settings)
        llm = factory.create(provider="anthropic", model="claude-3-5-sonnet-20241022")

        assert isinstance(llm, AnthropicLLM)
        assert isinstance(llm, BaseLLM)
        assert llm.model == "claude-3-5-sonnet-20241022"
        assert llm.provider_name == "anthropic"

    def test_create_openai_provider(self, test_settings):
        """Test creating OpenAI provider."""
        factory = LLMFactory(test_settings)
        llm = factory.create(provider="openai", model="gpt-4o")

        assert isinstance(llm, OpenAILLM)
        assert isinstance(llm, BaseLLM)
        assert llm.model == "gpt-4o"
        assert llm.provider_name == "openai"

    def test_create_google_provider(self, test_settings):
        """Test creating Google provider."""
        factory = LLMFactory(test_settings)
        llm = factory.create(provider="google", model="gemini-2.0-flash-exp")

        assert isinstance(llm, GoogleLLM)
        assert isinstance(llm, BaseLLM)
        assert llm.model == "gemini-2.0-flash-exp"
        assert llm.provider_name == "google"

    def test_create_with_custom_temperature(self, test_settings):
        """Test creating LLM with custom temperature."""
        factory = LLMFactory(test_settings)
        llm = factory.create(provider="anthropic", temperature=0.7)

        assert llm.temperature == 0.7

    def test_create_with_custom_timeout(self, test_settings):
        """Test creating LLM with custom timeout."""
        factory = LLMFactory(test_settings)
        llm = factory.create(provider="anthropic", timeout=60)

        assert llm.timeout == 60

    def test_create_default(self, test_settings):
        """Test creating default LLM from settings."""
        factory = LLMFactory(test_settings)
        llm = factory.create_default()

        assert isinstance(llm, AnthropicLLM)
        assert llm.model == "claude-3-5-sonnet-20241022"

    def test_create_missing_api_key(self):
        """Test creating LLM with missing API key."""
        settings = Settings(
            app_env="test",
            openai_api_key=None,  # No API key
            anthropic_api_key="test-key",
            google_api_key="test-key",
        )
        factory = LLMFactory(settings)

        with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
            factory.create(provider="openai")

    def test_create_invalid_provider(self, test_settings):
        """Test creating LLM with invalid provider."""
        factory = LLMFactory(test_settings)

        with pytest.raises(ValueError, match="Unknown provider"):
            factory.create(provider="invalid-provider")


class TestAnthropicLLM:
    """Test Anthropic LLM provider."""

    def test_initialization(self):
        """Test Anthropic LLM initialization."""
        llm = AnthropicLLM(
            model="claude-3-5-sonnet-20241022",
            api_key="test-key",
            temperature=0.5,
        )

        assert llm.model == "claude-3-5-sonnet-20241022"
        assert llm.temperature == 0.5
        assert llm.provider_name == "anthropic"

    def test_temperature_validation(self):
        """Test temperature validation."""
        with pytest.raises(ValueError, match="temperature must be between"):
            AnthropicLLM(model="claude-3-5-sonnet-20241022", api_key="test-key", temperature=3.0)

    def test_missing_api_key(self):
        """Test initialization without API key."""
        with pytest.raises(ValueError, match="Anthropic API key is required"):
            AnthropicLLM(model="claude-3-5-sonnet-20241022", api_key=None)

    def test_get_runnable(self):
        """Test getting LangChain runnable."""
        llm = AnthropicLLM(model="claude-3-5-sonnet-20241022", api_key="test-key")
        runnable = llm.get_runnable()

        assert runnable is not None
        # Runnable is a complex LangChain object, just verify it exists
        assert hasattr(runnable, "invoke") or hasattr(runnable, "ainvoke")

    # Note: calculate_cost is not implemented in AnthropicLLM
    # Cost calculation happens at a different layer


class TestOpenAILLM:
    """Test OpenAI LLM provider."""

    def test_initialization(self):
        """Test OpenAI LLM initialization."""
        llm = OpenAILLM(model="gpt-4o", api_key="test-key", temperature=0.3)

        assert llm.model == "gpt-4o"
        assert llm.temperature == 0.3
        assert llm.provider_name == "openai"

    def test_missing_api_key(self):
        """Test initialization without API key."""
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            OpenAILLM(model="gpt-4o", api_key=None)

    def test_estimate_cost_gpt4o(self):
        """Test cost estimation for GPT-4o."""
        llm = OpenAILLM(model="gpt-4o", api_key="test-key")

        cost = llm.estimate_cost(prompt_tokens=1000, completion_tokens=500)

        # GPT-4o: $2.50 per 1M input, $10.00 per 1M output
        expected_cost = (1000 / 1_000_000 * 2.50) + (500 / 1_000_000 * 10.00)
        assert cost == pytest.approx(expected_cost, rel=1e-6)

    def test_estimate_cost_gpt5_mini(self):
        """Test cost estimation for GPT-5-mini."""
        llm = OpenAILLM(model="gpt-5-mini", api_key="test-key")

        cost = llm.estimate_cost(prompt_tokens=1000, completion_tokens=500)

        # GPT-5-mini: $0.25 per 1M input, $2.00 per 1M output
        expected_cost = (1000 / 1_000_000 * 0.25) + (500 / 1_000_000 * 2.00)
        assert cost == pytest.approx(expected_cost, rel=1e-6)


class TestGoogleLLM:
    """Test Google LLM provider."""

    def test_initialization(self):
        """Test Google LLM initialization."""
        llm = GoogleLLM(model="gemini-2.0-flash-exp", api_key="test-key", temperature=0.4)

        assert llm.model == "gemini-2.0-flash-exp"
        assert llm.temperature == 0.4
        assert llm.provider_name == "google"

    def test_missing_api_key(self):
        """Test initialization without API key."""
        with pytest.raises(ValueError, match="Google API key is required"):
            GoogleLLM(model="gemini-2.0-flash-exp", api_key=None)


class TestBaseLLM:
    """Test BaseLLM abstract interface."""

    def test_metrics_recording(self):
        """Test metrics recording."""
        llm = AnthropicLLM(model="claude-3-5-sonnet-20241022", api_key="test-key")

        # Record metrics
        llm._record_metrics(prompt_tokens=100, completion_tokens=50, latency_ms=1200)

        metrics = llm.get_last_metrics()
        assert metrics is not None
        assert metrics.prompt_tokens == 100
        assert metrics.completion_tokens == 50
        assert metrics.total_tokens == 150
        assert metrics.latency_ms == 1200
        assert metrics.model == "claude-3-5-sonnet-20241022"
        assert metrics.provider == "anthropic"

    def test_no_metrics_initially(self):
        """Test that no metrics exist before first call."""
        llm = AnthropicLLM(model="claude-3-5-sonnet-20241022", api_key="test-key")

        metrics = llm.get_last_metrics()
        assert metrics is None
