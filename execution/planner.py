from dataclasses import dataclass, field
from typing import Any

from intelligence.reasoning import ReasoningResult
from intelligence.task import TaskComplexity
from execution.aem import AEMTask
from execution.workers import WorkerTaskType


@dataclass
class PlannedTask:
    """A planned execution task before it becomes an AEMTask."""

    name: str
    description: str
    task_type: WorkerTaskType = WorkerTaskType.GENERAL
    priority: int = 100
    required_capabilities: set[str] = field(default_factory=set)
    dependencies: set[str] = field(default_factory=set)
    payload: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdaptiveExecutionPlan:
    """Executable plan produced from Cauvis reasoning."""

    goal: str
    tasks: list[AEMTask] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AdaptiveTaskPlanner:
    """
    Converts a ReasoningResult into executable AEMTasks.

    The planner does not execute anything.
    It determines what should happen, in what order,
    which capabilities are required, and what context
    should be passed into execution.
    """

    def build_plan(
        self,
        reasoning: ReasoningResult,
    ) -> AdaptiveExecutionPlan:

        if not reasoning.goal or reasoning.goal == "empty_request":
            return AdaptiveExecutionPlan(
                goal=reasoning.goal,
                tasks=[],
                metadata={
                    "empty": True,
                    "task_count": 0,
                },
            )

        original_request = reasoning.goal

        tasks: list[PlannedTask] = []

        # Every real task starts by understanding the objective.
        tasks.append(
            PlannedTask(
                name="understand_goal",
                description="Understand the user's requested outcome.",
                task_type=WorkerTaskType.GENERAL,
                priority=10,
                required_capabilities={"chat"},
                payload=original_request,
                metadata={
                    "stage": "understanding",
                },
            )
        )

        requirements = reasoning.task_requirements

        if requirements is not None:

            # Internet research.
            if requirements.requires_internet:
                tasks.append(
                    PlannedTask(
                        name="research",
                        description=(
                            "Gather information requiring "
                            "internet access."
                        ),
                        task_type=WorkerTaskType.RESEARCH,
                        priority=20,
                        required_capabilities={"web"},
                        dependencies={"understand_goal"},
                        payload=original_request,
                        metadata={
                            "stage": "research",
                            "original_request": original_request,
                        },
                    )
                )

            # Vision work uses a GENERAL worker for now.
            #
            # "vision" is a capability requirement rather than
            # a dedicated WorkerTaskType in the current architecture.
            if requirements.requires_vision:
                tasks.append(
                    PlannedTask(
                        name="analyze_vision",
                        description=(
                            "Process the required visual "
                            "information."
                        ),
                        task_type=WorkerTaskType.GENERAL,
                        priority=20,
                        required_capabilities={"vision"},
                        dependencies={"understand_goal"},
                        payload=original_request,
                        metadata={
                            "stage": "vision",
                            "original_request": original_request,
                        },
                    )
                )

            # Code implementation.
            if requirements.requires_code:
                dependencies = {"understand_goal"}

                if requirements.requires_internet:
                    dependencies.add("research")

                if requirements.requires_vision:
                    dependencies.add("analyze_vision")

                tasks.append(
                    PlannedTask(
                        name="implementation",
                        description=(
                            "Determine and prepare the required "
                            "implementation."
                        ),
                        task_type=WorkerTaskType.CODE,
                        priority=30,
                        required_capabilities={"code"},
                        dependencies=dependencies,
                        payload=original_request,
                        metadata={
                            "stage": "implementation",
                            "original_request": original_request,
                        },
                    )
                )

            # Tool execution.
            if requirements.requires_tools:
                dependencies = {"understand_goal"}

                if requirements.requires_internet:
                    dependencies.add("research")

                if requirements.requires_vision:
                    dependencies.add("analyze_vision")

                if requirements.requires_code:
                    dependencies.add("implementation")

                tasks.append(
                    PlannedTask(
                        name="tool_execution",
                        description=(
                            "Execute the tools required to "
                            "accomplish the task."
                        ),
                        task_type=WorkerTaskType.GENERAL,
                        priority=40,
                        required_capabilities={"tools"},
                        dependencies=dependencies,
                        payload=original_request,
                        metadata={
                            "stage": "tool_execution",
                            "original_request": original_request,
                        },
                    )
                )

            # Long-context processing.
            if requirements.requires_long_context:
                dependencies = {"understand_goal"}

                if requirements.requires_internet:
                    dependencies.add("research")

                tasks.append(
                    PlannedTask(
                        name="context_processing",
                        description=(
                            "Gather and manage required "
                            "long-context information."
                        ),
                        task_type=WorkerTaskType.GENERAL,
                        priority=30,
                        required_capabilities={"long_context"},
                        dependencies=dependencies,
                        payload=original_request,
                        metadata={
                            "stage": "context_processing",
                            "original_request": original_request,
                        },
                    )
                )

        # Determine dependencies for finalization.
        #
        # Everything planned must complete before Cauvis
        # produces the final result.
        final_dependencies = {
            task.name
            for task in tasks
            if task.name != "understand_goal"
        }

        if not final_dependencies:
            final_dependencies = {"understand_goal"}

        tasks.append(
            PlannedTask(
                name="finalize",
                description=(
                    "Produce the requested outcome "
                    "from completed work."
                ),
                task_type=WorkerTaskType.GENERAL,
                priority=50,
                required_capabilities={"chat"},
                dependencies=final_dependencies,
                payload=original_request,
                metadata={
                    "stage": "finalization",
                    "original_request": original_request,
                },
            )
        )

        # Verification is deliberately a separate executable task.
        if reasoning.requires_verification:
            tasks.append(
                PlannedTask(
                    name="verify_result",
                    description=(
                        "Verify that the requested outcome "
                        "was actually achieved."
                    ),
                    task_type=WorkerTaskType.VERIFICATION,
                    priority=60,
                    required_capabilities={"verification"},
                    dependencies={"finalize"},
                    payload=original_request,
                    metadata={
                        "stage": "verification",
                        "original_request": original_request,
                    },
                )
            )

        # Convert PlannedTasks into the AEMTask format already
        # understood by the execution system.
        aem_tasks = [
            AEMTask(
                name=task.name,
                payload=task.payload,
                priority=task.priority,
                task_type=task.task_type,
                required_capabilities=set(
                    task.required_capabilities
                ),
                dependencies=set(task.dependencies),
                metadata={
                    "description": task.description,
                    **task.metadata,
                },
            )
            for task in tasks
        ]

        return AdaptiveExecutionPlan(
            goal=original_request,
            tasks=aem_tasks,
            metadata={
                "task_count": len(aem_tasks),
                "complexity": (
                    requirements.complexity.value
                    if requirements is not None
                    else TaskComplexity.LOW.value
                ),
                "requires_verification": (
                    reasoning.requires_verification
                ),
                "adaptive": True,
                "original_request": original_request,
            },
        )