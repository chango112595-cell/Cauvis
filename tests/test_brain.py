from intelligence.brain import CauvisBrain
from intelligence.models import ModelRequest, ModelResponse
from intelligence.router import AIModelRouter, ModelProvider


class FakeLocalProvider(ModelProvider):

    name = "fake_local"
    model = "fake-local-model"

    provider_types = {"local"}

    capabilities = {
        "chat",
        "code",
        "reasoning",
        "complexity:low",
        "complexity:medium",
        "complexity:high",
    }

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:

        return ModelResponse(
            text=(
                f"LOCAL PROVIDER RECEIVED: "
                f"{request.prompt}"
            ),
            model=self.model,
            provider=self.name,
            success=True,
            metadata={
                "provider_type": "local",
            },
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
        "tools",
        "reasoning",
        "long_context",
        "complexity:low",
        "complexity:medium",
        "complexity:high",
    }

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:

        return ModelResponse(
            text=(
                f"CLOUD PROVIDER RECEIVED: "
                f"{request.prompt}"
            ),
            model=self.model,
            provider=self.name,
            success=True,
            metadata={
                "provider_type": "cloud",
            },
        )


def main():

    router = AIModelRouter()

    router.register_provider(
        FakeLocalProvider()
    )

    router.register_provider(
        FakeCloudProvider()
    )

    brain = CauvisBrain(router)

    user_input = (
        "Build a Python program that searches "
        "the web and analyzes a screenshot"
    )

    analysis = brain.analyze(
        user_input
    )

    print("=" * 60)
    print("CAUVIS BRAIN ANALYSIS")
    print("=" * 60)

    print("\nTASK:")
    print(analysis.task)

    print("\nCAPABILITIES:")
    print(
        sorted(
            analysis.capabilities.capabilities
        )
    )

    print("\nREASONING:")
    print(analysis.reasoning)

    print("\nDEVICE:")
    print(analysis.device)

    print("\nPOLICY:")
    print(analysis.policy)

    response = brain.think(
        user_input
    )

    print("\n" + "=" * 60)
    print("ROUTED RESPONSE")
    print("=" * 60)

    print("Success:", response.success)
    print("Provider:", response.provider)
    print("Model:", response.model)
    print("Response:", response.text)

    print("\nResponse Metadata:")
    print(response.metadata)


if __name__ == "__main__":
    main()