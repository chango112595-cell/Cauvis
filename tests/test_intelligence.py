from intelligence.brain import CauvisBrain
from intelligence.models import ModelRequest, ModelResponse
from intelligence.router import AIModelRouter, ModelProvider


class FakeProvider(ModelProvider):

    name = "fake"
    model = "fake-model"

    def generate(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            text=f"Fake AI received: {request.prompt}",
            model=self.model,
            provider=self.name,
            success=True,
            metadata={
                "test": True,
            },
        )


def main():
    router = AIModelRouter()

    provider = FakeProvider()
    router.register_provider(provider)

    brain = CauvisBrain(router)

    response = brain.think(
        "What is artificial intelligence?"
    )

    print("Success:", response.success)
    print("Provider:", response.provider)
    print("Model:", response.model)
    print("Response:", response.text)
    print("Metadata:", response.metadata)


if __name__ == "__main__":
    main()