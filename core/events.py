from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class CauvisEvent:
    event_type: str
    timestamp: datetime
    data: dict[str, Any]