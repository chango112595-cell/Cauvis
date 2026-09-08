from dataclasses import dataclass, field
from typing import Any


@dataclass
class CauvisResponse:
    status: str
    message: str
    intent: str | None = None
    confidence: float | None = None
    data: dict[str, Any] = field(default_factory=dict)