"""
Type definitions for LLM interactions.

Provides common types used across all model providers.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    """
    Standard message format for LLM conversations.

    All providers convert to/from this format.
    """

    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None  # For tool response messages


class ToolCall(BaseModel):
    """
    Tool call made by the LLM.
    """

    id: str = Field(description="Unique tool call ID")
    name: str = Field(description="Tool name")
    input: dict[str, Any] = Field(description="Tool input arguments")


class LLMUsage(BaseModel):
    """
    Token usage statistics from LLM response.
    """

    input_tokens: int
    output_tokens: int
    total_tokens: int | None = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.total_tokens is None:
            self.total_tokens = self.input_tokens + self.output_tokens


class LLMResponse(BaseModel):
    """
    Standard response format from LLM.

    All providers convert their response to this format.
    """

    content: str = Field(description="Response text content")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Tools the LLM wants to call"
    )
    usage: LLMUsage = Field(description="Token usage")
    model: str = Field(description="Model name used")
    finish_reason: str = Field(
        description="Why generation stopped: 'stop', 'length', 'tool_use', 'error'"
    )
    raw_response: Any | None = Field(
        default=None, description="Original provider response (for debugging)"
    )


class ModelConfig(BaseModel):
    """
    Configuration for a specific model.
    """

    provider: Literal["anthropic", "openai"]
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
