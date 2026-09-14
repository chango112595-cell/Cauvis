import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ProviderConfigStatus(str, Enum):
    """
    Configuration readiness of an AI provider.

    This is separate from runtime health.
    """

    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ProviderConfiguration:
    """
    Read-only provider configuration snapshot.

    Credential values are never stored or exposed here.
    """

    provider_name: str
    status: ProviderConfigStatus
    enabled: bool
    configured: bool
    credential_env_var: str | None
    credential_present: bool
    reason: str
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "status": self.status.value,
            "enabled": self.enabled,
            "configured": self.configured,
            "credential_env_var": (
                self.credential_env_var
            ),
            "credential_present": (
                self.credential_present
            ),
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


class ProviderConfigGate:
    """
    Determines whether a provider is configured for use.

    This class does not perform network calls and does not
    claim that a configured provider is available.

    REGISTERED != CONFIGURED != AVAILABLE
    """

    def __init__(
        self,
        environment: Mapping[str, str] | None = None,
    ):
        self._environment = (
            environment
            if environment is not None
            else os.environ
        )

    def inspect(
        self,
        provider_name: str,
        credential_env_var: str | None = None,
        enabled: bool = True,
        credential_required: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderConfiguration:
        """
        Inspect configuration readiness without exposing secrets.
        """

        if not enabled:
            return ProviderConfiguration(
                provider_name=provider_name,
                status=ProviderConfigStatus.DISABLED,
                enabled=False,
                configured=False,
                credential_env_var=credential_env_var,
                credential_present=False,
                reason=(
                    "Provider is disabled by configuration."
                ),
                metadata=dict(metadata or {}),
            )

        credential_present = False

        if credential_env_var:
            value = self._environment.get(
                credential_env_var,
                ""
            )

            credential_present = bool(
                str(value).strip()
            )

        if credential_required:
            if not credential_env_var:
                return ProviderConfiguration(
                    provider_name=provider_name,
                    status=(
                        ProviderConfigStatus.NOT_CONFIGURED
                    ),
                    enabled=True,
                    configured=False,
                    credential_env_var=None,
                    credential_present=False,
                    reason=(
                        "Provider requires a credential, but no "
                        "credential environment variable was defined."
                    ),
                    metadata=dict(metadata or {}),
                )

            if not credential_present:
                return ProviderConfiguration(
                    provider_name=provider_name,
                    status=(
                        ProviderConfigStatus.NOT_CONFIGURED
                    ),
                    enabled=True,
                    configured=False,
                    credential_env_var=(
                        credential_env_var
                    ),
                    credential_present=False,
                    reason=(
                        "Required provider credential is not present "
                        "in the environment."
                    ),
                    metadata=dict(metadata or {}),
                )

        return ProviderConfiguration(
            provider_name=provider_name,
            status=ProviderConfigStatus.CONFIGURED,
            enabled=True,
            configured=True,
            credential_env_var=credential_env_var,
            credential_present=credential_present,
            reason=(
                "Provider configuration requirements are satisfied."
            ),
            metadata=dict(metadata or {}),
        )