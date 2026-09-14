from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderStatus(str, Enum):
    """
    Verified runtime state of an AI provider.

    UNKNOWN means Cauvis has not observed enough real runtime
    information to claim the provider is available.
    """

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ProviderHealth:
    """
    Read-only snapshot of one provider's observed runtime state.
    """

    provider_name: str
    status: ProviderStatus
    available: bool
    latency_ms: float | None = None
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "status": self.status.value,
            "available": self.available,
            "latency_ms": self.latency_ms,
            "consecutive_failures": (
                self.consecutive_failures
            ),
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "last_error": self.last_error,
            "metadata": dict(self.metadata),
        }


@dataclass
class _ProviderRuntimeRecord:
    """
    Internal mutable runtime record.

    External callers receive immutable ProviderHealth snapshots.
    """

    provider_name: str
    status: ProviderStatus = ProviderStatus.UNKNOWN
    latency_ms: float | None = None
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderRuntime:
    """
    Tracks verified runtime outcomes for AI providers.

    This class does not perform network requests and does not guess
    provider health. State changes only when Cauvis records an actual
    outcome or explicitly disables/enables a provider.
    """

    def __init__(
        self,
        degraded_after_failures: int = 1,
        unavailable_after_failures: int = 3,
    ):
        if degraded_after_failures < 1:
            raise ValueError(
                "degraded_after_failures must be at least 1."
            )

        if unavailable_after_failures < degraded_after_failures:
            raise ValueError(
                "unavailable_after_failures must be greater than "
                "or equal to degraded_after_failures."
            )

        self.degraded_after_failures = (
            degraded_after_failures
        )

        self.unavailable_after_failures = (
            unavailable_after_failures
        )

        self._records: dict[
            str,
            _ProviderRuntimeRecord,
        ] = {}

    def register(
        self,
        provider_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderHealth:
        """
        Register a provider without claiming that it is available.
        """

        record = self._records.get(
            provider_name
        )

        if record is None:
            record = _ProviderRuntimeRecord(
                provider_name=provider_name,
            )

            self._records[
                provider_name
            ] = record

        if metadata:
            record.metadata.update(
                metadata
            )

        return self._snapshot(record)

    def remove(
        self,
        provider_name: str,
    ) -> bool:
        """
        Remove runtime state for a provider.
        """

        return (
            self._records.pop(
                provider_name,
                None,
            )
            is not None
        )

    def record_success(
        self,
        provider_name: str,
        latency_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderHealth:
        """
        Record a verified successful provider operation.
        """

        record = self._ensure_record(
            provider_name
        )

        record.status = (
            ProviderStatus.AVAILABLE
        )

        record.consecutive_failures = 0
        record.total_successes += 1
        record.last_error = None

        if latency_ms is not None:
            record.latency_ms = max(
                0.0,
                float(latency_ms),
            )

        if metadata:
            record.metadata.update(
                metadata
            )

        return self._snapshot(record)

    def record_failure(
        self,
        provider_name: str,
        error: str,
        latency_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderHealth:
        """
        Record a verified failed provider operation.

        One or more failures move the provider to DEGRADED.
        Reaching the configured failure threshold moves it to
        UNAVAILABLE.
        """

        record = self._ensure_record(
            provider_name
        )

        record.consecutive_failures += 1
        record.total_failures += 1
        record.last_error = str(error)

        if latency_ms is not None:
            record.latency_ms = max(
                0.0,
                float(latency_ms),
            )

        if metadata:
            record.metadata.update(
                metadata
            )

        if (
            record.consecutive_failures
            >= self.unavailable_after_failures
        ):
            record.status = (
                ProviderStatus.UNAVAILABLE
            )

        elif (
            record.consecutive_failures
            >= self.degraded_after_failures
        ):
            record.status = (
                ProviderStatus.DEGRADED
            )

        return self._snapshot(record)

    def disable(
        self,
        provider_name: str,
        reason: str | None = None,
    ) -> ProviderHealth:
        """
        Explicitly disable a provider.
        """

        record = self._ensure_record(
            provider_name
        )

        record.status = (
            ProviderStatus.DISABLED
        )

        if reason:
            record.last_error = reason

        return self._snapshot(record)

    def enable(
        self,
        provider_name: str,
    ) -> ProviderHealth:
        """
        Re-enable a provider without claiming live availability.

        The provider returns to UNKNOWN until a real operation
        succeeds or fails.
        """

        record = self._ensure_record(
            provider_name
        )

        record.status = (
            ProviderStatus.UNKNOWN
        )

        record.consecutive_failures = 0
        record.last_error = None

        return self._snapshot(record)

    def get_health(
        self,
        provider_name: str,
    ) -> ProviderHealth | None:
        """
        Return an immutable health snapshot for one provider.
        """

        record = self._records.get(
            provider_name
        )

        if record is None:
            return None

        return self._snapshot(record)

    def list_health(
        self,
    ) -> tuple[ProviderHealth, ...]:
        """
        Return immutable snapshots for all tracked providers.
        """

        return tuple(
            self._snapshot(record)
            for record in self._records.values()
        )

    def is_available(
        self,
        provider_name: str,
    ) -> bool:
        """
        True only after a verified successful runtime operation.
        """

        health = self.get_health(
            provider_name
        )

        return bool(
            health
            and health.status
            == ProviderStatus.AVAILABLE
        )

    def _ensure_record(
        self,
        provider_name: str,
    ) -> _ProviderRuntimeRecord:

        record = self._records.get(
            provider_name
        )

        if record is None:
            record = _ProviderRuntimeRecord(
                provider_name=provider_name,
            )

            self._records[
                provider_name
            ] = record

        return record

    @staticmethod
    def _snapshot(
        record: _ProviderRuntimeRecord,
    ) -> ProviderHealth:

        available = (
            record.status
            == ProviderStatus.AVAILABLE
        )

        return ProviderHealth(
            provider_name=record.provider_name,
            status=record.status,
            available=available,
            latency_ms=record.latency_ms,
            consecutive_failures=(
                record.consecutive_failures
            ),
            total_successes=record.total_successes,
            total_failures=record.total_failures,
            last_error=record.last_error,
            metadata=dict(record.metadata),
        )