from dataclasses import dataclass, field

from intelligence.task import TaskRequirements


@dataclass
class CapabilitySet:
    """
    Standardized capabilities required to execute a task.
    """

    capabilities: set[str] = field(default_factory=set)

    def has(self, capability: str) -> bool:
        return capability in self.capabilities

    def add(self, capability: str) -> None:
        self.capabilities.add(capability)

    def remove(self, capability: str) -> None:
        self.capabilities.discard(capability)


class CapabilityMapper:
    """
    Converts TaskRequirements into standardized AI capabilities.
    """

    def map(self, task: TaskRequirements) -> CapabilitySet:

        capabilities = CapabilitySet()

        # Every AI request requires basic conversational capability.
        capabilities.add("chat")

        # ---------------------------------------------------------
        # TASK CAPABILITIES
        # ---------------------------------------------------------

        if task.requires_code:
            capabilities.add("code")

        if task.requires_vision:
            capabilities.add("vision")

        if task.requires_internet:
            capabilities.add("web")

        if task.requires_tools:
            capabilities.add("tools")

        if task.requires_long_context:
            capabilities.add("long_context")

        if task.privacy_sensitive:
            capabilities.add("privacy")

        # ---------------------------------------------------------
        # COMPLEXITY
        # ---------------------------------------------------------

        complexity = task.complexity.value

        capabilities.add(
            f"complexity:{complexity}"
        )

        # High-complexity tasks benefit from stronger reasoning.
        if complexity == "high":
            capabilities.add("reasoning")

        elif complexity == "medium":
            capabilities.add("reasoning")

        return capabilities