from dataclasses import dataclass, field
from typing import Any, Callable

from tools.results import ToolExecutor, ToolResult


@dataclass
class Tool:
    """
    Describes an executable tool available to Cauvis.
    """

    name: str
    description: str
    capabilities: set[str] = field(default_factory=set)
    enabled: bool = True
    handler: Callable[..., Any] | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class ToolRegistry:
    """
    Central registry for executable Cauvis tools.

    The registry discovers and manages tools.

    Tool execution is routed through ToolExecutor so
    every tool produces a standardized ToolResult.
    """

    def __init__(
        self,
        executor: ToolExecutor | None = None,
    ):
        self._tools: dict[str, Tool] = {}
        self.executor = executor or ToolExecutor()

    def register(
        self,
        tool: Tool,
    ) -> None:
        if not tool.name.strip():
            raise ValueError(
                "Tool name cannot be empty."
            )

        self._tools[tool.name] = tool

    def unregister(
        self,
        name: str,
    ) -> None:
        self._tools.pop(name, None)

    def get(
        self,
        name: str,
    ) -> Tool | None:
        return self._tools.get(name)

    def has(
        self,
        name: str,
    ) -> bool:
        tool = self.get(name)

        return (
            tool is not None
            and tool.enabled
        )

    def list_all(
        self,
    ) -> list[Tool]:
        return list(
            self._tools.values()
        )

    def list_enabled(
        self,
    ) -> list[Tool]:
        return [
            tool
            for tool in self._tools.values()
            if tool.enabled
        ]

    def find_by_capability(
        self,
        capability: str,
    ) -> list[Tool]:
        return [
            tool
            for tool in self._tools.values()
            if tool.enabled
            and capability in tool.capabilities
        ]

    def find_for_capabilities(
        self,
        required_capabilities: set[str],
    ) -> list[Tool]:
        return [
            tool
            for tool in self._tools.values()
            if tool.enabled
            and bool(
                tool.capabilities
                & required_capabilities
            )
        ]

    def missing_capabilities(
        self,
        required_capabilities: set[str],
    ) -> set[str]:
        available = set()

        for tool in self.list_enabled():
            available.update(
                tool.capabilities
            )

        return (
            required_capabilities
            - available
        )

    def can_support(
        self,
        required_capabilities: set[str],
    ) -> bool:
        return not self.missing_capabilities(
            required_capabilities
        )

    def enable(
        self,
        name: str,
    ) -> bool:
        tool = self.get(name)

        if tool is None:
            return False

        tool.enabled = True

        return True

    def disable(
        self,
        name: str,
    ) -> bool:
        tool = self.get(name)

        if tool is None:
            return False

        tool.enabled = False

        return True

    def execute(
        self,
        name: str,
        *args: Any,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Execute a tool through ToolExecutor.

        Every execution produces a ToolResult,
        including failures.
        """

        tool = self.get(name)

        if tool is None:
            return ToolResult.failure_result(
                tool_name=name,
                error=f"Unknown tool: {name}",
            )

        if not tool.enabled:
            return ToolResult.failure_result(
                tool_name=name,
                error=f"Tool is disabled: {name}",
            )

        if tool.handler is None:
            return ToolResult.failure_result(
                tool_name=name,
                error=(
                    f"Tool has no executable handler: "
                    f"{name}"
                ),
            )

        result = self.executor.execute(
            name,
            tool.handler,
            *args,
            **kwargs,
        )

        result.metadata.update(
            {
                "capabilities": sorted(
                    tool.capabilities
                ),
                "description": tool.description,
            }
        )

        return result

    def count(self) -> int:
        return len(self._tools)

    def enabled_count(self) -> int:
        return len(
            self.list_enabled()
        )