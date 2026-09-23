from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingAction:
    original_input: str
    category: str
    action: str
    missing_fields: tuple[str, ...]
    data: dict[str, Any] = field(default_factory=dict)


class PendingActionManager:
    """Session-scoped unfinished action storage."""

    def __init__(self):
        self._pending: dict[str, PendingAction] = {}

    def get(self, session_id: str) -> PendingAction | None:
        return self._pending.get(str(session_id))

    def set(self, session_id: str, action: PendingAction) -> None:
        self._pending[str(session_id)] = action

    def clear(self, session_id: str) -> None:
        self._pending.pop(str(session_id), None)

    def has(self, session_id: str) -> bool:
        return str(session_id) in self._pending
