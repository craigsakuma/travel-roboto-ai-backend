"""Configuration for the Travel-Roboto-AI-Backend.

Typed, 12-factor settings via Pydantic v2. Manages API keys, Firestore settings,
and A/B testing configuration. No I/O or side effects at import.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # --- Pydantic model config  ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App / Logging ---
    app_env: Literal["development", "test", "production"] = Field(
        default="development",
        description="Application environment (affects logging, feature flags, etc.)",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="DEBUG", description="Python logging verbosity level."
    )

    @property
    def is_prod(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def is_dev(self) -> bool:
        """Check if running in development environment."""
        return self.app_env == "development"

    @property
    def log_level_int(self) -> int:
        """Return stdlib logging level as int (e.g., logging.INFO)."""
        import logging

        return getattr(logging, self.log_level, logging.INFO)

    # --- PostgreSQL Database ---
    postgres_host: str = Field(default="localhost", description="PostgreSQL host address")
    postgres_port: int = Field(default=5432, description="PostgreSQL port", ge=1, le=65535)
    postgres_db: str = Field(default="travelroboto", description="PostgreSQL database name")
    postgres_user: str = Field(default="postgres", description="PostgreSQL username")
    postgres_password: SecretStr = Field(
        default="password", description="PostgreSQL password"
    )
    postgres_pool_size: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Database connection pool size",
    )
    postgres_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum overflow connections beyond pool_size",
    )
    postgres_pool_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Connection pool timeout in seconds",
    )

    @property
    def database_url(self) -> str:
        """
        Construct PostgreSQL connection URL for async SQLAlchemy.

        Returns:
            str: Database URL in format postgresql+asyncpg://user:pass@host:port/db
        """
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """
        Construct PostgreSQL connection URL for sync operations (e.g., Alembic migrations).

        Returns:
            str: Database URL in format postgresql+psycopg://user:pass@host:port/db
        """
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # --- LLM Provider API Keys ---
    openai_api_key: SecretStr | None = Field(
        default=None, description="API key for OpenAI (GPT-4, etc.)"
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None, description="API key for Anthropic (Claude models)"
    )
    google_api_key: SecretStr | None = Field(
        default=None, description="API key for Google AI (Gemini models)"
    )

    # --- A/B Testing Configuration ---
    ab_testing_enabled: bool = Field(
        default=True, description="Enable A/B testing for models and prompts."
    )
    default_model_provider: Literal["openai", "anthropic", "google"] = Field(
        default="anthropic", description="Default LLM provider when A/B testing is disabled."
    )
    default_model_name: str = Field(
        default="claude-sonnet-4-20250514",
        description="Default model name when A/B testing is disabled.",
    )

    # Model pool for A/B testing (conversation-level assignment)
    ab_model_variants: list[dict[str, str]] = Field(
        default=[
            {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
            {"provider": "openai", "model": "gpt-4o"},
        ],
        description="List of model variants for A/B testing. Each dict has 'provider' and 'model' keys.",
    )

    # --- Prompt Template Configuration ---
    prompts_base_dir: Path = Field(
        default=BASE_DIR / "agents" / "prompts", description="Base directory for prompt templates."
    )

    @property
    def travel_concierge_prompts_dir(self) -> Path:
        """Directory containing Travel Concierge agent prompts."""
        return self.prompts_base_dir / "travel_concierge"

    @property
    def trip_coordinator_prompts_dir(self) -> Path:
        """Directory containing Trip Coordinator agent prompts."""
        return self.prompts_base_dir / "trip_coordinator"

    # --- Gmail Integration (for email webhook) ---
    gmail_webhook_secret: SecretStr | None = Field(
        default=None, description="Secret token for validating Gmail webhook requests."
    )
    gmail_client_id: str | None = Field(
        default=None, description="Google OAuth 2.0 client ID for Gmail API access."
    )
    gmail_client_secret: SecretStr | None = Field(
        default=None, description="Google OAuth 2.0 client secret for Gmail API access."
    )
    gmail_credentials_dir: Path = Field(
        default=BASE_DIR / "credentials",
        description="Directory where Gmail OAuth credentials are stored.",
    )
    gmail_token_file: Path = Field(
        default=BASE_DIR / "credentials" / "gmail_token.json",
        description="Path to saved Gmail OAuth access token.",
    )
    gmail_scopes: tuple[str, ...] = Field(
        default=(
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
        ),
        description="OAuth scopes for Gmail API access.",
    )

    # --- Evaluation & Observability ---
    enable_llm_tracing: bool = Field(
        default=True,
        description="Enable detailed logging of LLM calls (thought/action/observation).",
    )
    evaluation_output_dir: Path = Field(
        default=BASE_DIR / "evaluation" / "results",
        description="Directory for storing evaluation results and metrics.",
    )
    golden_test_cases_path: Path = Field(
        default=BASE_DIR / "evaluation" / "test_cases.json",
        description="Path to golden Q&A test cases for evaluation.",
    )

    # --- Rate Limiting & Performance ---
    max_conversation_history_turns: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of conversation turns to include in context.",
    )
    llm_timeout_seconds: int = Field(
        default=30, ge=5, le=120, description="Timeout for LLM API calls in seconds."
    )
    max_concurrent_llm_calls: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent LLM API calls (for async operations).",
    )

    # --- Feature Flags ---
    enable_rag: bool = Field(
        default=False,
        description="Enable RAG (vector search) for document retrieval. False for MVP.",
    )
    enable_conflict_resolution: bool = Field(
        default=False,
        description="Enable automatic conflict resolution for trip data. False for MVP.",
    )
    enable_real_time_updates: bool = Field(
        default=False,
        description="Enable real-time WebSocket updates for multi-user trips. False for MVP.",
    )

    # --- Development Helpers ---
    sample_trip_data_path: Path = Field(
        default=BASE_DIR / "data" / "sample_trip.json",
        description="Path to sample trip data for development/testing.",
    )
    mock_llm_responses: bool = Field(
        default=False,
        description="Use mock LLM responses instead of real API calls (for testing).",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide singleton Settings instance (FastAPI DI-friendly).

    Uses lru_cache to ensure only one Settings instance is created per process.
    This is the recommended pattern for FastAPI dependency injection.

    Returns:
        Settings: The application settings instance.

    Example:
        ```python
        from fastapi import Depends
        from config import get_settings, Settings


        @app.get("/health")
        async def health(settings: Settings = Depends(get_settings)):
            return {"env": settings.app_env}
        ```
    """
    return Settings()


# Convenience alias for direct imports (use get_settings() for DI)
settings = get_settings()
