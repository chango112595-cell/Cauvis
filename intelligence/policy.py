from dataclasses import dataclass
from enum import Enum

from intelligence.device import DeviceProfile
from intelligence.task import TaskRequirements, TaskComplexity


class ExecutionStrategy(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


@dataclass
class IntelligencePolicy:
    strategy: ExecutionStrategy
    local_allowed: bool
    cloud_allowed: bool
    reason: str


class AdaptivePolicyEngine:
    """Chooses an AI execution strategy using device and task requirements."""

    def evaluate(
        self,
        profile: DeviceProfile,
        task: TaskRequirements,
    ) -> IntelligencePolicy:

        # ---------------------------------------------------------
        # DEVICE CAPABILITY
        # ---------------------------------------------------------

        has_gpu = bool(profile.gpu_names)
        has_dedicated_gpu = has_gpu and not profile.gpu_integrated

        # Lightweight local AI should be possible on ordinary
        # computers with enough system memory.
        local_allowed = profile.memory_gb >= 8

        # Cloud capability is assumed available at the policy level.
        # Actual network/provider availability will be handled later.
        cloud_allowed = True

        # ---------------------------------------------------------
        # TASK REQUIREMENTS
        # ---------------------------------------------------------

        # Tasks requiring the internet cannot be completed entirely
        # locally unless Cauvis has another internet-capable tool.
        if task.requires_internet:
            if task.privacy_sensitive:
                return IntelligencePolicy(
                    strategy=ExecutionStrategy.HYBRID,
                    local_allowed=local_allowed,
                    cloud_allowed=cloud_allowed,
                    reason=(
                        "The task requires internet access but also involves "
                        "privacy-sensitive information. Keep private processing "
                        "local where possible and use cloud services only when needed."
                    ),
                )

            return IntelligencePolicy(
                strategy=ExecutionStrategy.HYBRID,
                local_allowed=local_allowed,
                cloud_allowed=cloud_allowed,
                reason=(
                    "The task requires internet access. Local AI can handle "
                    "appropriate processing while online tools or cloud AI "
                    "handle internet-dependent work."
                ),
            )

        # Privacy-sensitive tasks should prefer local processing.
        if task.privacy_sensitive:
            if local_allowed:
                return IntelligencePolicy(
                    strategy=ExecutionStrategy.LOCAL,
                    local_allowed=True,
                    cloud_allowed=cloud_allowed,
                    reason=(
                        "The task contains privacy-sensitive information and "
                        "this device can support local AI."
                    ),
                )

            return IntelligencePolicy(
                strategy=ExecutionStrategy.CLOUD,
                local_allowed=False,
                cloud_allowed=cloud_allowed,
                reason=(
                    "The task is privacy-sensitive, but this device does not "
                    "currently have enough resources for local AI."
                ),
            )

        # Vision workloads may require specialized models.
        if task.requires_vision:
            if has_dedicated_gpu:
                return IntelligencePolicy(
                    strategy=ExecutionStrategy.HYBRID,
                    local_allowed=local_allowed,
                    cloud_allowed=cloud_allowed,
                    reason=(
                        "The task requires vision processing and the device "
                        "has a dedicated GPU. Local and cloud vision models "
                        "can be combined."
                    ),
                )

            return IntelligencePolicy(
                strategy=ExecutionStrategy.HYBRID,
                local_allowed=local_allowed,
                cloud_allowed=cloud_allowed,
                reason=(
                    "The task requires vision processing. A hybrid strategy "
                    "allows Cauvis to use local resources while using a "
                    "specialized vision model when necessary."
                ),
            )

        # ---------------------------------------------------------
        # COMPLEXITY
        # ---------------------------------------------------------

        if task.complexity == TaskComplexity.HIGH:
            if has_dedicated_gpu and profile.memory_gb >= 16:
                return IntelligencePolicy(
                    strategy=ExecutionStrategy.HYBRID,
                    local_allowed=local_allowed,
                    cloud_allowed=cloud_allowed,
                    reason=(
                        "The task is highly complex and the device has "
                        "strong local hardware. Use local and cloud AI "
                        "according to workload."
                    ),
                )

            return IntelligencePolicy(
                strategy=ExecutionStrategy.CLOUD,
                local_allowed=local_allowed,
                cloud_allowed=cloud_allowed,
                reason=(
                    "The task is highly complex. Cloud AI is preferred for "
                    "heavy reasoning while local resources remain available "
                    "for supporting work."
                ),
            )

        if task.complexity == TaskComplexity.MEDIUM:
            if local_allowed:
                return IntelligencePolicy(
                    strategy=ExecutionStrategy.HYBRID,
                    local_allowed=True,
                    cloud_allowed=cloud_allowed,
                    reason=(
                        "The task has moderate complexity and this device "
                        "can support local AI. Use local processing first "
                        "with cloud assistance when beneficial."
                    ),
                )

            return IntelligencePolicy(
                strategy=ExecutionStrategy.CLOUD,
                local_allowed=False,
                cloud_allowed=cloud_allowed,
                reason=(
                    "The task has moderate complexity but local hardware "
                    "is limited. Prefer cloud execution."
                ),
            )

        # ---------------------------------------------------------
        # SIMPLE TASKS
        # ---------------------------------------------------------

        if local_allowed:
            return IntelligencePolicy(
                strategy=ExecutionStrategy.LOCAL,
                local_allowed=True,
                cloud_allowed=cloud_allowed,
                reason=(
                    "The task is simple enough for local processing and "
                    "the device has sufficient resources."
                ),
            )

        return IntelligencePolicy(
            strategy=ExecutionStrategy.CLOUD,
            local_allowed=False,
            cloud_allowed=cloud_allowed,
            reason=(
                "The task is simple, but the device has limited resources "
                "for local AI."
            ),
        )