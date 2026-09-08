from intelligence.models import ModelRequest, ModelResponse
from intelligence.policy import ExecutionStrategy, IntelligencePolicy
from intelligence.router import AIModelRouter, ModelProvider


class FakeLocalProvider(ModelProvider):

    name = "fake_local"
    model = "fake-local-model"

    provider_types = {"local"}

    capabilities = {
        "chat",
        "code",
    }

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:

        return ModelResponse(
            text=f"LOCAL handled: {request.prompt}",
            model=self.model,
            provider=self.name,
            success=True,
        )


class FakeCloudProvider(ModelProvider):

    name = "fake_cloud"
    model = "fake-cloud-model"

    provider_types = {"cloud"}

    capabilities = {
        "chat",
        "code",
        "vision",
        "web",
    }

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:

        return ModelResponse(
            text=f"CLOUD handled: {request.prompt}",
            model=self.model,
            provider=self.name,
            success=True,
        )


def main():

    router = AIModelRouter()

    router.register_provider(
        FakeLocalProvider()
    )

    router.register_provider(
        FakeCloudProvider()
    )

    request = ModelRequest(
        prompt="Build a Python program."
    )

    local_policy = IntelligencePolicy(
        strategy=ExecutionStrategy.LOCAL,
        local_allowed=True,
        cloud_allowed=True,
        reason="Test local routing.",
    )

    response = router.generate(
        request,
        policy=local_policy,
        required_capabilities={"code"},
    )

    print("LOCAL TEST")
    print("Success:", response.success)
    print("Provider:", response.provider)
    print("Model:", response.model)
    print("Response:", response.text)

    cloud_policy = IntelligencePolicy(
        strategy=ExecutionStrategy.CLOUD,
        local_allowed=True,
        cloud_allowed=True,
        reason="Test cloud routing.",
    )

    request = ModelRequest(
        prompt="Analyze this screenshot."
    )

    response = router.generate(
        request,
        policy=cloud_policy,
        required_capabilities={"vision"},
    )

    print("\nCLOUD TEST")
    print("Success:", response.success)
    print("Provider:", response.provider)
    print("Model:", response.model)
    print("Response:", response.text)


if __name__ == "__main__":
    main()