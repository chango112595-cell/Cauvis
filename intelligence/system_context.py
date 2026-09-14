from dataclasses import asdict, dataclass
from typing import Any

from intelligence.device import DeviceProfile
from intelligence.router import AIModelRouter, ModelProvider


@dataclass(frozen=True)
class ProviderContext:
    """
    Read-only description of a registered AI provider.

    This describes what Cauvis can prove from provider registration.
    It does not claim provider health or live availability.
    """

    name: str
    model: str
    capabilities: tuple[str, ...]
    provider_types: tuple[str, ...]
    is_default: bool
    capable_for_request: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "capabilities": list(self.capabilities),
            "provider_types": list(self.provider_types),
            "is_default": self.is_default,
            "capable_for_request": self.capable_for_request,
        }


@dataclass(frozen=True)
class SystemContextSnapshot:
    """
    Read-only snapshot of Cauvis runtime knowledge.

    Stage 1 contains only information Cauvis can currently prove:
    required capabilities, registered providers, provider declarations,
    default provider, capability matches, and device information.

    Health, permissions, workers, tools, and recovery state will be
    added only when those systems are explicitly connected.
    """

    required_capabilities: tuple[str, ...]
    registered_providers: tuple[str, ...]
    capable_providers: tuple[str, ...]
    default_provider: str | None
    providers: tuple[ProviderContext, ...]
    device: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_capabilities": list(
                self.required_capabilities
            ),
            "registered_providers": list(
                self.registered_providers
            ),
            "capable_providers": list(
                self.capable_providers
            ),
            "default_provider": self.default_provider,
            "providers": [
                provider.to_dict()
                for provider in self.providers
            ],
            "device": dict(self.device),
            "metadata": dict(self.metadata),
        }


class SystemContextBuilder:
    """
    Builds Nexus-inspired runtime awareness for CauvisBrain.

    The builder is observational only. It does not alter routing,
    policy, provider state, permissions, or execution.
    """

    def __init__(self, router: AIModelRouter):
        self.router = router

    def build(
        self,
        required_capabilities: set[str],
        device: DeviceProfile,
    ) -> SystemContextSnapshot:

        required = set(required_capabilities)
        provider_contexts: list[ProviderContext] = []
        capable_providers: list[str] = []

        for provider_name in self.router.list_providers():
            provider = self.router.get_provider(
                provider_name
            )

            if provider is None:
                continue

            capabilities = set(
                getattr(
                    provider,
                    "capabilities",
                    set(),
                )
                or set()
            )

            provider_types = self._get_provider_types(
                provider
            )

            capable = required.issubset(
                capabilities
            )

            if capable:
                capable_providers.append(
                    provider_name
                )

            provider_contexts.append(
                ProviderContext(
                    name=provider_name,
                    model=str(
                        getattr(
                            provider,
                            "model",
                            "unknown",
                        )
                    ),
                    capabilities=tuple(
                        sorted(capabilities)
                    ),
                    provider_types=tuple(
                        sorted(provider_types)
                    ),
                    is_default=(
                        provider_name
                        == self.router.default_provider
                    ),
                    capable_for_request=capable,
                )
            )

        registered_providers = tuple(
            provider.name
            for provider in provider_contexts
        )

        return SystemContextSnapshot(
            required_capabilities=tuple(
                sorted(required)
            ),
            registered_providers=(
                registered_providers
            ),
            capable_providers=tuple(
                capable_providers
            ),
            default_provider=(
                self.router.default_provider
            ),
            providers=tuple(provider_contexts),
            device=asdict(device),
            metadata={
                "schema_version": 1,
                "provider_count": len(
                    provider_contexts
                ),
                "observational_only": True,
                "provider_health_included": False,
                "worker_health_included": False,
                "tool_health_included": False,
                "permission_state_included": False,
                "recovery_state_included": False,
            },
        )

    @staticmethod
    def _get_provider_types(
        provider: ModelProvider,
    ) -> set[str]:
        """
        Normalize both current and legacy provider type declarations.

        Cauvis router supports provider_types, while some existing test
        providers expose the older singular provider_type property.
        """

        provider_types = getattr(
            provider,
            "provider_types",
            None,
        )

        if provider_types:
            if isinstance(provider_types, str):
                return {provider_types}

            return {
                str(provider_type)
                for provider_type in provider_types
            }

        provider_type = getattr(
            provider,
            "provider_type",
            None,
        )

        if provider_type:
            return {str(provider_type)}

        return set()