from dataclasses import dataclass, field
from typing import Any

from intelligence.evidence import ClaimEvidenceBundle


@dataclass
class ModelRequest:
    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    text: str
    model: str
    provider: str
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    evidence: list[ClaimEvidenceBundle] = field(
        default_factory=list
    )
