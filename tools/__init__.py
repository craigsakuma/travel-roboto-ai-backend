"""
Tools module for LLM function calling.

Provides tool registry and trip-related tools.
"""

from tools.registry import ToolDefinition, ToolRegistry
from tools.trip_tools import get_trip_details, register_trip_tools

__all__ = [
    "ToolRegistry",
    "ToolDefinition",
    "get_trip_details",
    "register_trip_tools",
]
