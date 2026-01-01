"""
FastAPI application entrypoint for Travel Roboto AI Backend.

- Primary: Expose create_app() factory for Uvicorn (--factory) in all environments.
- Convenience: Allow `python -m main` for local development runs, honoring $PORT.

Architecture:
- Skills-based modular monolith organized by AI capabilities
- Supports A/B testing for models and prompts
- PostgreSQL for conversation memory and trip data persistence
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import Settings, get_settings
from utils.logging import RequestIdMiddleware, configure_logging

# Configure logging at import time
configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Async context manager for application lifespan events.

    Handles startup and shutdown tasks like:
    - Initializing database connection pool
    - Warming up model clients
    - Cleanup on shutdown
    """
    settings: Settings = app.state.settings

    logger.info(
        "Starting Travel Agent API",
        extra={
            "env": settings.app_env,
            "database": settings.postgres_db,
            "ab_testing_enabled": settings.ab_testing_enabled,
        },
    )

    # Startup: Initialize connections
    try:
        # Initialize database engine and connection pool
        from db import init_db

        engine = init_db(settings)
        app.state.db_engine = engine
        logger.info(
            "Database initialized",
            extra={
                "host": settings.postgres_host,
                "database": settings.postgres_db,
                "pool_size": settings.postgres_pool_size,
            },
        )

        # Warm up model providers (optional, improves first request latency)
        if not settings.mock_llm_responses:
            from models.factory import warm_up_models

            await warm_up_models(settings)
            logger.info("LLM providers warmed up")

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        raise

    yield  # Application is running

    # Shutdown: Cleanup
    logger.info("Shutting down Travel Agent API")
    if hasattr(app.state, "db_engine"):
        await app.state.db_engine.dispose()
        logger.info("Database connection pool closed")


def create_app() -> FastAPI:
    """
    Application factory for FastAPI.

    Creates and configures the FastAPI application with:
    - API routes organized by capability
    - CORS middleware for React frontend
    - Request ID tracking for observability
    - Dependency injection for settings

    Returns:
        FastAPI: Configured application instance
    """
    settings = get_settings()

    app = FastAPI(
        title="Travel Agent API",
        description="AI-powered travel planning assistant with multi-user collaboration",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_dev else None,  # Disable in production
        redoc_url="/redoc" if settings.is_dev else None,
    )

    # Store settings in app state for access in lifespan and routes
    app.state.settings = settings

    # --- Middleware ---

    # CORS for React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID tracking (for correlation across logs)
    app.add_middleware(RequestIdMiddleware)

    # --- Routes ---

    # API endpoints organized by capability
    from api.chat import router as chat_router
    from api.trips import router as trips_router
    from api.webhooks import router as webhooks_router

    app.include_router(chat_router, prefix="/api", tags=["Chat"])
    app.include_router(webhooks_router, prefix="/api/webhooks", tags=["Webhooks"])
    app.include_router(trips_router, prefix="/api/trips", tags=["Trips"])

    # Health check endpoint
    @app.get("/health", tags=["System"])
    async def health_check():
        """Health check endpoint for load balancers and monitoring."""
        return {
            "status": "healthy",
            "env": settings.app_env,
            "ab_testing_enabled": settings.ab_testing_enabled,
        }

    # Root endpoint
    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint with API information."""
        return {
            "service": "Travel Agent API",
            "version": "0.1.0",
            "docs": "/docs" if settings.is_dev else "disabled",
        }

    logger.info(
        "FastAPI application created",
        extra={
            "env": settings.app_env,
            "routes_count": len(app.routes),
        },
    )

    return app


if __name__ == "__main__":
    """
    Development server entry point.

    Run with: python main.py

    In production, use:
        uvicorn main:create_app --factory --host 0.0.0.0 --port 8000
    """
    import os

    import uvicorn

    settings = get_settings()
    port = int(os.getenv("PORT", "8000"))

    logger.info(f"Starting development server on port {port}")

    uvicorn.run(
        "main:create_app",
        factory=True,
        host="0.0.0.0",
        port=port,
        reload=settings.is_dev,  # Auto-reload in development
        log_level=settings.log_level.lower(),
    )
