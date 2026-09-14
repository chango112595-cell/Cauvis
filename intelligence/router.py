import time

from intelligence.models import ModelRequest, ModelResponse
from intelligence.policy import ExecutionStrategy, IntelligencePolicy
from intelligence.provider_config import (
    ProviderConfigGate,
    ProviderConfiguration,
)
from intelligence.provider_runtime import (
    ProviderRuntime,
    ProviderStatus,
)


class ModelProvider:
    """Base interface for any AI model provider."""

    name = "base"
    model = "unknown"
    capabilities: set[str] = set()

    def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError(
            "Model providers must implement the generate method."
        )


class AIModelRouter:
    """Routes AI requests according to Cauvis intelligence policy."""

    def __init__(
        self,
        provider_runtime: ProviderRuntime | None = None,
        provider_config_gate: ProviderConfigGate | None = None,
    ):
        self.providers: dict[str, ModelProvider] = {}
        self.default_provider: str | None = None

        self.provider_runtime = (
            provider_runtime
            or ProviderRuntime()
        )

        self.provider_config_gate = (
            provider_config_gate
            or ProviderConfigGate()
        )

        self.provider_configurations: dict[
            str,
            ProviderConfiguration,
        ] = {}

    # ---------------------------------------------------------
    # PROVIDER REGISTRATION
    # ---------------------------------------------------------

    def register_provider(self, provider: ModelProvider) -> None:
        """Register an AI provider with Cauvis."""

        self.providers[provider.name] = provider

        configuration = (
            self.provider_config_gate.inspect(
                provider_name=provider.name,
                credential_env_var=getattr(
                    provider,
                    "credential_env_var",
                    None,
                ),
                enabled=bool(
                    getattr(
                        provider,
                        "enabled",
                        True,
                    )
                ),
                credential_required=bool(
                    getattr(
                        provider,
                        "credential_required",
                        False,
                    )
                ),
                metadata={
                    "model": str(
                        getattr(
                            provider,
                            "model",
                            "unknown",
                        )
                    ),
                },
            )
        )

        self.provider_configurations[
            provider.name
        ] = configuration

        self.provider_runtime.register(
            provider.name,
            metadata={
                "model": str(
                    getattr(
                        provider,
                        "model",
                        "unknown",
                    )
                ),
                "configuration": (
                    configuration.to_dict()
                ),
            },
        )

        if self.default_provider is None:
            self.default_provider = provider.name

    def remove_provider(self, provider_name: str) -> None:
        """Remove a registered provider."""

        if provider_name in self.providers:
            del self.providers[provider_name]

        self.provider_runtime.remove(
            provider_name
        )

        self.provider_configurations.pop(
            provider_name,
            None,
        )

        if self.default_provider == provider_name:
            self.default_provider = next(
                iter(self.providers),
                None,
            )

    def set_default_provider(self, provider_name: str) -> None:
        """Set the default provider."""

        if provider_name not in self.providers:
            raise ValueError(
                f"Unknown AI provider: {provider_name}"
            )

        self.default_provider = provider_name

    # ---------------------------------------------------------
    # PROVIDER DISCOVERY
    # ---------------------------------------------------------

    def list_providers(self) -> list[str]:
        """Return the names of all registered providers."""

        return list(self.providers.keys())

    def get_provider(
        self,
        provider_name: str,
    ) -> ModelProvider | None:
        """Return a provider by name."""

        return self.providers.get(provider_name)

    def get_provider_configuration(
        self,
        provider_name: str,
    ) -> ProviderConfiguration | None:
        """
        Return the safe configuration snapshot for a provider.

        Credential values are never stored in this snapshot.
        """

        return self.provider_configurations.get(
            provider_name
        )

    def _is_provider_configured(
        self,
        provider_name: str,
    ) -> bool:
        """
        Return True only when the registered provider has a
        configuration snapshot that is explicitly configured.

        Missing configuration state fails closed.
        """

        configuration = (
            self.get_provider_configuration(
                provider_name
            )
        )

        return bool(
            configuration
            and configuration.enabled
            and configuration.configured
        )


    def _provider_runtime_rank(
        self,
        provider_name: str,
    ) -> int | None:
        """
        Return runtime preference rank for a provider.

        Lower values are preferred.

        AVAILABLE:
            Verified healthy and preferred.

        UNKNOWN:
            Eligible because a newly registered provider
            has not yet had a chance to prove availability.

        DEGRADED:
            Eligible only behind AVAILABLE and UNKNOWN.

        UNAVAILABLE / DISABLED:
            Excluded from automatic selection.

        Missing runtime state fails closed.
        """

        health = self.provider_runtime.get_health(
            provider_name
        )

        if health is None:
            return None

        ranks = {
            ProviderStatus.AVAILABLE: 0,
            ProviderStatus.UNKNOWN: 1,
            ProviderStatus.DEGRADED: 2,
        }

        return ranks.get(
            health.status
        )

    def _ranked_providers(
        self,
    ) -> tuple[ModelProvider, ...]:
        """
        Return configured providers ordered by runtime health.

        Registration order is preserved when providers have
        the same runtime rank.
        """

        ranked: list[
            tuple[int, int, ModelProvider]
        ] = []

        for registration_index, provider in enumerate(
            self.providers.values()
        ):
            if not self._is_provider_configured(
                provider.name
            ):
                continue

            runtime_rank = (
                self._provider_runtime_rank(
                    provider.name
                )
            )

            if runtime_rank is None:
                continue

            ranked.append(
                (
                    runtime_rank,
                    registration_index,
                    provider,
                )
            )

        ranked.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )

        return tuple(
            item[2]
            for item in ranked
        )

    # ---------------------------------------------------------
    # CAPABILITY MATCHING
    # ---------------------------------------------------------

    def find_capable_provider(
        self,
        required_capabilities: set[str],
        preferred_provider: str | None = None,
    ) -> ModelProvider | None:
        """
        Find a provider capable of handling the requested task.

        If a preferred provider is supplied and it has all required
        capabilities, it will be selected first.
        """

        if preferred_provider:
            provider = self.providers.get(preferred_provider)

            if (
                provider is not None
                and self._is_provider_configured(
                    provider.name
                )
                and self._provider_runtime_rank(
                    provider.name
                )
                is not None
            ):
                if required_capabilities.issubset(
                    provider.capabilities
                ):
                    return provider

        for provider in self._ranked_providers():
            if required_capabilities.issubset(
                provider.capabilities
            ):
                return provider

        return None

    # ---------------------------------------------------------
    # STRATEGY ROUTING
    # ---------------------------------------------------------

    def select_provider(
        self,
        policy: IntelligencePolicy,
        required_capabilities: set[str] | None = None,
        provider_name: str | None = None,
    ) -> ModelProvider | None:
        """
        Select a provider using the execution strategy.

        LOCAL:
            Prefer a local provider.

        CLOUD:
            Prefer a cloud provider.

        HYBRID:
            Prefer a provider capable of supporting the task.
            Hybrid orchestration will be expanded later.
        """

        required_capabilities = required_capabilities or set()

        # Explicit provider selection always gets priority.
        if provider_name:
            provider = self.providers.get(provider_name)

            if (
                provider is not None
                and self._is_provider_configured(
                    provider.name
                )
                and self._provider_runtime_rank(
                    provider.name
                )
                is not None
            ):
                return provider

        # -----------------------------------------------------
        # LOCAL
        # -----------------------------------------------------

        if policy.strategy == ExecutionStrategy.LOCAL:
            provider = self._find_by_type(
                "local",
                required_capabilities,
            )

            if provider is not None:
                return provider

        # -----------------------------------------------------
        # CLOUD
        # -----------------------------------------------------

        if policy.strategy == ExecutionStrategy.CLOUD:
            provider = self._find_by_type(
                "cloud",
                required_capabilities,
            )

            if provider is not None:
                return provider

        # -----------------------------------------------------
        # HYBRID
        # -----------------------------------------------------

        if policy.strategy == ExecutionStrategy.HYBRID:
            provider = self.find_capable_provider(
                required_capabilities,
            )

            if provider is not None:
                return provider

        # -----------------------------------------------------
        # FALLBACK
        # -----------------------------------------------------

        if self.default_provider:
            provider = self.providers.get(
                self.default_provider
            )

            if (
                provider is not None
                and self._is_provider_configured(
                    provider.name
                )
                and self._provider_runtime_rank(
                    provider.name
                )
                is not None
            ):
                return provider

        return None

    def _find_by_type(
        self,
        provider_type: str,
        required_capabilities: set[str],
    ) -> ModelProvider | None:
        """Find a provider matching a provider type and capabilities."""

        for provider in self._ranked_providers():

            provider_types = getattr(
                provider,
                "provider_types",
                set(),
            )

            if provider_type not in provider_types:
                continue

            if required_capabilities.issubset(
                provider.capabilities
            ):
                return provider

        return None


    def _policy_candidates(
        self,
        policy: IntelligencePolicy,
        required_capabilities: set[str],
        provider_name: str | None = None,
    ) -> tuple[ModelProvider, ...]:
        """
        Build the ordered provider candidates for one
        policy-aware request.

        Explicit provider selection is intentionally limited to
        that provider only. Cauvis must not silently substitute
        another provider when the caller explicitly names one.

        Automatic routing uses runtime-aware order. LOCAL and
        CLOUD strategies try their preferred provider type first,
        then the alternate type only when policy allows it.

        The default provider is used only when the strategy
        produces no eligible candidates, preserving the previous
        selection behavior.
        """

        # -----------------------------------------------------
        # Explicit provider: no silent failover
        # -----------------------------------------------------

        if provider_name:
            provider = self.providers.get(
                provider_name
            )

            if (
                provider is not None
                and self._is_provider_configured(
                    provider.name
                )
                and self._provider_runtime_rank(
                    provider.name
                )
                is not None
            ):
                return (
                    provider,
                )

            return ()

        candidates: list[
            ModelProvider
        ] = []

        candidate_names: set[str] = set()

        def append_matching(
            provider_type: str | None = None,
        ) -> None:
            """
            Append configured, runtime-eligible providers that
            satisfy the requested capabilities.

            When provider_type is supplied, only providers of that
            type are appended. Existing candidates are not duplicated.
            """

            for provider in self._ranked_providers():

                if provider.name in candidate_names:
                    continue

                if provider_type is not None:
                    provider_types = getattr(
                        provider,
                        "provider_types",
                        set(),
                    )

                    if (
                        provider_type
                        not in provider_types
                    ):
                        continue

                if not required_capabilities.issubset(
                    provider.capabilities
                ):
                    continue

                candidates.append(
                    provider
                )

                candidate_names.add(
                    provider.name
                )

        # -----------------------------------------------------
        # LOCAL
        # -----------------------------------------------------

        if (
            policy.strategy
            == ExecutionStrategy.LOCAL
        ):
            # Honor the requested strategy first.
            append_matching(
                "local"
            )

            # Cloud may rescue a failed/unavailable local provider
            # only when the policy explicitly permits cloud use.
            if policy.cloud_allowed:
                append_matching(
                    "cloud"
                )

        # -----------------------------------------------------
        # CLOUD
        # -----------------------------------------------------

        elif (
            policy.strategy
            == ExecutionStrategy.CLOUD
        ):
            # Honor the requested strategy first.
            append_matching(
                "cloud"
            )

            # Local AI is the resilient offline fallback when the
            # device/policy says local execution is permitted.
            if policy.local_allowed:
                append_matching(
                    "local"
                )

        # -----------------------------------------------------
        # HYBRID
        # -----------------------------------------------------

        elif (
            policy.strategy
            == ExecutionStrategy.HYBRID
        ):
            # Hybrid may consider both provider classes, but still
            # respects the policy's local/cloud permission flags.
            if (
                policy.local_allowed
                and policy.cloud_allowed
            ):
                append_matching()

            else:
                if policy.local_allowed:
                    append_matching(
                        "local"
                    )

                if policy.cloud_allowed:
                    append_matching(
                        "cloud"
                    )

        if candidates:
            return tuple(
                candidates
            )

        # -----------------------------------------------------
        # Preserve previous default fallback behavior
        # -----------------------------------------------------

        if self.default_provider:
            provider = self.providers.get(
                self.default_provider
            )

            if (
                provider is not None
                and self._is_provider_configured(
                    provider.name
                )
                and self._provider_runtime_rank(
                    provider.name
                )
                is not None
            ):
                return (
                    provider,
                )

        return ()

    # ---------------------------------------------------------
    # GENERATION
    # ---------------------------------------------------------

    def generate(
        self,
        request: ModelRequest,
        policy: IntelligencePolicy | None = None,
        required_capabilities: set[str] | None = None,
        provider_name: str | None = None,
    ) -> ModelResponse:

        required_capabilities = required_capabilities or set()

        # -----------------------------------------------------
        # POLICY-AWARE ROUTING
        # -----------------------------------------------------

        if policy is not None:
            candidates = self._policy_candidates(
                policy=policy,
                required_capabilities=required_capabilities,
                provider_name=provider_name,
            )

            if not candidates:
                return ModelResponse(
                    text="",
                    model="none",
                    provider="none",
                    success=False,
                    error=(
                        "No AI provider is available for the "
                        f"{policy.strategy.value} execution strategy."
                    ),
                )

            last_response: ModelResponse | None = None

            for provider in candidates:
                response = self._generate_with_runtime(
                    provider,
                    request,
                )

                if response.success:
                    return response

                last_response = response

                # An explicitly requested provider must never
                # silently fail over to a different provider.
                if provider_name:
                    break

            if last_response is not None:
                return last_response

            return ModelResponse(
                text="",
                model="none",
                provider="none",
                success=False,
                error=(
                    "AI provider routing ended without "
                    "a provider response."
                ),
            )

        # -----------------------------------------------------
        # LEGACY / DEFAULT ROUTING
        # -----------------------------------------------------

        selected_provider = (
            provider_name
            or self.default_provider
        )

        if selected_provider is None:
            return ModelResponse(
                text="",
                model="none",
                provider="none",
                success=False,
                error="No AI model provider is registered.",
            )

        provider = self.providers.get(
            selected_provider
        )

        if provider is None:
            return ModelResponse(
                text="",
                model="none",
                provider=selected_provider,
                success=False,
                error=(
                    f"AI provider '{selected_provider}' "
                    "is not registered."
                ),
            )

        if not self._is_provider_configured(
            selected_provider
        ):
            configuration = (
                self.get_provider_configuration(
                    selected_provider
                )
            )

            reason = (
                configuration.reason
                if configuration is not None
                else (
                    "Provider configuration state "
                    "is unavailable."
                )
            )

            return ModelResponse(
                text="",
                model=str(
                    getattr(
                        provider,
                        "model",
                        "unknown",
                    )
                ),
                provider=selected_provider,
                success=False,
                error=(
                    f"AI provider '{selected_provider}' "
                    "is not configured for use. "
                    f"{reason}"
                ),
            )

        return self._generate_with_runtime(
            provider,
            request,
        )

    def _generate_with_runtime(
        self,
        provider: ModelProvider,
        request: ModelRequest,
    ) -> ModelResponse:
        """
        Execute one provider request while recording the
        verified runtime outcome.

        Records real provider success, failure, and latency.

        Runtime state also informs automatic provider selection.
        This method executes exactly one provider operation; any
        cross-provider failover is controlled by generate().
        """

        started = time.perf_counter()

        try:
            response = provider.generate(
                request
            )

        except Exception as exc:
            latency_ms = (
                time.perf_counter() - started
            ) * 1000.0

            self.provider_runtime.record_failure(
                provider.name,
                error=str(exc),
                latency_ms=latency_ms,
                metadata={
                    "exception_type": (
                        type(exc).__name__
                    ),
                },
            )

            raise

        latency_ms = (
            time.perf_counter() - started
        ) * 1000.0

        if response.success:
            self.provider_runtime.record_success(
                provider.name,
                latency_ms=latency_ms,
                metadata={
                    "model": response.model,
                },
            )

        else:
            self.provider_runtime.record_failure(
                provider.name,
                error=(
                    response.error
                    or "Provider returned an unsuccessful response."
                ),
                latency_ms=latency_ms,
                metadata={
                    "model": response.model,
                },
            )

        return response
