from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from execution.aem import (
    AEMResult,
    AEMStrategy,
    AEMTask,
    AEMRegistry,
)


class RecoveryAction(str, Enum):
    """
    High-level action selected by the Cauvis recovery policy.
    """

    NONE = "none"
    RETRY = "retry"
    FALLBACK = "fallback"
    ABORT = "abort"


@dataclass
class RecoveryDecision:
    """
    Decision produced after inspecting a failed AEM execution.
    """

    action: RecoveryAction
    recoverable: bool
    reason: str

    failed_tasks: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class RecoveryResult:
    """
    Standard result returned by recovery execution.

    Stage 2 introduces this contract before automatic
    recovery execution is connected.
    """

    success: bool
    action: RecoveryAction
    recovered_tasks: int
    total_failed_tasks: int

    aem_result: AEMResult | None = None
    error: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class RecoveryEngine:
    """
    Cauvis execution recovery policy.

    Version 1 decides whether recovery should occur and
    which existing recovery strategy should be preferred.

    It does not yet execute recovery. Retry and fallback
    execution remain owned by the existing AEM runtime.
    """

    def __init__(
        self,
        aem_registry: AEMRegistry,
    ):
        self.aem_registry = aem_registry

    def prepare_recovery_tasks(
        self,
        tasks: list[AEMTask],
        result: AEMResult,
        decision: RecoveryDecision,
    ) -> tuple[list[AEMTask], str | None]:
        """
        Prepare isolated failed tasks for retry or fallback.

        Successful dependency tasks are not replayed.
        Their saved outputs are used to reconstruct the same
        effective payload originally supplied to the failed task.
        """

        if (
            not decision.recoverable
            or decision.action not in {
                RecoveryAction.RETRY,
                RecoveryAction.FALLBACK,
            }
        ):
            return [], (
                "Recovery decision does not permit "
                "automatic execution."
            )

        task_map = {
            task.name: task
            for task in tasks
        }

        saved_outputs = dict(
            result.metadata.get(
                "outputs",
                {},
            )
        )

        prepared_tasks = []

        for task_name in decision.failed_tasks:
            original_task = task_map.get(
                task_name
            )

            if original_task is None:
                return [], (
                    "Failed task is missing from the "
                    f"original plan: {task_name}"
                )

            if not original_task.metadata.get(
                "recovery_safe",
                False,
            ):
                return [], (
                    f"Automatic recovery is not allowed "
                    f"for task '{task_name}'. "
                    "Set recovery_safe=True only when "
                    "repeating the task is known to be safe."
                )

            missing_dependencies = (
                set(original_task.dependencies)
                - set(saved_outputs)
            )

            if missing_dependencies:
                return [], (
                    f"Cannot recover task '{task_name}' "
                    "because dependency outputs are missing: "
                    + ", ".join(
                        sorted(
                            missing_dependencies
                        )
                    )
                )

            dependency_outputs = {
                dependency: saved_outputs[
                    dependency
                ]
                for dependency
                in original_task.dependencies
            }

            if not dependency_outputs:
                payload = original_task.payload

            elif len(dependency_outputs) == 1:
                payload = next(
                    iter(
                        dependency_outputs.values()
                    )
                )

            else:
                payload = {
                    "dependencies": dict(
                        dependency_outputs
                    ),
                    "input": original_task.payload,
                }

            recovery_metadata = dict(
                original_task.metadata
            )

            recovery_metadata.update(
                {
                    "recovery": True,
                    "recovery_action": (
                        decision.action.value
                    ),
                    "original_dependencies": sorted(
                        original_task.dependencies
                    ),
                    "recovery_exclude_workers": list(
                        decision.metadata.get(
                            "failed_workers",
                            [],
                        )
                    ),
                }
            )

            prepared_tasks.append(
                AEMTask(
                    name=original_task.name,
                    payload=payload,
                    priority=original_task.priority,
                    task_type=original_task.task_type,
                    required_capabilities=set(
                        original_task.required_capabilities
                    ),
                    metadata=recovery_metadata,
                    dependencies=set(),
                )
            )

        if not prepared_tasks:
            return [], (
                "No failed tasks were available "
                "for recovery."
            )

        return prepared_tasks, None

    def recover(
        self,
        tasks: list[AEMTask],
        result: AEMResult,
    ) -> RecoveryResult:
        """
        Execute a safe recovery decision using existing AEMs.

        Recovery never bypasses the recovery_safe gate and
        does not replay already-successful dependency tasks.
        """

        decision = self.decide(
            tasks,
            result,
        )

        if decision.action == RecoveryAction.NONE:
            return RecoveryResult(
                success=True,
                action=RecoveryAction.NONE,
                recovered_tasks=0,
                total_failed_tasks=0,
                metadata={
                    "decision_reason": decision.reason,
                    "recovery_required": False,
                },
            )

        if (
            decision.action == RecoveryAction.ABORT
            or not decision.recoverable
        ):
            return RecoveryResult(
                success=False,
                action=RecoveryAction.ABORT,
                recovered_tasks=0,
                total_failed_tasks=len(
                    decision.failed_tasks
                ),
                error=decision.reason,
                metadata={
                    "decision_reason": decision.reason,
                    "failed_tasks": list(
                        decision.failed_tasks
                    ),
                },
            )

        recovery_tasks, preparation_error = (
            self.prepare_recovery_tasks(
                tasks,
                result,
                decision,
            )
        )

        if preparation_error is not None:
            return RecoveryResult(
                success=False,
                action=RecoveryAction.ABORT,
                recovered_tasks=0,
                total_failed_tasks=len(
                    decision.failed_tasks
                ),
                error=preparation_error,
                metadata={
                    "requested_action": (
                        decision.action.value
                    ),
                    "decision_reason": decision.reason,
                    "failed_tasks": list(
                        decision.failed_tasks
                    ),
                },
            )

        strategy_map = {
            RecoveryAction.RETRY: AEMStrategy.RETRY,
            RecoveryAction.FALLBACK: AEMStrategy.FALLBACK,
        }

        strategy = strategy_map.get(
            decision.action
        )

        if strategy is None:
            return RecoveryResult(
                success=False,
                action=RecoveryAction.ABORT,
                recovered_tasks=0,
                total_failed_tasks=len(
                    decision.failed_tasks
                ),
                error=(
                    "Recovery action has no executable "
                    "AEM strategy."
                ),
            )

        recovery_aem = self.aem_registry.get(
            strategy
        )

        if recovery_aem is None:
            return RecoveryResult(
                success=False,
                action=RecoveryAction.ABORT,
                recovered_tasks=0,
                total_failed_tasks=len(
                    decision.failed_tasks
                ),
                error=(
                    f"Recovery AEM is unavailable: "
                    f"{strategy.value}"
                ),
                metadata={
                    "requested_action": (
                        decision.action.value
                    ),
                },
            )

        try:
            recovery_result = recovery_aem.execute(
                recovery_tasks
            )

        except Exception as exc:
            return RecoveryResult(
                success=False,
                action=decision.action,
                recovered_tasks=0,
                total_failed_tasks=len(
                    decision.failed_tasks
                ),
                error=str(exc),
                metadata={
                    "recovery_strategy": (
                        strategy.value
                    ),
                    "failed_tasks": list(
                        decision.failed_tasks
                    ),
                },
            )

        return RecoveryResult(
            success=recovery_result.success,
            action=decision.action,
            recovered_tasks=(
                recovery_result.completed_tasks
            ),
            total_failed_tasks=len(
                decision.failed_tasks
            ),
            aem_result=recovery_result,
            error=recovery_result.error,
            metadata={
                "recovery_strategy": strategy.value,
                "decision_reason": decision.reason,
                "failed_tasks": list(
                    decision.failed_tasks
                ),
                "prepared_tasks": [
                    task.name
                    for task in recovery_tasks
                ],
                "decision_metadata": dict(
                    decision.metadata
                ),
            },
        )

    def resume_dependency_graph(
        self,
        tasks: list[AEMTask],
        original_result: AEMResult,
        recovery_result: RecoveryResult,
    ) -> AEMResult:
        """
        Resume an interrupted dependency graph after its
        failed tasks have recovered successfully.

        Previously successful outputs and newly recovered
        outputs are seeded into DependencyGraphAEM.resume().
        Seeded tasks are not dispatched again.
        """

        original_metadata = dict(
            original_result.metadata
        )

        if not original_metadata.get(
            "dependency_graph",
            False,
        ):
            return AEMResult(
                success=False,
                strategy=AEMStrategy.DEPENDENCY_GRAPH,
                completed_tasks=0,
                total_tasks=len(tasks),
                results=[],
                error=(
                    "Graph resume requires an original "
                    "dependency graph result."
                ),
                metadata={
                    "dependency_graph": True,
                    "resume_failed": True,
                    "resume_rejected": True,
                },
            )

        if (
            not recovery_result.success
            or recovery_result.aem_result is None
            or not recovery_result.aem_result.success
        ):
            return AEMResult(
                success=False,
                strategy=AEMStrategy.DEPENDENCY_GRAPH,
                completed_tasks=(
                    original_result.completed_tasks
                ),
                total_tasks=len(tasks),
                results=[],
                error=(
                    "Dependency graph cannot resume because "
                    "recovery did not complete successfully."
                ),
                metadata={
                    "dependency_graph": True,
                    "resume_failed": True,
                    "recovery_action": (
                        recovery_result.action.value
                    ),
                },
            )

        saved_outputs = dict(
            original_metadata.get(
                "outputs",
                {},
            )
        )

        failed_tasks = list(
            recovery_result.metadata.get(
                "failed_tasks",
                [],
            )
        )

        recovered_outputs = {}

        for worker_result in (
            recovery_result.aem_result.results
        ):

            if not worker_result.success:
                continue

            task_name = (
                worker_result.metadata.get(
                    "task_name"
                )
            )

            if (
                task_name
                and task_name in failed_tasks
            ):
                recovered_outputs[
                    task_name
                ] = worker_result.output

        missing_recovered_tasks = (
            set(failed_tasks)
            - set(recovered_outputs)
        )

        if missing_recovered_tasks:
            return AEMResult(
                success=False,
                strategy=AEMStrategy.DEPENDENCY_GRAPH,
                completed_tasks=len(
                    saved_outputs
                ),
                total_tasks=len(tasks),
                results=[],
                error=(
                    "Recovered outputs are missing for: "
                    + ", ".join(
                        sorted(
                            missing_recovered_tasks
                        )
                    )
                ),
                metadata={
                    "dependency_graph": True,
                    "resume_failed": True,
                    "failed_tasks": failed_tasks,
                    "recovered_outputs": dict(
                        recovered_outputs
                    ),
                },
            )

        output_overlap = (
            set(saved_outputs)
            & set(recovered_outputs)
        )

        if output_overlap:
            return AEMResult(
                success=False,
                strategy=AEMStrategy.DEPENDENCY_GRAPH,
                completed_tasks=len(
                    saved_outputs
                ),
                total_tasks=len(tasks),
                results=[],
                error=(
                    "Resume state contains conflicting "
                    "successful and recovered outputs for: "
                    + ", ".join(
                        sorted(
                            output_overlap
                        )
                    )
                ),
                metadata={
                    "dependency_graph": True,
                    "resume_failed": True,
                    "output_conflict": sorted(
                        output_overlap
                    ),
                },
            )

        merged_outputs = dict(
            saved_outputs
        )

        merged_outputs.update(
            recovered_outputs
        )

        graph_aem = self.aem_registry.get(
            AEMStrategy.DEPENDENCY_GRAPH
        )

        if graph_aem is None:
            return AEMResult(
                success=False,
                strategy=AEMStrategy.DEPENDENCY_GRAPH,
                completed_tasks=len(
                    merged_outputs
                ),
                total_tasks=len(tasks),
                results=[],
                error=(
                    "Dependency Graph AEM is unavailable "
                    "for resume."
                ),
                metadata={
                    "dependency_graph": True,
                    "resume_failed": True,
                },
            )

        resume_method = getattr(
            graph_aem,
            "resume",
            None,
        )

        if not callable(resume_method):
            return AEMResult(
                success=False,
                strategy=AEMStrategy.DEPENDENCY_GRAPH,
                completed_tasks=len(
                    merged_outputs
                ),
                total_tasks=len(tasks),
                results=[],
                error=(
                    "Dependency Graph AEM does not support "
                    "resume execution."
                ),
                metadata={
                    "dependency_graph": True,
                    "resume_failed": True,
                },
            )

        try:
            resumed_result = resume_method(
                tasks,
                merged_outputs,
            )

        except Exception as exc:
            return AEMResult(
                success=False,
                strategy=AEMStrategy.DEPENDENCY_GRAPH,
                completed_tasks=len(
                    merged_outputs
                ),
                total_tasks=len(tasks),
                results=[],
                error=str(exc),
                metadata={
                    "dependency_graph": True,
                    "resume_failed": True,
                },
            )

        resumed_result.metadata.update(
            {
                "resumed": True,
                "recovery_action": (
                    recovery_result.action.value
                ),
                "original_completed_outputs": sorted(
                    saved_outputs
                ),
                "recovered_outputs": dict(
                    recovered_outputs
                ),
                "resume_seeded_tasks": sorted(
                    merged_outputs
                ),
            }
        )

        return resumed_result

    def decide(
        self,
        tasks: list[AEMTask],
        result: AEMResult,
    ) -> RecoveryDecision:
        """
        Inspect an AEM result and select a safe recovery action.
        """

        if result.success:
            return RecoveryDecision(
                action=RecoveryAction.NONE,
                recoverable=False,
                reason=(
                    "Execution succeeded. "
                    "Recovery is not required."
                ),
            )

        metadata = dict(result.metadata)

        raw_failed_tasks = metadata.get(
            "failed_tasks",
            [],
        )

        if isinstance(raw_failed_tasks, str):
            failed_tasks = [
                raw_failed_tasks
            ]

        elif isinstance(
            raw_failed_tasks,
            (list, tuple, set),
        ):
            failed_tasks = [
                task_name
                for task_name in raw_failed_tasks
                if (
                    isinstance(task_name, str)
                    and task_name
                )
            ]

        else:
            # Some AEMs, such as ParallelAEM,
            # report failed_tasks as a numeric count.
            # Task names will be recovered below from
            # failed WorkerResult metadata when available.
            failed_tasks = []

        if metadata.get("validation_failed"):
            return RecoveryDecision(
                action=RecoveryAction.ABORT,
                recoverable=False,
                reason=(
                    "Execution failed structural validation. "
                    "Retrying cannot repair the execution graph."
                ),
                failed_tasks=failed_tasks,
                metadata={
                    "original_strategy": (
                        result.strategy.value
                    ),
                    "validation_failed": True,
                },
            )

        failed_worker_results = [
            worker_result
            for worker_result in result.results
            if not worker_result.success
        ]

        if (
            not failed_tasks
            and failed_worker_results
        ):
            known_task_names = {
                task.name
                for task in tasks
            }

            recovered_names = []

            for worker_result in failed_worker_results:
                task_name = worker_result.metadata.get(
                    "task_name"
                )

                if (
                    task_name
                    and task_name in known_task_names
                    and task_name not in recovered_names
                ):
                    recovered_names.append(
                        task_name
                    )

            failed_tasks = recovered_names

        fallback_available = (
            self.aem_registry.has(
                AEMStrategy.FALLBACK
            )
        )

        retry_available = (
            self.aem_registry.has(
                AEMStrategy.RETRY
            )
        )

        failed_worker_names = {
            worker_result.worker_name
            for worker_result
            in failed_worker_results
        }

        task_map = {
            task.name: task
            for task in tasks
        }

        alternate_workers = {}

        for task_name in failed_tasks:
            task = task_map.get(task_name)

            if task is None:
                continue

            candidates = (
                self.aem_registry.scheduler.find_candidates(
                    task.to_worker_task()
                )
            )

            alternates = [
                worker.name
                for worker in candidates
                if worker.name
                not in failed_worker_names
            ]

            if alternates:
                alternate_workers[
                    task_name
                ] = alternates

        fallback_possible = (
            fallback_available
            and bool(failed_tasks)
            and all(
                task_name in alternate_workers
                for task_name in failed_tasks
            )
        )

        if failed_worker_results:
            if fallback_possible:
                return RecoveryDecision(
                    action=RecoveryAction.FALLBACK,
                    recoverable=True,
                    reason=(
                        "Worker execution failed and an "
                        "alternate capable worker is available."
                    ),
                    failed_tasks=failed_tasks,
                    metadata={
                        "original_strategy": (
                            result.strategy.value
                        ),
                        "failed_workers": sorted(
                            failed_worker_names
                        ),
                        "alternate_workers": (
                            alternate_workers
                        ),
                    },
                )

            if retry_available:
                return RecoveryDecision(
                    action=RecoveryAction.RETRY,
                    recoverable=True,
                    reason=(
                        "Worker execution failed and the "
                        "retry AEM is available."
                    ),
                    failed_tasks=failed_tasks,
                    metadata={
                        "original_strategy": (
                            result.strategy.value
                        ),
                        "failed_workers": sorted(
                            failed_worker_names
                        ),
                    },
                )

        return RecoveryDecision(
            action=RecoveryAction.ABORT,
            recoverable=False,
            reason=(
                "No safe automatic recovery action "
                "was identified."
            ),
            failed_tasks=failed_tasks,
            metadata={
                "original_strategy": (
                    result.strategy.value
                ),
                "original_error": result.error,
            },
        )
