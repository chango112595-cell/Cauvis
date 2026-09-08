from intelligence.models import ModelRequest, ModelResponse
from intelligence.policy import ExecutionStrategy, IntelligencePolicy


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

    def __init__(self):
        self.providers: dict[str, ModelProvider] = {}
        self.default_provider: str | None = None

    # ---------------------------------------------------------
    # PROVIDER REGISTRATION
    # ---------------------------------------------------------

    def register_provider(self, provider: ModelProvider) -> None:
        """Register an AI provider with Cauvis."""

        self.providers[provider.name] = provider

        if self.default_provider is None:
            self.default_provider = provider.name

    def remove_provider(self, provider_name: str) -> None:
        """Remove a registered provider."""

        if provider_name in self.providers:
            del self.providers[provider_name]

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

            if provider is not None:
                if required_capabilities.issubset(
                    provider.capabilities
                ):
                    return provider

        for provider in self.providers.values():
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

            if provider is not None:
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
            return self.providers.get(
                self.default_provider
            )

        return None

    def _find_by_type(
        self,
        provider_type: str,
        required_capabilities: set[str],
    ) -> ModelProvider | None:
        """Find a provider matching a provider type and capabilities."""

        for provider in self.providers.values():

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
            provider = self.select_provider(
                policy=policy,
                required_capabilities=required_capabilities,
                provider_name=provider_name,
            )

            if provider is None:
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

            return provider.generate(request)

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

        return provider.generate(request)