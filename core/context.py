from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionContext:
    user_input: str
    session_id: str
    metadata: dict[str, Any] = field(default_factory=dict)