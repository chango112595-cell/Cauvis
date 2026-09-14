from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from execution.workers import (
    Worker,
    WorkerRegistry,
    WorkerResult,
    WorkerTask,
    WorkerTaskType,
)


class SchedulingStrategy(str, Enum):
    """
    Determines how the scheduler selects a worker.
    """

    ROUND_ROBIN = "round_robin"
    LEAST_BUSY = "least_busy"
    PRIORITY = "priority"


@dataclass
class DispatchRecord:
    """
    Record of a task dispatched to a worker.
    """

    task_id: str
    task_name: str
    worker_name: str
    success: bool
    execution_time: float
    error: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class SchedulerResult:
    """
    Standard result returned by the scheduler.
    """

    success: bool
    worker_name: str | None = None
    worker_result: WorkerResult | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class WorkerScheduler:
    """
    Selects and dispatches work to the best available worker.

    The scheduler is responsible for worker selection.

    It does NOT:
    - grant permissions
    - bypass security
    - execute tools directly
    - verify task outcomes

    Those responsibilities belong to other Cauvis systems.
    """

    def __init__(
        self,
        registry: WorkerRegistry,
        strategy: SchedulingStrategy = (
            SchedulingStrategy.ROUND_ROBIN
        ),
    ):
        self.registry = registry
        self.strategy = strategy

        self._round_robin_index = 0

        self._history: list[
            DispatchRecord
        ] = []

    # ---------------------------------------------------------
    # Strategy management
    # ---------------------------------------------------------

    def set_strategy(
        self,
        strategy: SchedulingStrategy,
    ) -> None:
        self.strategy = strategy

    def get_strategy(
        self,
    ) -> SchedulingStrategy:
        return self.strategy

    # ---------------------------------------------------------
    # Worker discovery
    # ---------------------------------------------------------

    def find_candidates(
        self,
        task: WorkerTask,
    ) -> list[Worker]:
        """
        Find enabled workers capable of handling the task.

        A worker must support:
        1. The task type
        2. All required capabilities
        """

        candidates = []

        for worker in self.registry.list_enabled():

            if not worker.can_handle(task):
                continue

            candidates.append(worker)

        return candidates

    # ---------------------------------------------------------
    # Worker selection
    # ---------------------------------------------------------

    def select_worker(
        self,
        task: WorkerTask,
    ) -> Worker | None:

        candidates = self.find_candidates(task)

        if not candidates:
            return None

        if self.strategy == (
            SchedulingStrategy.ROUND_ROBIN
        ):
            worker = candidates[
                self._round_robin_index
                % len(candidates)
            ]

            self._round_robin_index += 1

            return worker

        if self.strategy == (
            SchedulingStrategy.LEAST_BUSY
        ):
            return min(
                candidates,
                key=lambda worker: (
                    worker.metrics.tasks_started
                    - worker.metrics.tasks_completed
                    - worker.metrics.tasks_failed
                ),
            )

        if self.strategy == (
            SchedulingStrategy.PRIORITY
        ):
            return min(
                candidates,
                key=lambda worker: (
                    worker.metrics.tasks_started
                    - worker.metrics.tasks_completed
                    - worker.metrics.tasks_failed,
                    -worker.metrics.average_execution_time(),
                ),
            )

        return candidates[0]

    # ---------------------------------------------------------
    # Dispatch
    # ---------------------------------------------------------

    def dispatch(
        self,
        task: WorkerTask,
    ) -> SchedulerResult:

        worker = self.select_worker(task)

        if worker is None:
            error = (
                "No capable worker is available "
                f"for task '{task.name}'. "
                f"Task type: {task.task_type.value}. "
                f"Required capabilities: "
                f"{sorted(task.required_capabilities)}"
            )

            return SchedulerResult(
                success=False,
                error=error,
            )

        return self.dispatch_to_worker(
            worker,
            task,
        )

    def dispatch_to_worker(
        self,
        worker: Worker,
        task: WorkerTask,
    ) -> SchedulerResult:
        """
        Dispatch a task to a specific already-selected worker.

        This is used when the caller must preserve an explicit
        worker choice, such as fallback execution.
        """

        if not worker.can_handle(task):
            error = (
                f"Worker '{worker.name}' cannot handle "
                f"task '{task.name}'."
            )

            return SchedulerResult(
                success=False,
                worker_name=worker.name,
                error=error,
            )

        worker_result = worker.execute(task)

        record = DispatchRecord(
            task_id=str(task.task_id),
            task_name=task.name,
            worker_name=worker.name,
            success=worker_result.success,
            execution_time=(
                worker_result.execution_time
            ),
            error=worker_result.error,
            metadata={
                "task_type": task.task_type.value,
                "required_capabilities": sorted(
                    task.required_capabilities
                ),
            },
        )

        self._history.append(record)

        return SchedulerResult(
            success=worker_result.success,
            worker_name=worker.name,
            worker_result=worker_result,
            error=worker_result.error,
            metadata={
                "task_type": task.task_type.value,
                "worker_capabilities": sorted(
                    worker.capabilities
                ),
            },
        )

    # ---------------------------------------------------------
    # History
    # ---------------------------------------------------------

    def history(
        self,
    ) -> list[DispatchRecord]:

        return list(self._history)

    def clear_history(
        self,
    ) -> None:

        self._history.clear()

    def history_count(
        self,
    ) -> int:

        return len(self._history)

    # ---------------------------------------------------------
    # Metrics
    # ---------------------------------------------------------

    def worker_load(
        self,
    ) -> dict[str, int]:

        load: dict[str, int] = {}

        for worker in self.registry.list_all():

            active_load = (
                worker.metrics.tasks_started
                - worker.metrics.tasks_completed
                - worker.metrics.tasks_failed
            )

            load[worker.name] = max(
                0,
                active_load,
            )

        return load

    def worker_success_rates(
        self,
    ) -> dict[str, float]:

        rates: dict[str, float] = {}

        for worker in self.registry.list_all():

            started = worker.metrics.tasks_started

            if started == 0:
                rates[worker.name] = 0.0
                continue

            completed = (
                worker.metrics.tasks_completed
            )

            rates[worker.name] = (
                completed / started
            )

        return rates

    # ---------------------------------------------------------
    # Diagnostics
    # ---------------------------------------------------------

    def task_type_summary(
        self,
    ) -> dict[str, list[str]]:

        summary: dict[
            str,
            list[str],
        ] = {}

        for worker in self.registry.list_enabled():

            for task_type in worker.task_types:

                key = task_type.value

                summary.setdefault(
                    key,
                    [],
                )

                summary[key].append(
                    worker.name
                )

        return summary

    def capability_summary(
        self,
    ) -> dict[str, list[str]]:

        summary: dict[
            str,
            list[str],
        ] = {}

        for worker in self.registry.list_enabled():

            for capability in worker.capabilities:

                summary.setdefault(
                    capability,
                    [],
                )

                summary[capability].append(
                    worker.name
                )

        return summary