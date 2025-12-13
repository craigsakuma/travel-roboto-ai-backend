"""
logging_utils.py
================

Reusable logging utilities for the Travel-Roboto-AI-Backend project.

This module:
- Uses a ContextVar-backed request_id to correlate logs per request/flow.
- Provides a logging Filter that injects `request_id` into every LogRecord.
- Exposes helpers to set/get/generate request IDs.
- Adds concise helpers for structured logging (`log_with_id`) and
  scoped block logging with timing (`log_context`).
- Includes `truncate_msg` to keep extremely long log lines readable.

IMPORTANT
---------
This module does NOT configure the root logger; configure that in `main.py`
(handlers, formatter with `%(request_id)s`, levels, etc.).
"""

from __future__ import annotations

import contextvars
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any

# ---------------------------------------------------------------------------
# ContextVar for request-scoped correlation
# ---------------------------------------------------------------------------

# Carries the current request_id (or None). Middlewares/entrypoints should set it.
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> str | None:
    """Return the current request_id from the context (or None if not set)."""
    return _request_id_var.get()


def set_request_id(request_id: str | None) -> None:
    """Set the current request_id in the context for correlation-aware logging."""
    _request_id_var.set(request_id)


def new_request_id() -> str:
    """Generate a new request_id as a UUID4 string."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Filter to inject request_id onto every LogRecord
# ---------------------------------------------------------------------------

class RequestIdFilter(logging.Filter):
    """
    Logging filter that injects the current request_id into each LogRecord
    as `request_id`. If none is set, uses "-".
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        rid = get_request_id()
        # Make available to formatters via %(request_id)s
        record.request_id = rid if rid else "-"
        return True


# ---------------------------------------------------------------------------
# Logger and structured logging helpers
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger. Handlers/formatters/levels are inherited from the
    root logger configured in `main.py`.
    """
    return logging.getLogger(name)


def log_with_id(
    logger: logging.Logger,
    level: int | str,
    message: str,
    *,
    request_id: str | None = None,
    **extra: Any,
) -> None:
    """
    Log a message with a request_id and arbitrary structured fields.

    - If `request_id` is not provided, uses the ContextVar value.
    - You can pass additional structured fields via **extra, e.g. user_id=..., step=...
    - Reserved LogRecord attributes are ignored. In DEBUG mode, a warning is logged.
    - Uses `logger.log(level, ...)` so you can pass logging.INFO, logging.ERROR, etc.
    """
    rid = request_id if request_id is not None else get_request_id()

    # Normalize level: allow both logging.DEBUG or "DEBUG"
    if isinstance(level, str):
        try:
            level = getattr(logging, level.upper())
        except AttributeError:
            logger.warning("Unknown log level %r, defaulting to INFO", level)
            level = logging.INFO

    reserved = {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message"
    }

    # Detect reserved keys in the extra kwargs
    reserved_used = [k for k in extra if k in reserved]
    if reserved_used:
        msg = (
            "Ignoring reserved logging keys in extra: %s. "
            "These names are managed by the logging system."
        )
        # In dev (DEBUG logging), make the misuse obvious
        if logger.isEnabledFor(logging.DEBUG):
            logger.warning(msg, ", ".join(reserved_used))
        # Strip them regardless to keep logs safe
        extra = {k: v for k, v in extra.items() if k not in reserved}

    logger.log(level, message, extra={"request_id": rid or "-", **extra})


@contextmanager
def log_context(
    logger: logging.Logger,
    label: str,
    *,
    level: int = logging.INFO,
    request_id: str | None = None,
    **extra: Any,
):
    """
    Context manager that logs Start/End for a labeled block and measures elapsed time.

    Example:
        with log_context(logger, "ingest_emails", user_id=user_id):
            ...  # do work

    Emits:
        - "Start: ingest_emails"
        - "End: ingest_emails (elapsed=0.123s)"
    """
    start = time.perf_counter()
    log_with_id(logger, level, f"Start: {label}", request_id=request_id, **extra)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        log_with_id(
            logger,
            level,
            f"End: {label} (elapsed={elapsed:.3f}s)",
            request_id=request_id,
            **extra,
        )


# ---------------------------------------------------------------------------
# Utility: keep very long strings readable in logs
# ---------------------------------------------------------------------------

def truncate_msg(msg: str, max_length: int = 500) -> str:
    """
    Truncate long strings for logging (useful for LLM responses, payloads, etc.).

    If `msg` exceeds `max_length`, returns the first max_length characters plus "...".
    """
    return msg if len(msg) <= max_length else f"{msg[:max_length]}..."


__all__ = [
    "get_request_id",
    "set_request_id",
    "new_request_id",
    "RequestIdFilter",
    "get_logger",
    "log_with_id",
    "log_context",
    "truncate_msg",
]
