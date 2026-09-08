from core.config import CauvisConfig
from core.context import ExecutionContext
from core.state import CauvisState
from core.intent import IntentDetector
from core.response import CauvisResponse


class CauvisOrchestrator:

    def __init__(self, config: CauvisConfig):
        self.config = config
        self.state = CauvisState()
        self.intent_detector = IntentDetector()

    def handle(self, user_input: str) -> CauvisResponse:
        context = ExecutionContext(
            user_input=user_input,
            session_id="local-session",
        )

        intent = self.intent_detector.detect(user_input)

        if intent.name == "shutdown":
            self.state.running = False

            return CauvisResponse(
                status="success",
                message="Cauvis shutting down.",
                intent=intent.name,
                confidence=intent.confidence,
            )

        return CauvisResponse(
            status="success",
            message=f"I understood that as a {intent.name} request.",
            intent=intent.name,
            confidence=intent.confidence,
            data={
                "input": context.user_input,
            },
        )