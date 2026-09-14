from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationTurn:
    """One verified turn in a Cauvis conversation session."""

    role: str
    content: str


class ConversationRuntime:
    """
    In-memory session conversation history for Cauvis.

    This is short-term conversation context only.

    It is intentionally separate from:
    - persistent user memory
    - verified experience memory
    - future learning/self-improvement memory.
    """

    def __init__(
        self,
        max_turns: int = 20,
        max_context_characters: int = 12000,
    ):
        if max_turns <= 0:
            raise ValueError(
                "max_turns must be greater than zero."
            )

        if max_context_characters <= 0:
            raise ValueError(
                "max_context_characters must be greater than zero."
            )

        self.max_turns = int(
            max_turns
        )

        self.max_context_characters = int(
            max_context_characters
        )

        self._sessions: dict[
            str,
            list[ConversationTurn],
        ] = {}

    def append(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> ConversationTurn:
        session_id = self._normalize_session_id(
            session_id
        )

        role = str(role).strip().lower()

        if role not in {
            "user",
            "assistant",
        }:
            raise ValueError(
                "Conversation role must be "
                "'user' or 'assistant'."
            )

        content = str(content).strip()

        if not content:
            raise ValueError(
                "Conversation content must not be empty."
            )

        turn = ConversationTurn(
            role=role,
            content=content,
        )

        turns = self._sessions.setdefault(
            session_id,
            [],
        )

        turns.append(
            turn
        )

        if len(turns) > self.max_turns:
            del turns[
                : len(turns) - self.max_turns
            ]

        return turn

    def turns(
        self,
        session_id: str,
    ) -> tuple[ConversationTurn, ...]:
        session_id = self._normalize_session_id(
            session_id
        )

        return tuple(
            self._sessions.get(
                session_id,
                (),
            )
        )

    def turn_count(
        self,
        session_id: str,
    ) -> int:
        return len(
            self.turns(
                session_id
            )
        )

    def has_history(
        self,
        session_id: str,
    ) -> bool:
        return (
            self.turn_count(
                session_id
            )
            > 0
        )

    def clear(
        self,
        session_id: str,
    ) -> None:
        session_id = self._normalize_session_id(
            session_id
        )

        self._sessions.pop(
            session_id,
            None,
        )

    def clear_all(self) -> None:
        self._sessions.clear()

    def render_context(
        self,
        session_id: str,
    ) -> str:
        """
        Render prior turns for model context.

        The newest turns are retained when the configured
        character budget is exceeded.
        """

        turns = self.turns(
            session_id
        )

        if not turns:
            return ""

        rendered: list[str] = []

        for turn in turns:
            label = (
                "User"
                if turn.role == "user"
                else "Cauvis"
            )

            rendered.append(
                f"{label}: {turn.content}"
            )

        selected: list[str] = []
        used_characters = 0

        for item in reversed(
            rendered
        ):
            additional = (
                len(item)
                + (1 if selected else 0)
            )

            if (
                selected
                and used_characters + additional
                > self.max_context_characters
            ):
                break

            if (
                not selected
                and len(item)
                > self.max_context_characters
            ):
                item = item[
                    -self.max_context_characters:
                ]

                additional = len(
                    item
                )

            selected.append(
                item
            )

            used_characters += (
                additional
            )

        selected.reverse()

        return "\n".join(
            selected
        )

    @staticmethod
    def _normalize_session_id(
        session_id: str,
    ) -> str:
        session_id = str(
            session_id
        ).strip()

        if not session_id:
            raise ValueError(
                "session_id must not be empty."
            )

        return session_id
