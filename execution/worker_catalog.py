from dataclasses import dataclass
from typing import Any, Callable

from execution.workers import (
    Worker,
    WorkerRegistry,
    WorkerTask,
    WorkerTaskType,
)


WorkerHandler = Callable[[WorkerTask], Any]


@dataclass
class WorkerSpec:
    """Definition of a standard Cauvis worker role."""

    name: str
    description: str
    capabilities: set[str]
    task_types: set[WorkerTaskType]
    handler_key: str
    enabled: bool = True


DEFAULT_WORKER_SPECS: tuple[WorkerSpec, ...] = (
    WorkerSpec(
        name="general_worker",
        description=(
            "Handles general conversation and reasoning work."
        ),
        capabilities={
            "chat",
            "reasoning",
        },
        task_types={
            WorkerTaskType.GENERAL,
        },
        handler_key="general",
    ),
    WorkerSpec(
        name="research_worker",
        description=(
            "Handles research and web-dependent work."
        ),
        capabilities={
            "web",
        },
        task_types={
            WorkerTaskType.RESEARCH,
        },
        handler_key="research",
    ),
    WorkerSpec(
        name="code_worker",
        description=(
            "Handles code analysis and implementation work."
        ),
        capabilities={
            "code",
        },
        task_types={
            WorkerTaskType.CODE,
        },
        handler_key="code",
    ),
    WorkerSpec(
        name="tool_worker",
        description=(
            "Handles general tasks requiring tools."
        ),
        capabilities={
            "tools",
        },
        task_types={
            WorkerTaskType.GENERAL,
        },
        handler_key="tools",
    ),
    WorkerSpec(
        name="vision_worker",
        description=(
            "Handles vision-capable general tasks."
        ),
        capabilities={
            "vision",
        },
        task_types={
            WorkerTaskType.GENERAL,
        },
        handler_key="vision",
    ),
    WorkerSpec(
        name="context_worker",
        description=(
            "Handles long-context processing."
        ),
        capabilities={
            "long_context",
        },
        task_types={
            WorkerTaskType.GENERAL,
        },
        handler_key="long_context",
    ),
    WorkerSpec(
        name="file_worker",
        description=(
            "Handles filesystem-oriented work."
        ),
        capabilities={
            "filesystem",
        },
        task_types={
            WorkerTaskType.FILE,
        },
        handler_key="filesystem",
    ),
    WorkerSpec(
        name="system_worker",
        description=(
            "Handles operating-system-oriented work."
        ),
        capabilities={
            "system",
        },
        task_types={
            WorkerTaskType.SYSTEM,
        },
        handler_key="system",
    ),
    WorkerSpec(
        name="verification_worker",
        description=(
            "Handles explicit result verification."
        ),
        capabilities={
            "verification",
        },
        task_types={
            WorkerTaskType.VERIFICATION,
        },
        handler_key="verification",
    ),
)


class WorkerCatalog:
    """
    Standard Cauvis worker catalog.

    The catalog defines worker roles and capabilities.
    Execution handlers must be explicitly bound before
    a worker can be registered for real execution.
    """

    def __init__(
        self,
        handlers: dict[str, WorkerHandler] | None = None,
    ):
        self._specs = {
            spec.name: spec
            for spec in DEFAULT_WORKER_SPECS
        }

        self._handlers: dict[
            str,
            WorkerHandler,
        ] = dict(
            handlers or {}
        )

    def list_specs(
        self,
    ) -> list[WorkerSpec]:
        return list(
            self._specs.values()
        )

    def get_spec(
        self,
        worker_name: str,
    ) -> WorkerSpec | None:
        return self._specs.get(
            worker_name
        )

    def bind_handler(
        self,
        handler_key: str,
        handler: WorkerHandler,
    ) -> None:
        self._handlers[
            handler_key
        ] = handler

    def unbind_handler(
        self,
        handler_key: str,
    ) -> None:
        self._handlers.pop(
            handler_key,
            None,
        )

    def missing_handlers(
        self,
    ) -> list[str]:
        return sorted(
            spec.handler_key
            for spec in self._specs.values()
            if (
                spec.enabled
                and spec.handler_key
                not in self._handlers
            )
        )

    def build_worker(
        self,
        worker_name: str,
    ) -> Worker:
        spec = self.get_spec(
            worker_name
        )

        if spec is None:
            raise KeyError(
                "Unknown worker catalog entry: "
                f"{worker_name}"
            )

        handler = self._handlers.get(
            spec.handler_key
        )

        if handler is None:
            raise ValueError(
                f"Worker '{worker_name}' "
                "requires handler "
                f"'{spec.handler_key}'."
            )

        return Worker(
            name=spec.name,
            description=spec.description,
            capabilities=set(
                spec.capabilities
            ),
            task_types=set(
                spec.task_types
            ),
            handler=handler,
            enabled=spec.enabled,
            metadata={
                "catalog_worker": True,
                "handler_key": (
                    spec.handler_key
                ),
            },
        )

    def build_registry(
        self,
        strict: bool = True,
    ) -> WorkerRegistry:
        missing = self.missing_handlers()

        if strict and missing:
            raise ValueError(
                "Missing worker handlers: "
                + ", ".join(missing)
            )

        registry = WorkerRegistry()

        for spec in self._specs.values():
            if not spec.enabled:
                continue

            if (
                spec.handler_key
                not in self._handlers
            ):
                continue

            registry.register(
                self.build_worker(
                    spec.name
                )
            )

        return registry

    def summary(
        self,
    ) -> dict[str, dict[str, Any]]:
        return {
            spec.name: {
                "handler_key": (
                    spec.handler_key
                ),
                "handler_bound": (
                    spec.handler_key
                    in self._handlers
                ),
                "capabilities": sorted(
                    spec.capabilities
                ),
                "task_types": sorted(
                    task_type.value
                    for task_type
                    in spec.task_types
                ),
                "enabled": spec.enabled,
            }
            for spec in self._specs.values()
        }


def build_default_worker_catalog(
    handlers: (
        dict[str, WorkerHandler]
        | None
    ) = None,
) -> WorkerCatalog:
    return WorkerCatalog(
        handlers=handlers
    )


def build_default_worker_registry(
    handlers: dict[
        str,
        WorkerHandler,
    ],
    strict: bool = True,
) -> WorkerRegistry:
    catalog = (
        build_default_worker_catalog(
            handlers
        )
    )

    return catalog.build_registry(
        strict=strict
    )