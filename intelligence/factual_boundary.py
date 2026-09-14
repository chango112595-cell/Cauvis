from dataclasses import dataclass
from enum import Enum
import re


class FactualRequestKind(str, Enum):
    """
    Freshness class for a factual request.

    GENERAL:
        Stable/general knowledge may be answered without fresh
        retrieval, but model output is still not externally verified.

    CURRENT:
        The request depends on time-sensitive/live information.

    EXPLICIT_RETRIEVAL:
        The user explicitly requested web/online/retrieval evidence.
    """

    GENERAL = "general"
    CURRENT = "current"
    EXPLICIT_RETRIEVAL = "explicit_retrieval"


@dataclass(frozen=True)
class FactualBoundaryDecision:
    """
    Deterministic decision about whether fresh evidence is required.

    This decision does NOT verify any factual claim.
    It only defines the evidence requirement for answering.
    """

    kind: FactualRequestKind
    requires_fresh_evidence: bool
    requires_retrieval: bool
    reason: str
    signals: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "requires_fresh_evidence": (
                self.requires_fresh_evidence
            ),
            "requires_retrieval": (
                self.requires_retrieval
            ),
            "reason": self.reason,
            "signals": list(
                self.signals
            ),
        }


class FactualBoundaryClassifier:
    """
    Conservative deterministic freshness/retrieval classifier.

    This is intentionally separate from TaskAnalyzer.

    TaskAnalyzer answers:
        "What capabilities might this task require?"

    This classifier answers:
        "Must Cauvis have fresh external/runtime evidence before
         presenting the answer as current/live information?"
    """

    _EXPLICIT_RETRIEVAL_PHRASES = (
        "search the web",
        "search online",
        "search the internet",
        "browse the web",
        "browse online",
        "look online",
        "look it up online",
        "look this up online",
        "check online",
        "verify online",
        "verify on the web",
        "use the internet",
        "web search",
        "find online",
        "find it online",
    )

    _TEMPORAL_PHRASES = (
        "latest",
        "right now",
        "as of now",
        "as of today",
        "today",
        "tonight",
        "this morning",
        "this afternoon",
        "this evening",
        "this week",
        "this month",
    )

    _LIVE_DOMAIN_PATTERNS = (
        r"\bweather\s+(?:in|for|near)\b",
        r"\bforecast\s+(?:in|for|near)\b",
        r"\b(?:stock|share)\s+price\b",
        r"\bexchange\s+rate\b",
        r"\bflight\s+status\b",
        r"\btraffic\s+(?:in|near|on)\b",
        r"\b(?:live|final)\s+score\b",
        r"\bscore\s+(?:of|for|between)\b",
        r"\b(?:league|team)\s+standings\b",
        r"\bservice\s+outage\b",
        r"\bpower\s+outage\b",
        r"\bavailability\s+(?:today|now)\b",
        r"\bopen\s+now\b",
    )

    _CURRENT_ENTITY_PATTERN = re.compile(
        r"\bcurrent\s+("
        r"president|"
        r"prime minister|"
        r"governor|"
        r"mayor|"
        r"ceo|"
        r"price|"
        r"weather|"
        r"score|"
        r"status|"
        r"version|"
        r"release|"
        r"schedule|"
        r"ranking|"
        r"standings|"
        r"rate|"
        r"rates|"
        r"population"
        r")\b",
        re.IGNORECASE,
    )

    def classify(
        self,
        user_input: str,
    ) -> FactualBoundaryDecision:
        text = " ".join(
            user_input.lower().strip().split()
        )

        if not text:
            return FactualBoundaryDecision(
                kind=FactualRequestKind.GENERAL,
                requires_fresh_evidence=False,
                requires_retrieval=False,
                reason=(
                    "No factual freshness signal was present."
                ),
            )

        retrieval_signals = tuple(
            phrase
            for phrase
            in self._EXPLICIT_RETRIEVAL_PHRASES
            if phrase in text
        )

        if retrieval_signals:
            return FactualBoundaryDecision(
                kind=(
                    FactualRequestKind.EXPLICIT_RETRIEVAL
                ),
                requires_fresh_evidence=True,
                requires_retrieval=True,
                reason=(
                    "The user explicitly requested external "
                    "web/online retrieval."
                ),
                signals=retrieval_signals,
            )

        current_signals: list[str] = []

        for phrase in self._TEMPORAL_PHRASES:
            if phrase in text:
                current_signals.append(
                    phrase
                )

        current_match = (
            self._CURRENT_ENTITY_PATTERN.search(
                text
            )
        )

        if current_match:
            current_signals.append(
                current_match.group(0)
            )

        for pattern in self._LIVE_DOMAIN_PATTERNS:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                current_signals.append(
                    match.group(0)
                )

        if current_signals:
            return FactualBoundaryDecision(
                kind=FactualRequestKind.CURRENT,
                requires_fresh_evidence=True,
                requires_retrieval=True,
                reason=(
                    "The request depends on current/live or "
                    "time-sensitive factual information."
                ),
                signals=tuple(
                    dict.fromkeys(
                        current_signals
                    )
                ),
            )

        return FactualBoundaryDecision(
            kind=FactualRequestKind.GENERAL,
            requires_fresh_evidence=False,
            requires_retrieval=False,
            reason=(
                "No explicit retrieval or current/live freshness "
                "signal was detected."
            ),
        )
