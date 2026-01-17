"""
Tool registry for LLM function calling.

Provides:
- Type-safe tool registration with Pydantic schemas
- Tool metadata for LangChain integration
- Centralized tool management for agents
"""

from typing import Any, Callable

from pydantic import BaseModel, Field

from utils.logging import get_agent_logger

logger = get_agent_logger("tool_registry")


class ToolDefinition(BaseModel):
    """
    Definition of a tool that can be called by LLMs.
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str = Field(description="Tool name (must be unique)")
    description: str = Field(
        description="Human-readable description of what the tool does"
    )
    parameters_schema: dict[str, Any] = Field(
        description="JSON Schema for tool parameters"
    )
    function: Callable[..., Any] = Field(
        description="Python function to execute", exclude=True
    )


class ToolRegistry:
    """
    Registry for managing LLM-callable tools.

    Provides centralized registration and lookup of tools for function calling.
    Tools are defined with Pydantic schemas for type safety.
    """

    def __init__(self):
        """Initialize empty tool registry."""
        self._tools: dict[str, ToolDefinition] = {}
        logger.logger.debug("Initialized ToolRegistry")

    def register(
        self,
        name: str,
        description: str,
        parameters_schema: dict[str, Any],
        function: Callable[..., Any],
    ) -> None:
        """
        Register a new tool.

        Args:
            name: Unique tool name (used by LLM to call the tool)
            description: Description of what the tool does
            parameters_schema: JSON Schema defining tool parameters
            function: Python function to execute when tool is called

        Raises:
            ValueError: If a tool with this name already exists
        """
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        tool = ToolDefinition(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            function=function,
        )
        self._tools[name] = tool
        logger.logger.debug(f"Registered tool: {name}")

    def get_tool(self, name: str) -> ToolDefinition | None:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            ToolDefinition if found, None otherwise
        """
        return self._tools.get(name)

    def get_all_tools(self) -> list[ToolDefinition]:
        """
        Get all registered tools.

        Returns:
            List of all tool definitions
        """
        return list(self._tools.values())

    def get_tools_for_langchain(self) -> list[dict[str, Any]]:
        """
        Get tools in LangChain-compatible format.

        Returns:
            List of tool definitions formatted for LangChain
        """
        tools = []
        for tool in self._tools.values():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters_schema,
                    },
                }
            )
        return tools

    def get_tools_for_anthropic(self) -> list[dict[str, Any]]:
        """
        Get tools in Anthropic Claude format.

        Returns:
            List of tool definitions formatted for Anthropic API
        """
        tools = []
        for tool in self._tools.values():
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters_schema,
                }
            )
        return tools

    async def execute_tool(self, name: str, **kwargs: Any) -> Any:
        """
        Execute a registered tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
            Exception: If tool execution fails
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found in registry")

        logger.logger.info(f"Executing tool: {name}", extra={"tool_args": kwargs})

        try:
            # Execute the tool function
            result = await tool.function(**kwargs)
            logger.logger.debug(
                f"Tool {name} executed successfully", extra={"result": result}
            )
            return result
        except Exception as e:
            logger.error(
                e, context="tool_execution_failed", tool_name=name, tool_args=kwargs
            )
            raise

    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
