from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class ToolResult:
    """
    Standard result returned by every Cauvis tool.
    """

    success: bool
    tool_name: str
    output: Any = None
    error: str | None = None
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def success_result(
        cls,
        tool_name: str,
        output: Any = None,
        metadata: dict[str, Any] | None = None,
        execution_time: float = 0.0,
    ) -> "ToolResult":
        """
        Create a successful tool result.
        """

        return cls(
            success=True,
            tool_name=tool_name,
            output=output,
            execution_time=execution_time,
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        tool_name: str,
        error: str,
        metadata: dict[str, Any] | None = None,
        execution_time: float = 0.0,
    ) -> "ToolResult":
        """
        Create a failed tool result.
        """

        return cls(
            success=False,
            tool_name=tool_name,
            error=error,
            execution_time=execution_time,
            metadata=metadata or {},
        )


class ToolExecutor:
    """
    Executes a tool and converts its raw return value
    into a standardized ToolResult.
    """

    def execute(
        self,
        tool_name: str,
        handler,
        *args: Any,
        **kwargs: Any,
    ) -> ToolResult:
        start = time.perf_counter()

        try:
            output = handler(
                *args,
                **kwargs,
            )

            execution_time = (
                time.perf_counter() - start
            )

            return ToolResult.success_result(
                tool_name=tool_name,
                output=output,
                execution_time=execution_time,
            )

        except Exception as exc:
            execution_time = (
                time.perf_counter() - start
            )

            return ToolResult.failure_result(
                tool_name=tool_name,
                error=str(exc),
                execution_time=execution_time,
            )