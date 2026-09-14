from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from uuid import UUID, uuid4
import time


class WorkerStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DISABLED = "disabled"


class WorkerTaskType(str, Enum):
    GENERAL = "general"
    RESEARCH = "research"
    CODE = "code"
    FILE = "file"
    SYSTEM = "system"
    VERIFICATION = "verification"


@dataclass
class WorkerTask:
    name: str
    payload: Any = None
    task_type: WorkerTaskType = WorkerTaskType.GENERAL
    priority: int = 100
    task_id: UUID = field(default_factory=uuid4)
    required_capabilities: set[str] = field(
        default_factory=set
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class WorkerResult:
    success: bool
    worker_name: str
    task_id: UUID
    output: Any = None
    error: str | None = None
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class WorkerMetrics:
    tasks_started: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    last_execution_time: float = 0.0
    last_task_id: UUID | None = None

    def average_execution_time(self) -> float:
        if self.tasks_completed == 0:
            return 0.0

        return (
            self.total_execution_time
            / self.tasks_completed
        )


class Worker:
    """
    Lightweight execution worker.

    Workers perform work assigned by the scheduler.
    They do not make security decisions.
    """

    def __init__(
        self,
        name: str,
        description: str,
        capabilities: set[str] | None = None,
        task_types: set[WorkerTaskType] | None = None,
        handler: Callable[
            [WorkerTask],
            Any
        ] | None = None,
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ):
        self.name = name
        self.description = description

        self.capabilities = (
            set(capabilities)
            if capabilities
            else set()
        )

        self.task_types = (
            set(task_types)
            if task_types
            else {WorkerTaskType.GENERAL}
        )

        self.handler = handler
        self.enabled = enabled

        self.status = (
            WorkerStatus.IDLE
            if enabled
            else WorkerStatus.DISABLED
        )

        self.metrics = WorkerMetrics()

        self.metadata = (
            dict(metadata)
            if metadata
            else {}
        )

    def can_handle(
        self,
        task: WorkerTask,
    ) -> bool:
        """
        Determine whether this worker can handle
        the supplied task.
        """

        if not self.enabled:
            return False

        if self.status == WorkerStatus.DISABLED:
            return False

        if (
            task.task_type
            not in self.task_types
            and WorkerTaskType.GENERAL
            not in self.task_types
        ):
            return False

        if not task.required_capabilities.issubset(
            self.capabilities
        ):
            return False

        return True

    def execute(
        self,
        task: WorkerTask,
    ) -> WorkerResult:

        if not self.enabled:
            return WorkerResult(
                success=False,
                worker_name=self.name,
                task_id=task.task_id,
                error="Worker is disabled.",
                metadata={
                    "task_name": task.name,
                },
            )

        if not self.can_handle(task):
            return WorkerResult(
                success=False,
                worker_name=self.name,
                task_id=task.task_id,
                error=(
                    "Worker cannot handle "
                    f"task '{task.name}'."
                ),
                metadata={
                    "task_name": task.name,
                },
            )

        if self.handler is None:
            return WorkerResult(
                success=False,
                worker_name=self.name,
                task_id=task.task_id,
                error="Worker has no handler.",
                metadata={
                    "task_name": task.name,
                },
            )

        self.status = WorkerStatus.RUNNING

        self.metrics.tasks_started += 1
        self.metrics.last_task_id = task.task_id

        start_time = time.perf_counter()

        try:
            output = self.handler(task)

            execution_time = (
                time.perf_counter()
                - start_time
            )

            self.metrics.tasks_completed += 1
            self.metrics.total_execution_time += (
                execution_time
            )
            self.metrics.last_execution_time = (
                execution_time
            )

            self.status = WorkerStatus.SUCCESS

            return WorkerResult(
                success=True,
                worker_name=self.name,
                task_id=task.task_id,
                output=output,
                execution_time=execution_time,
                metadata={
                    "task_name": task.name,
                },
            )

        except Exception as exc:

            execution_time = (
                time.perf_counter()
                - start_time
            )

            self.metrics.tasks_failed += 1
            self.metrics.last_execution_time = (
                execution_time
            )

            self.status = WorkerStatus.FAILED

            return WorkerResult(
                success=False,
                worker_name=self.name,
                task_id=task.task_id,
                execution_time=execution_time,
                error=str(exc),
                metadata={
                    "task_name": task.name,
                },
            )

        finally:
            if self.enabled:
                self.status = WorkerStatus.IDLE

    def disable(self) -> None:
        self.enabled = False
        self.status = WorkerStatus.DISABLED

    def enable(self) -> None:
        self.enabled = True
        self.status = WorkerStatus.IDLE


class WorkerRegistry:
    """
    Registry of all available workers.
    """

    def __init__(self):
        self._workers: dict[
            str,
            Worker
        ] = {}

    def register(
        self,
        worker: Worker,
    ) -> None:

        self._workers[
            worker.name
        ] = worker

    def unregister(
        self,
        worker_name: str,
    ) -> None:

        self._workers.pop(
            worker_name,
            None,
        )

    def get(
        self,
        worker_name: str,
    ) -> Worker | None:

        return self._workers.get(
            worker_name
        )

    def has(
        self,
        worker_name: str,
    ) -> bool:

        return worker_name in self._workers

    def list_all(
        self,
    ) -> list[Worker]:

        return list(
            self._workers.values()
        )

    def list_enabled(
        self,
    ) -> list[Worker]:

        return [
            worker
            for worker
            in self._workers.values()
            if worker.enabled
        ]

    def find_for_task(
        self,
        task: WorkerTask,
    ) -> list[Worker]:

        return [
            worker
            for worker
            in self.list_enabled()
            if worker.can_handle(task)
        ]

    def find_by_capability(
        self,
        capability: str,
    ) -> list[Worker]:

        return [
            worker
            for worker
            in self.list_enabled()
            if capability
            in worker.capabilities
        ]

    def enable(
        self,
        worker_name: str,
    ) -> bool:

        worker = self.get(worker_name)

        if worker is None:
            return False

        worker.enable()

        return True

    def disable(
        self,
        worker_name: str,
    ) -> bool:

        worker = self.get(worker_name)

        if worker is None:
            return False

        worker.disable()

        return True

    def count(self) -> int:
        return len(
            self._workers
        )

    def enabled_count(self) -> int:

        return len(
            self.list_enabled()
        )

    def capability_summary(
        self,
    ) -> dict[str, list[str]]:

        summary: dict[
            str,
            list[str]
        ] = {}

        for worker in self.list_enabled():

            for capability in (
                worker.capabilities
            ):

                summary.setdefault(
                    capability,
                    []
                )

                summary[
                    capability
                ].append(worker.name)

        return summary

    def task_type_summary(
        self,
    ) -> dict[str, list[str]]:

        summary: dict[
            str,
            list[str]
        ] = {}

        for worker in self.list_enabled():

            for task_type in (
                worker.task_types
            ):

                summary.setdefault(
                    task_type.value,
                    []
                )

                summary[
                    task_type.value
                ].append(worker.name)

        return summary


class WorkerPool:
    """
    Manages the active Cauvis worker workforce.

    The pool is intentionally lightweight.

    Workers are objects managed by Cauvis rather than
    separate operating-system processes.
    """

    def __init__(
        self,
        registry: WorkerRegistry,
        max_workers: int | None = None,
    ):
        self.registry = registry

        self.max_workers = max_workers

        self.active = True

        self._submitted = 0
        self._completed = 0
        self._failed = 0

    def add_worker(
        self,
        worker: Worker,
    ) -> bool:

        if (
            self.max_workers is not None
            and self.registry.enabled_count()
            >= self.max_workers
        ):
            return False

        self.registry.register(worker)

        return True

    def remove_worker(
        self,
        worker_name: str,
    ) -> bool:

        if not self.registry.has(
            worker_name
        ):
            return False

        self.registry.unregister(
            worker_name
        )

        return True

    def submit(
        self,
        task: WorkerTask,
    ) -> list[Worker]:

        if not self.active:
            return []

        candidates = (
            self.registry.find_for_task(task)
        )

        if candidates:
            self._submitted += 1

        return candidates

    def record_result(
        self,
        result: WorkerResult,
    ) -> None:

        if result.success:
            self._completed += 1
        else:
            self._failed += 1

    def enable(self) -> None:
        self.active = True

    def disable(self) -> None:
        self.active = False

    def worker_count(self) -> int:
        return self.registry.enabled_count()

    def stats(self) -> dict[str, Any]:

        return {
            "active": self.active,
            "workers": self.worker_count(),
            "submitted": self._submitted,
            "completed": self._completed,
            "failed": self._failed,
            "max_workers": self.max_workers,
        }

    def health(self) -> dict[str, Any]:

        workers = self.registry.list_enabled()

        healthy = 0
        failed = 0
        running = 0

        for worker in workers:

            if worker.status == WorkerStatus.RUNNING:
                running += 1

            elif worker.status == WorkerStatus.FAILED:
                failed += 1

            else:
                healthy += 1

        return {
            "healthy": healthy,
            "failed": failed,
            "running": running,
            "total": len(workers),
        }