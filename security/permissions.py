from dataclasses import dataclass
from enum import Enum


class PermissionLevel(str, Enum):
    """
    Defines how much authorization an action requires.
    """

    SAFE = "safe"
    APPROVAL_REQUIRED = "approval_required"
    HIGH_RISK = "high_risk"
    DENIED = "denied"


@dataclass
class PermissionDecision:
    """
    Result of a permission evaluation.
    """

    allowed: bool
    requires_approval: bool
    level: PermissionLevel
    reason: str


class PermissionManager:
    """
    Controls whether Cauvis is permitted to perform an action.

    This is intentionally separate from the AI brain.
    The AI can request an action, but it does not grant
    itself permission to perform that action.
    """

    def __init__(self):
        self._permissions: dict[
            str, PermissionLevel
        ] = {}

        self._register_default_permissions()

    def _register_default_permissions(self) -> None:
        """
        Register Cauvis's initial permission policy.
        """

        safe_actions = {
            "system.info",
            "system.status",
            "web.search",
            "web.read",
            "vision.analyze",
        }

        approval_actions = {
            "application.launch",
            "filesystem.write",
            "filesystem.copy",
            "filesystem.move",
            "filesystem.download",
            "message.send",
        }

        high_risk_actions = {
            "terminal.execute",
            "filesystem.delete",
            "system.settings",
            "software.install",
            "system.shutdown",
            "system.restart",
        }

        for action in safe_actions:
            self.register(
                action,
                PermissionLevel.SAFE,
            )

        for action in approval_actions:
            self.register(
                action,
                PermissionLevel.APPROVAL_REQUIRED,
            )

        for action in high_risk_actions:
            self.register(
                action,
                PermissionLevel.HIGH_RISK,
            )

    # REGISTRATION

    def register(
        self,
        action: str,
        level: PermissionLevel,
    ) -> None:
        """
        Register or update an action's permission level.
        """

        if not action.strip():
            raise ValueError(
                "Permission action cannot be empty."
            )

        self._permissions[action] = level

    # DISCOVERY

    def get_level(
        self,
        action: str,
    ) -> PermissionLevel:
        """
        Return the permission level for an action.

        Unknown actions are denied by default.
        """

        return self._permissions.get(
            action,
            PermissionLevel.DENIED,
        )

    def is_registered(
        self,
        action: str,
    ) -> bool:
        """
        Determine whether an action has an explicit
        permission policy.
        """

        return action in self._permissions

    # EVALUATION

    def evaluate(
        self,
        action: str,
    ) -> PermissionDecision:
        """
        Evaluate whether Cauvis may perform an action.
        """

        level = self.get_level(action)

        if level == PermissionLevel.SAFE:
            return PermissionDecision(
                allowed=True,
                requires_approval=False,
                level=level,
                reason=(
                    "This action is classified as safe."
                ),
            )

        if level == PermissionLevel.APPROVAL_REQUIRED:
            return PermissionDecision(
                allowed=False,
                requires_approval=True,
                level=level,
                reason=(
                    "This action requires user approval "
                    "before execution."
                ),
            )

        if level == PermissionLevel.HIGH_RISK:
            return PermissionDecision(
                allowed=False,
                requires_approval=True,
                level=level,
                reason=(
                    "This action is high risk and cannot "
                    "execute automatically."
                ),
            )

        return PermissionDecision(
            allowed=False,
            requires_approval=False,
            level=PermissionLevel.DENIED,
            reason=(
                "This action has no permission policy "
                "and is denied by default."
            ),
        )

    # INFORMATION

    def list_permissions(
        self,
    ) -> dict[str, PermissionLevel]:
        """
        Return a copy of the current permission policy.
        """

        return dict(self._permissions)

    def count(self) -> int:
        """
        Return the number of explicitly registered actions.
        """

        return len(self._permissions)