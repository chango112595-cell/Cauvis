from dataclasses import dataclass, field
from typing import Any


@dataclass
class Capability:
    """
    Describes something Cauvis can potentially do.
    """

    name: str
    description: str
    category: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityRegistry:
    """
    Central registry for Cauvis capabilities.

    The registry does not execute capabilities.
    It only defines and discovers what Cauvis can do.
    """

    def __init__(self):
        self._capabilities: dict[str, Capability] = {}

    # REGISTRATION

    def register(self, capability: Capability) -> None:
        """
        Register a capability with Cauvis.
        """

        if not capability.name.strip():
            raise ValueError(
                "Capability name cannot be empty."
            )

        self._capabilities[capability.name] = capability

    def unregister(self, name: str) -> None:
        """
        Remove a capability from the registry.
        """

        self._capabilities.pop(name, None)

    # DISCOVERY

    def get(self, name: str) -> Capability | None:
        """
        Return a capability by name.
        """

        return self._capabilities.get(name)

    def has(self, name: str) -> bool:
        """
        Determine whether a capability exists and is enabled.
        """

        capability = self.get(name)

        return (
            capability is not None
            and capability.enabled
        )

    def list_all(self) -> list[Capability]:
        """
        Return all registered capabilities.
        """

        return list(self._capabilities.values())

    def list_enabled(self) -> list[Capability]:
        """
        Return only enabled capabilities.
        """

        return [
            capability
            for capability in self._capabilities.values()
            if capability.enabled
        ]

    def list_by_category(
        self,
        category: str,
    ) -> list[Capability]:
        """
        Return capabilities belonging to a category.
        """

        return [
            capability
            for capability in self._capabilities.values()
            if capability.category == category
            and capability.enabled
        ]

    # STATE

    def enable(self, name: str) -> bool:
        """
        Enable an existing capability.
        """

        capability = self.get(name)

        if capability is None:
            return False

        capability.enabled = True
        return True

    def disable(self, name: str) -> bool:
        """
        Disable an existing capability.
        """

        capability = self.get(name)

        if capability is None:
            return False

        capability.enabled = False
        return True

    # REQUIREMENT MATCHING

    def missing(
        self,
        required_capabilities: set[str],
    ) -> set[str]:
        """
        Return required capabilities that Cauvis
        does not currently have enabled.
        """

        return {
            capability
            for capability in required_capabilities
            if not self.has(capability)
        }

    def can_support(
        self,
        required_capabilities: set[str],
    ) -> bool:
        """
        Determine whether all required capabilities
        are currently available.
        """

        return not self.missing(
            required_capabilities
        )

    # INFORMATION

    def count(self) -> int:
        """
        Return the total number of registered capabilities.
        """

        return len(self._capabilities)

    def enabled_count(self) -> int:
        """
        Return the number of enabled capabilities.
        """

        return len(self.list_enabled())