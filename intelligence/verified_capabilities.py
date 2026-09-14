from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from intelligence.router import AIModelRouter


class CapabilityTruthStatus(str, Enum):
    """
    Evidence level for a Cauvis runtime capability.

    AVAILABLE:
        Cauvis can directly prove the capability is active in
        the current runtime.

    REGISTERED:
        A supporting component is registered, but live
        availability has not been proven.

    CONFIGURED:
        A supporting component is configured, but live
        availability has not been proven.

    DEGRADED:
        A supporting runtime has recorded real failures but
        remains eligible for use.

    UNAVAILABLE:
        A supporting runtime has been observed unavailable.

    DISABLED:
        The capability/provider is explicitly disabled.

    NOT_CONFIGURED:
        A required supporting component is present but its
        configuration requirements are not satisfied.

    NOT_CONNECTED:
        The implementation may exist elsewhere in Cauvis, but
        it is not attached to this running Cauvis instance.

    NOT_VERIFIED:
        Cauvis does not currently have enough runtime evidence
        to truthfully claim the capability is available.
    """

    AVAILABLE = "available"
    REGISTERED = "registered"
    CONFIGURED = "configured"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"
    NOT_CONNECTED = "not_connected"
    NOT_VERIFIED = "not_verified"


@dataclass(frozen=True)
class VerifiedCapability:
    """
    Read-only truth record for one Cauvis capability.

    This describes what the running Cauvis instance can prove.
    It is intentionally separate from CapabilitySet, which
    describes what a user request requires.
    """

    name: str
    status: CapabilityTruthStatus
    available: bool
    description: str
    evidence: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "available": self.available,
            "description": self.description,
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class VerifiedCapabilitySnapshot:
    """
    Read-only snapshot of runtime capability truth.

    It must never upgrade repository definitions, planned
    features, or unbound components into available abilities.
    """

    capabilities: tuple[VerifiedCapability, ...]
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def get(
        self,
        name: str,
    ) -> VerifiedCapability | None:
        for capability in self.capabilities:
            if capability.name == name:
                return capability

        return None

    def list_available(
        self,
    ) -> tuple[VerifiedCapability, ...]:
        return tuple(
            capability
            for capability in self.capabilities
            if capability.available
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capabilities": [
                capability.to_dict()
                for capability in self.capabilities
            ],
            "metadata": dict(self.metadata),
        }


class VerifiedCapabilityBuilder:
    """
    Build an observational capability-truth snapshot.

    Stage Beta 1.2B deliberately fails closed.

    Repository definitions are not treated as proof that a
    feature is available. Execution, tools, workers, web,
    filesystem, system control, and voice remain NOT_CONNECTED
    until real runtime objects are explicitly supplied.
    """

    def build(
        self,
        *,
        router: AIModelRouter | None,
        conversation_connected: bool,
        brain_connected: bool,
        execution_engine: Any | None = None,
        tool_registry: Any | None = None,
        worker_registry: Any | None = None,
        voice_runtime: Any | None = None,
    ) -> VerifiedCapabilitySnapshot:
        capabilities: list[VerifiedCapability] = []

        capabilities.append(
            self._binary_runtime_capability(
                name="conversation",
                connected=conversation_connected,
                description=(
                    "Bounded conversation continuity within "
                    "the current running Cauvis session. "
                    "This is not persistent long-term memory."
                ),
                connected_evidence=(
                    "ConversationRuntime is attached "
                    "to the running orchestrator.",
                    "Conversation history is in-memory and "
                    "session-scoped only.",
                ),
            )
        )

        capabilities.append(
            VerifiedCapability(
                name="persistent_memory",
                status=(
                    CapabilityTruthStatus.NOT_CONNECTED
                ),
                available=False,
                description=(
                    "Persistent long-term memory across "
                    "Cauvis restarts or future sessions."
                ),
                evidence=(
                    "No persistent memory runtime is attached.",
                    "Current ConversationRuntime is session-only.",
                ),
            )
        )

        capabilities.append(
            self._binary_runtime_capability(
                name="brain",
                connected=brain_connected,
                description=(
                    "Cauvis request analysis, reasoning, "
                    "planning, and AI coordination."
                ),
                connected_evidence=(
                    "CauvisBrain is attached to the "
                    "running orchestrator.",
                ),
            )
        )

        capabilities.append(
            self._binary_runtime_capability(
                name="ai_routing",
                connected=router is not None,
                description=(
                    "AI model provider registration, "
                    "selection, and failover routing."
                ),
                connected_evidence=(
                    "AIModelRouter is attached to the "
                    "running orchestrator.",
                ),
            )
        )

        if router is not None:
            capabilities.extend(
                self._provider_capabilities(
                    router
                )
            )

        capabilities.append(
            self._binary_runtime_capability(
                name="execution_actions",
                connected=execution_engine is not None,
                description=(
                    "ExecutionEngine-backed external actions."
                ),
                connected_evidence=(
                    "ExecutionEngine is attached to the "
                    "running runtime.",
                ),
            )
        )

        capabilities.append(
            self._binary_runtime_capability(
                name="tool_execution",
                connected=tool_registry is not None,
                description=(
                    "Registered executable tool operations."
                ),
                connected_evidence=(
                    "ToolRegistry is attached to the "
                    "running runtime.",
                ),
            )
        )

        capabilities.append(
            self._binary_runtime_capability(
                name="worker_execution",
                connected=worker_registry is not None,
                description=(
                    "Bound Cauvis worker execution."
                ),
                connected_evidence=(
                    "WorkerRegistry is attached to the "
                    "running runtime.",
                ),
            )
        )

        capabilities.append(
            self._binary_runtime_capability(
                name="voice",
                connected=voice_runtime is not None,
                description=(
                    "Microphone, speech recognition, "
                    "and speech output runtime."
                ),
                connected_evidence=(
                    "Voice runtime is attached to the "
                    "running runtime.",
                ),
            )
        )

        # These action classes require real execution/tool/worker
        # evidence. In Beta 1.2B they fail closed rather than
        # assuming availability from repository definitions.
        action_runtime_connected = bool(
            execution_engine is not None
            and tool_registry is not None
        )

        for name, description in (
            (
                "filesystem_actions",
                "Filesystem-changing actions.",
            ),
            (
                "system_actions",
                "Operating-system or application actions.",
            ),
            (
                "web_actions",
                "Live web/browser actions.",
            ),
            (
                "reminders",
                "Scheduled reminder actions.",
            ),
        ):
            if action_runtime_connected:
                capabilities.append(
                    VerifiedCapability(
                        name=name,
                        status=(
                            CapabilityTruthStatus.NOT_VERIFIED
                        ),
                        available=False,
                        description=description,
                        evidence=(
                            "Execution and tool runtimes are "
                            "connected, but this specific "
                            "capability has not yet been "
                            "verified from bound executable "
                            "handlers.",
                        ),
                    )
                )

            else:
                capabilities.append(
                    VerifiedCapability(
                        name=name,
                        status=(
                            CapabilityTruthStatus.NOT_CONNECTED
                        ),
                        available=False,
                        description=description,
                        evidence=(
                            "No verified execution/tool path is "
                            "attached for this action class.",
                        ),
                    )
                )

        return VerifiedCapabilitySnapshot(
            capabilities=tuple(capabilities),
            metadata={
                "schema_version": 1,
                "observational_only": True,
                "fails_closed": True,
                "request_requirements_are_not_runtime_truth": (
                    True
                ),
            },
        )

    @staticmethod
    def _binary_runtime_capability(
        *,
        name: str,
        connected: bool,
        description: str,
        connected_evidence: tuple[str, ...],
    ) -> VerifiedCapability:
        if connected:
            return VerifiedCapability(
                name=name,
                status=CapabilityTruthStatus.AVAILABLE,
                available=True,
                description=description,
                evidence=connected_evidence,
            )

        return VerifiedCapability(
            name=name,
            status=CapabilityTruthStatus.NOT_CONNECTED,
            available=False,
            description=description,
            evidence=(
                "Required runtime object is not attached.",
            ),
        )

    @staticmethod
    def _provider_capabilities(
        router: AIModelRouter,
    ) -> list[VerifiedCapability]:
        results: list[VerifiedCapability] = []

        for provider_name in router.list_providers():
            provider = router.get_provider(
                provider_name
            )

            configuration = (
                router.get_provider_configuration(
                    provider_name
                )
            )

            health = (
                router.provider_runtime.get_health(
                    provider_name
                )
            )

            status = (
                VerifiedCapabilityBuilder
                ._provider_truth_status(
                    configuration=configuration,
                    health=health,
                )
            )

            available = bool(
                status
                == CapabilityTruthStatus.AVAILABLE
            )

            evidence = [
                (
                    f"Provider '{provider_name}' is "
                    "registered with AIModelRouter."
                )
            ]

            if configuration is not None:
                evidence.append(
                    "Configuration status: "
                    f"{configuration.status.value}."
                )

            if health is not None:
                evidence.append(
                    "Observed runtime status: "
                    f"{health.status.value}."
                )

            results.append(
                VerifiedCapability(
                    name=(
                        f"provider:{provider_name}"
                    ),
                    status=status,
                    available=available,
                    description=(
                        "AI model provider"
                    ),
                    evidence=tuple(evidence),
                    metadata={
                        "provider": provider_name,
                        "model": str(
                            getattr(
                                provider,
                                "model",
                                "unknown",
                            )
                        )
                        if provider is not None
                        else "unknown",
                        "configured": (
                            bool(
                                configuration.configured
                            )
                            if configuration is not None
                            else False
                        ),
                        "runtime_available": available,
                    },
                )
            )

        return results

    @staticmethod
    def _provider_truth_status(
        *,
        configuration: Any | None,
        health: Any | None,
    ) -> CapabilityTruthStatus:
        if configuration is not None:
            config_status = (
                configuration.status.value
            )

            if config_status == "disabled":
                return (
                    CapabilityTruthStatus.DISABLED
                )

            if config_status == "not_configured":
                return (
                    CapabilityTruthStatus.NOT_CONFIGURED
                )

        if health is not None:
            runtime_status = health.status.value

            if runtime_status == "available":
                return (
                    CapabilityTruthStatus.AVAILABLE
                )

            if runtime_status == "degraded":
                return (
                    CapabilityTruthStatus.DEGRADED
                )

            if runtime_status == "unavailable":
                return (
                    CapabilityTruthStatus.UNAVAILABLE
                )

            if runtime_status == "disabled":
                return (
                    CapabilityTruthStatus.DISABLED
                )

        if (
            configuration is not None
            and configuration.configured
        ):
            return (
                CapabilityTruthStatus.CONFIGURED
            )

        return CapabilityTruthStatus.REGISTERED
