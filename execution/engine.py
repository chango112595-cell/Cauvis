from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from capabilities.registry import CapabilityRegistry
from intelligence.reasoning import ReasoningResult
from security.permissions import PermissionManager
from tools.registry import ToolRegistry
from tools.results import ToolResult
from verification.verifier import VerificationEngine


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionStep:
    """A single step in an execution plan."""

    step_number: int
    description: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    required_capabilities: set[str] = field(
        default_factory=set
    )
    required_permissions: set[str] = field(
        default_factory=set
    )
    selected_tools: list[str] = field(
        default_factory=list
    )
    result: Any = None
    error: str | None = None


@dataclass
class ExecutionPlan:
    """A complete execution plan created from reasoning."""

    goal: str
    steps: list[ExecutionStep] = field(
        default_factory=list
    )
    requires_tools: bool = False
    requires_verification: bool = True
    status: ExecutionStatus = ExecutionStatus.PENDING
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class ExecutionResult:
    """Final result returned by the execution engine."""

    success: bool
    goal: str
    status: ExecutionStatus
    completed_steps: int
    total_steps: int
    failed_step: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class ExecutionEngine:
    """
    Controlled execution coordinator for Cauvis.

    The engine converts reasoning into an execution plan,
    checks capabilities, checks permissions, discovers tools,
    executes approved tools, and verifies results.

    Dangerous actions are blocked unless the permission
    system explicitly allows them.
    """

    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        tool_registry: ToolRegistry,
        permission_manager: PermissionManager,
        verification_engine: VerificationEngine,
    ):
        self.capability_registry = capability_registry
        self.tool_registry = tool_registry
        self.permission_manager = permission_manager
        self.verification_engine = verification_engine

    def create_plan(
        self,
        reasoning: ReasoningResult,
        required_capabilities: set[str] | None = None,
        required_permissions: set[str] | None = None,
    ) -> ExecutionPlan:
        required_capabilities = (
            required_capabilities or set()
        )

        required_permissions = (
            required_permissions or set()
        )

        steps = []

        for index, description in enumerate(
            reasoning.steps,
            start=1,
        ):
            steps.append(
                ExecutionStep(
                    step_number=index,
                    description=description,
                    required_capabilities=set(
                        required_capabilities
                    ),
                    required_permissions=set(
                        required_permissions
                    ),
                )
            )

        return ExecutionPlan(
            goal=reasoning.goal,
            steps=steps,
            requires_tools=reasoning.requires_tools,
            requires_verification=(
                reasoning.requires_verification
            ),
            metadata={
                "reasoning_step_count": len(
                    reasoning.steps
                ),
                "required_capabilities": sorted(
                    required_capabilities
                ),
                "required_permissions": sorted(
                    required_permissions
                ),
            },
        )

    def discover_tools(
        self,
        required_capabilities: set[str],
    ) -> list[str]:
        tools = self.tool_registry.find_for_capabilities(
            required_capabilities
        )

        return [
            tool.name
            for tool in tools
        ]

    def validate_plan(
        self,
        plan: ExecutionPlan,
    ) -> tuple[bool, set[str]]:
        required = set(
            plan.metadata.get(
                "required_capabilities",
                [],
            )
        )

        missing_from_capabilities = (
            self.capability_registry.missing(
                required
            )
        )

        missing_from_tools = (
            self.tool_registry.missing_capabilities(
                required
            )
        )

        missing = (
            missing_from_capabilities
            | missing_from_tools
        )

        return (
            not missing,
            missing,
        )

    def check_permissions(
        self,
        plan: ExecutionPlan,
    ) -> tuple[bool, list[str]]:
        """
        Check every permission required by the plan.
        """

        required_permissions = set(
            plan.metadata.get(
                "required_permissions",
                [],
            )
        )

        blocked = []

        for action in required_permissions:
            decision = (
                self.permission_manager.evaluate(
                    action
                )
            )

            if not decision.allowed:
                blocked.append(action)

        return (
            not blocked,
            sorted(blocked),
        )

    def execute_tool(
        self,
        tool_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Execute a registered tool through the Tool Registry.

        Every tool execution returns a standardized
        ToolResult.
        """

        return self.tool_registry.execute(
            tool_name,
            *args,
            **kwargs,
        )

    def verify_execution(
        self,
        plan: ExecutionPlan,
        completed_steps: int,
    ) -> bool:
        """
        Verify that all planned steps completed.

        More specific outcome verification will be connected
        to individual tools as the tool system grows.
        """

        if not plan.requires_verification:
            return True

        return (
            completed_steps == len(plan.steps)
            and plan.status
            == ExecutionStatus.RUNNING
        )

    def execute(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionResult:
        if not plan.steps:
            plan.status = ExecutionStatus.FAILED

            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=0,
                error=(
                    "Execution plan contains no steps."
                ),
            )

        valid, missing = self.validate_plan(plan)

        if not valid:
            plan.status = ExecutionStatus.FAILED

            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=len(plan.steps),
                error=(
                    "Required capabilities are unavailable."
                ),
                metadata={
                    "missing_capabilities": sorted(
                        missing
                    ),
                },
            )

        permissions_allowed, blocked = (
            self.check_permissions(plan)
        )

        if not permissions_allowed:
            plan.status = ExecutionStatus.FAILED

            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=len(plan.steps),
                error=(
                    "Required permissions were not granted."
                ),
                metadata={
                    "blocked_permissions": blocked,
                },
            )

        plan.status = ExecutionStatus.RUNNING

        completed_steps = 0

        required_capabilities = set(
            plan.metadata.get(
                "required_capabilities",
                [],
            )
        )

        available_tools = self.discover_tools(
            required_capabilities
        )

        if plan.requires_tools and not available_tools:
            plan.status = ExecutionStatus.FAILED

            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=len(plan.steps),
                error=(
                    "No executable tools are available "
                    "for the required capabilities."
                ),
            )

        for step in plan.steps:
            step.status = ExecutionStatus.RUNNING
            step.selected_tools = list(
                available_tools
            )

            try:
                if plan.requires_tools:
                    tool_name = available_tools[0]

                    tool_result = self.execute_tool(
                        tool_name,
                        plan.goal,
                    )

                    step.result = {
                        "status": "executed",
                        "tool": tool_name,
                        "result": tool_result.output,
                        "tool_result": tool_result,
                    }

                    if not tool_result.success:
                        step.status = ExecutionStatus.FAILED
                        step.error = (
                            tool_result.error
                            or (
                                "Tool execution failed "
                                "without an error message."
                            )
                        )

                        plan.status = ExecutionStatus.FAILED

                        return ExecutionResult(
                            success=False,
                            goal=plan.goal,
                            status=ExecutionStatus.FAILED,
                            completed_steps=completed_steps,
                            total_steps=len(plan.steps),
                            failed_step=step.step_number,
                            error=step.error,
                            metadata={
                                "available_tools": (
                                    available_tools
                                ),
                                "failed_tool": tool_name,
                                "tool_result": tool_result,
                            },
                        )

                else:
                    step.result = {
                        "status": "executed",
                    }

                step.status = ExecutionStatus.SUCCESS
                completed_steps += 1

            except Exception as exc:
                step.status = ExecutionStatus.FAILED
                step.error = str(exc)

                plan.status = ExecutionStatus.FAILED

                return ExecutionResult(
                    success=False,
                    goal=plan.goal,
                    status=ExecutionStatus.FAILED,
                    completed_steps=completed_steps,
                    total_steps=len(plan.steps),
                    failed_step=step.step_number,
                    error=str(exc),
                    metadata={
                        "available_tools": available_tools,
                    },
                )

        verified = self.verify_execution(
            plan,
            completed_steps,
        )

        if not verified:
            plan.status = ExecutionStatus.FAILED

            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=completed_steps,
                total_steps=len(plan.steps),
                error=(
                    "Execution completed but "
                    "verification failed."
                ),
                metadata={
                    "available_tools": available_tools,
                    "verified": False,
                },
            )

        plan.status = ExecutionStatus.SUCCESS

        return ExecutionResult(
            success=True,
            goal=plan.goal,
            status=ExecutionStatus.SUCCESS,
            completed_steps=completed_steps,
            total_steps=len(plan.steps),
            metadata={
                "requires_tools": plan.requires_tools,
                "requires_verification": (
                    plan.requires_verification
                ),
                "available_tools": available_tools,
                "verified": True,
            },
        )