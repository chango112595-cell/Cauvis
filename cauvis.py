from core.config import CauvisConfig
from core.orchestrator import CauvisOrchestrator


def main():
    config = CauvisConfig()
    cauvis = CauvisOrchestrator(config, enable_ai=True)

    print("=" * 50)
    print(f"{config.name} v{config.version}")
    print("Cauvis Beta 1 online.")
    print("=" * 50)

    while cauvis.state.running:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            response = cauvis.handle(user_input)

            print(f"Cauvis: {response.message}")

            if response.intent == "shutdown":
                break

        except KeyboardInterrupt:
            print("\nCauvis shutting down.")
            break


if __name__ == "__main__":
    main()