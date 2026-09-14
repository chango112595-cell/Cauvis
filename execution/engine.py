from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from capabilities.registry import CapabilityRegistry
from execution.aem import AEMRegistry, AEMStrategy
from execution.planner import AdaptiveExecutionPlan
from execution.scheduler import WorkerScheduler
from execution.recovery import RecoveryEngine
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
        worker_scheduler: WorkerScheduler | None = None,
        aem_registry: AEMRegistry | None = None,
    ):
        self.capability_registry = capability_registry
        self.tool_registry = tool_registry
        self.permission_manager = permission_manager
        self.verification_engine = verification_engine
        self.worker_scheduler = worker_scheduler

        if aem_registry is not None:
            self.aem_registry = aem_registry
        elif worker_scheduler is not None:
            self.aem_registry = AEMRegistry(
                worker_scheduler
            )
        else:
            self.aem_registry = None

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

    def execute_adaptive(
        self,
        plan: AdaptiveExecutionPlan,
    ) -> ExecutionResult:
        """
        Execute an AdaptiveExecutionPlan through Cauvis AEMs
        and the worker scheduler.

        The legacy execute(ExecutionPlan) path remains separate
        so existing execution behavior stays backward compatible.
        """

        total_tasks = len(plan.tasks)

        if not plan.tasks:
            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=0,
                error=(
                    "Adaptive execution plan contains no tasks."
                ),
                metadata={
                    "execution_mode": "adaptive_aem",
                },
            )

        if (
            self.worker_scheduler is None
            or self.aem_registry is None
        ):
            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=total_tasks,
                error=(
                    "Adaptive execution requires a configured "
                    "WorkerScheduler and AEMRegistry."
                ),
                metadata={
                    "execution_mode": "adaptive_aem",
                },
            )

        required_capabilities: set[str] = set()

        for task in plan.tasks:
            required_capabilities.update(
                task.required_capabilities
            )

        missing_capabilities = (
            self.capability_registry.missing(
                required_capabilities
            )
        )

        if missing_capabilities:
            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=total_tasks,
                error=(
                    "Required adaptive execution "
                    "capabilities are unavailable."
                ),
                metadata={
                    "execution_mode": "adaptive_aem",
                    "missing_capabilities": sorted(
                        missing_capabilities
                    ),
                },
            )

        required_permissions = set(
            plan.metadata.get(
                "required_permissions",
                [],
            )
        )

        blocked_permissions = []

        for action in required_permissions:
            decision = (
                self.permission_manager.evaluate(
                    action
                )
            )

            if not decision.allowed:
                blocked_permissions.append(action)

        if blocked_permissions:
            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=total_tasks,
                error=(
                    "Required permissions were not granted."
                ),
                metadata={
                    "execution_mode": "adaptive_aem",
                    "blocked_permissions": sorted(
                        blocked_permissions
                    ),
                },
            )

        adaptive_aem = self.aem_registry.get(
            AEMStrategy.ADAPTIVE
        )

        if adaptive_aem is None:
            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=total_tasks,
                error=(
                    "Adaptive AEM is unavailable or disabled."
                ),
                metadata={
                    "execution_mode": "adaptive_aem",
                },
            )

        try:
            aem_result = adaptive_aem.execute(
                plan.tasks
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=0,
                total_steps=total_tasks,
                error=str(exc),
                metadata={
                    "execution_mode": "adaptive_aem",
                },
            )

        result_metadata = dict(
            aem_result.metadata
        )

        result_metadata.update(
            {
                "execution_mode": "adaptive_aem",
                "aem_strategy": (
                    aem_result.strategy.value
                ),
                "worker_results": (
                    aem_result.results
                ),
            }
        )

        if not aem_result.success:
            result_metadata["verified"] = False

            recovery_engine = RecoveryEngine(
                self.aem_registry
            )

            recovery_decision = (
                recovery_engine.decide(
                    plan.tasks,
                    aem_result,
                )
            )

            result_metadata[
                "recovery_decision"
            ] = {
                "action": (
                    recovery_decision.action.value
                ),
                "recoverable": (
                    recovery_decision.recoverable
                ),
                "reason": recovery_decision.reason,
                "failed_tasks": list(
                    recovery_decision.failed_tasks
                ),
                "metadata": dict(
                    recovery_decision.metadata
                ),
            }

            # Automatic recovery is intentionally limited
            # to single-task plans in Stage 3.
            #
            # Multi-task dependency plans may still contain
            # downstream work that must be resumed safely.
            if (
                total_tasks == 1
                and recovery_decision.recoverable
            ):
                recovery_result = (
                    recovery_engine.recover(
                        plan.tasks,
                        aem_result,
                    )
                )

                result_metadata[
                    "recovery_result"
                ] = {
                    "success": recovery_result.success,
                    "action": (
                        recovery_result.action.value
                    ),
                    "recovered_tasks": (
                        recovery_result.recovered_tasks
                    ),
                    "total_failed_tasks": (
                        recovery_result.total_failed_tasks
                    ),
                    "error": recovery_result.error,
                    "metadata": dict(
                        recovery_result.metadata
                    ),
                }

                recovery_aem_result = (
                    recovery_result.aem_result
                )

                recovery_verified = (
                    recovery_result.success
                    and recovery_aem_result
                    is not None
                    and recovery_aem_result.success
                    and recovery_aem_result.completed_tasks
                    == recovery_aem_result.total_tasks
                    == total_tasks
                )

                if recovery_verified:
                    result_metadata[
                        "original_worker_results"
                    ] = list(
                        aem_result.results
                    )

                    result_metadata[
                        "worker_results"
                    ] = list(
                        recovery_aem_result.results
                    )

                    result_metadata[
                        "recovered"
                    ] = True

                    result_metadata[
                        "verified"
                    ] = True

                    return ExecutionResult(
                        success=True,
                        goal=plan.goal,
                        status=ExecutionStatus.SUCCESS,
                        completed_steps=total_tasks,
                        total_steps=total_tasks,
                        metadata=result_metadata,
                    )

            # ------------------------------------------------
            # Stage 4: safe dependency-graph recovery + resume
            # ------------------------------------------------
            #
            # Ordinary multi-task strategies remain blocked
            # from automatic recovery. Only dependency graphs
            # can resume because they preserve successful
            # outputs and dependency state.
            #
            # total_tasks > 1 also prevents a single-task graph
            # from entering both the Stage 3 and Stage 4 paths.
            if (
                total_tasks > 1
                and recovery_decision.recoverable
                and aem_result.strategy
                == AEMStrategy.DEPENDENCY_GRAPH
            ):
                recovery_result = (
                    recovery_engine.recover(
                        plan.tasks,
                        aem_result,
                    )
                )

                result_metadata[
                    "recovery_result"
                ] = {
                    "success": recovery_result.success,
                    "action": (
                        recovery_result.action.value
                    ),
                    "recovered_tasks": (
                        recovery_result.recovered_tasks
                    ),
                    "total_failed_tasks": (
                        recovery_result.total_failed_tasks
                    ),
                    "error": recovery_result.error,
                    "metadata": dict(
                        recovery_result.metadata
                    ),
                }

                recovery_aem_result = (
                    recovery_result.aem_result
                )

                recovery_completed = (
                    recovery_result.success
                    and recovery_aem_result
                    is not None
                    and recovery_aem_result.success
                    and recovery_aem_result.completed_tasks
                    == recovery_aem_result.total_tasks
                    == recovery_result.total_failed_tasks
                )

                if recovery_completed:
                    resumed_result = (
                        recovery_engine.resume_dependency_graph(
                            plan.tasks,
                            aem_result,
                            recovery_result,
                        )
                    )

                    result_metadata[
                        "graph_resume_result"
                    ] = {
                        "success": resumed_result.success,
                        "completed_tasks": (
                            resumed_result.completed_tasks
                        ),
                        "total_tasks": (
                            resumed_result.total_tasks
                        ),
                        "error": resumed_result.error,
                        "metadata": dict(
                            resumed_result.metadata
                        ),
                    }

                    resume_verified = (
                        resumed_result.success
                        and resumed_result.completed_tasks
                        == resumed_result.total_tasks
                        == total_tasks
                    )

                    if resume_verified:
                        result_metadata[
                            "original_worker_results"
                        ] = list(
                            aem_result.results
                        )

                        result_metadata[
                            "recovery_worker_results"
                        ] = list(
                            recovery_aem_result.results
                        )

                        result_metadata[
                            "resume_worker_results"
                        ] = list(
                            resumed_result.results
                        )

                        result_metadata[
                            "worker_results"
                        ] = list(
                            resumed_result.results
                        )

                        result_metadata[
                            "outputs"
                        ] = dict(
                            resumed_result.metadata.get(
                                "outputs",
                                {},
                            )
                        )

                        result_metadata[
                            "recovered"
                        ] = True

                        result_metadata[
                            "resumed"
                        ] = True

                        result_metadata[
                            "verified"
                        ] = True

                        return ExecutionResult(
                            success=True,
                            goal=plan.goal,
                            status=ExecutionStatus.SUCCESS,
                            completed_steps=total_tasks,
                            total_steps=total_tasks,
                            metadata=result_metadata,
                        )

            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=(
                    aem_result.completed_tasks
                ),
                total_steps=(
                    aem_result.total_tasks
                ),
                error=(
                    aem_result.error
                    or "Adaptive AEM execution failed."
                ),
                metadata=result_metadata,
            )

        verified = (
            aem_result.completed_tasks
            == aem_result.total_tasks
            == total_tasks
        )

        if not verified:
            result_metadata["verified"] = False

            return ExecutionResult(
                success=False,
                goal=plan.goal,
                status=ExecutionStatus.FAILED,
                completed_steps=(
                    aem_result.completed_tasks
                ),
                total_steps=total_tasks,
                error=(
                    "Adaptive execution completed but "
                    "verification failed."
                ),
                metadata=result_metadata,
            )

        result_metadata["verified"] = True

        return ExecutionResult(
            success=True,
            goal=plan.goal,
            status=ExecutionStatus.SUCCESS,
            completed_steps=(
                aem_result.completed_tasks
            ),
            total_steps=total_tasks,
            metadata=result_metadata,
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