from dataclasses import dataclass


@dataclass
class Intent:
    name: str
    confidence: float
    original_input: str


class IntentDetector:

    def detect(self, text: str) -> Intent:
        normalized = text.lower().strip()

        if normalized in {"hello", "hi", "hey"}:
            return Intent(
                name="greeting",
                confidence=1.0,
                original_input=text,
            )

        shutdown_commands = {
            "shutdown",
            "exit",
            "quit",
            "salir",
            "cerrar",
            "apagar",
        }

        if normalized in shutdown_commands:
            return Intent(
                name="shutdown",
                confidence=1.0,
                original_input=text,
            )

        if normalized.startswith("what"):
            return Intent(
                name="question",
                confidence=0.8,
                original_input=text,
            )

        if normalized.startswith("how"):
            return Intent(
                name="question",
                confidence=0.8,
                original_input=text,
            )

        return Intent(
            name="general",
            confidence=0.5,
            original_input=text,
        )