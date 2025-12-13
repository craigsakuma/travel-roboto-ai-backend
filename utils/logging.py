"""
Logging utilities for the Travel-Roboto-AI-Backend.

Provides:
- Request ID tracking across async contexts
- Agent thought/action/observation logging
- Structured logging for LLM calls
- Request ID middleware for FastAPI
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from config import get_settings

# Context variable to track request_id across async contexts
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """
    Logging filter that injects request_id into every log record.

    If no request_id is set in the context, defaults to "-".
    This allows the formatter to safely use %(request_id)s.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that generates and tracks request IDs.

    - Generates a UUID for each request
    - Sets it in the context variable for logging
    - Adds X-Request-ID header to responses
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Set in context for logging
        token = request_id_var.set(request_id)

        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Reset context
            request_id_var.reset(token)


def configure_logging() -> None:
    """
    Configure the root logger with request_id-aware formatting.

    Sets up:
    - Request ID injection via RequestIdFilter
    - Structured log format with timestamp, level, module, function, request_id
    - Output to stdout (container/cloud-friendly)
    - Log level from settings
    """
    settings = get_settings()

    # Resolve log level from settings
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Build formatter with request_id
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s | %(request_id)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Stream to stdout (good for Docker, Railway, GCP, etc.)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    # Install on root logger
    root = logging.getLogger()
    root.handlers.clear()  # Avoid duplicate handlers on reload
    root.setLevel(level)
    root.addHandler(handler)

    # Reduce noise from common libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


class AgentLogger:
    """
    Specialized logger for tracking agent reasoning cycles.

    Logs agent thought, action, observation, and response in a structured format.
    Useful for debugging and evaluation.

    Example:
        logger = AgentLogger("travel_concierge")
        logger.thought("I need to search for flight information")
        logger.action("call_tool", {"tool": "flight_search", "params": {...}})
        logger.observation("Found 3 flights matching criteria")
        logger.response("Here are your flight options...")
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"agent.{agent_name}")
        self.settings = get_settings()

    def thought(self, content: str, **extra):
        """Log agent's reasoning/planning step."""
        if self.settings.enable_llm_tracing:
            self.logger.info(
                f"[THOUGHT] {content}",
                extra={"agent": self.agent_name, "step": "thought", **extra},
            )

    def action(self, action_type: str, details: dict[str, Any] | None = None, **extra):
        """Log agent's action (tool call, direct response, etc.)."""
        if self.settings.enable_llm_tracing:
            self.logger.info(
                f"[ACTION] {action_type}",
                extra={
                    "agent": self.agent_name,
                    "step": "action",
                    "action_type": action_type,
                    "details": details or {},
                    **extra,
                },
            )

    def observation(self, content: str, **extra):
        """Log agent's observation after action."""
        if self.settings.enable_llm_tracing:
            self.logger.info(
                f"[OBSERVATION] {content}",
                extra={"agent": self.agent_name, "step": "observation", **extra},
            )

    def response(self, content: str, **extra):
        """Log agent's final response to user."""
        self.logger.info(
            f"[RESPONSE] {content[:100]}...",  # Truncate for readability
            extra={"agent": self.agent_name, "step": "response", **extra},
        )

    def error(self, error: Exception, context: str = "", **extra):
        """Log agent errors with full context."""
        self.logger.error(
            f"[ERROR] {context}: {str(error)}",
            exc_info=True,
            extra={"agent": self.agent_name, "step": "error", **extra},
        )

    def llm_call(
        self,
        model: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        latency_ms: float | None = None,
        **extra,
    ):
        """Log LLM API call metrics."""
        if self.settings.enable_llm_tracing:
            self.logger.info(
                f"[LLM_CALL] model={model}",
                extra={
                    "agent": self.agent_name,
                    "step": "llm_call",
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "latency_ms": latency_ms,
                    **extra,
                },
            )


def get_agent_logger(agent_name: str) -> AgentLogger:
    """
    Factory function to create an AgentLogger.

    Args:
        agent_name: Name of the agent (e.g., "travel_concierge", "trip_coordinator")

    Returns:
        AgentLogger: Logger instance for the agent
    """
    return AgentLogger(agent_name)
