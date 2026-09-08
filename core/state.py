from dataclasses import dataclass, field
from typing import Any


@dataclass
class CauvisState:
    running: bool = True
    mode: str = "idle"
    current_task: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)