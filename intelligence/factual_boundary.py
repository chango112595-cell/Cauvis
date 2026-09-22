from dataclasses import dataclass
from enum import Enum
import re

from core.routing_language import RoutingLanguageNormalizer


class FactualRequestKind(str, Enum):
    """
    Freshness/provenance class for a factual request.
    """

    GENERAL = "general"
    CURRENT = "current"
    EXPLICIT_RETRIEVAL = "explicit_retrieval"
    RUNTIME_CURRENT = "runtime_current"
    CAPABILITY_STATUS = "capability_status"
    USER_ASSERTION = "user_assertion"


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
            "requires_fresh_evidence": self.requires_fresh_evidence,
            "requires_retrieval": self.requires_retrieval,
            "reason": self.reason,
            "signals": list(self.signals),
        }


class FactualBoundaryClassifier:
    """
    Conservative deterministic freshness/retrieval classifier.

    Distinguishes:
    - stable/general knowledge
    - current external facts
    - explicit external retrieval
    - current facts about the running Cauvis runtime
    - capability-status questions
    - user assertions that are not verification requests
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
        "tomorrow",
        "later today",
        "this morning",
        "this afternoon",
        "this evening",
        "this week",
        "this weekend",
        "this month",
        "next week",
        "next month",
    )

    _CAPABILITY_PHRASES = (
        "browse the web",
        "search the web",
        "use the web",
        "use the internet",
        "control my computer",
        "control the computer",
        "access my files",
        "access files",
        "use my files",
        "set reminders",
        "create reminders",
        "use tools",
        "run tools",
        "execute tools",
    )

    _CAPABILITY_CONTEXT_PHRASES = (
        "in this running cauvis instance",
        "in this cauvis instance",
        "in this running instance",
        "currently available",
        "available right now",
        "capabilities are available",
        "capabilities do you have",
    )

    _CAPABILITY_QUESTION_PREFIXES = (
        "which capabilities",
        "what capabilities",
        "what can you do",
        "what are you able to do",
    )

    _RUNTIME_CURRENT_PATTERNS = (
        (
            r"\b(?:what|which)\b.{0,50}"
            r"\b(?:ai\s+)?model\b.{0,50}"
            r"\b(?:using|use|active|running)\b"
        ),
        (
            r"\b(?:what|which)\b.{0,50}"
            r"\bprovider\b.{0,50}"
            r"\b(?:using|use|active|running)\b"
        ),
        r"\bactive\s+(?:ai\s+)?model\b",
        r"\bactive\s+provider\b",
        r"\brunning\s+(?:ai\s+)?model\b",
        r"\brunning\s+provider\b",
    )

    _LIVE_DOMAIN_PATTERNS = (
        r"\bweather\s+(?:in|for|near)\b",
        r"\bforecast\s+(?:in|for|near)\b",
        r"\bweather\s+(?:today|tonight|tomorrow|this\s+weekend|next\s+week)\b",
        (
            r"\b(?:how\s+(?:the\s+)?weather|the\s+weather)\s+"
            r"(?:is\s+)?going\s+to\s+be\b"
        ),
        r"\bwhat\s+will\s+(?:the\s+)?weather\s+be\b",
        r"\bwill\s+it\s+(?:rain|snow|storm)\b",
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

    _GENERIC_CURRENT_REQUEST_PATTERN = re.compile(
        (
            r"^(?:who|what|which|where|when|why|how|"
            r"is|are|can|could|would|will|"
            r"tell\s+me|give\s+me|show\s+me|"
            r"find|check|verify)\b"
            r".{0,180}\bcurrent\b"
        ),
        re.IGNORECASE,
    )

    _CURRENT_ASSERTION_PATTERN = re.compile(
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
        r")\s+(?:is|are)\b",
        re.IGNORECASE,
    )

    def classify(
        self,
        user_input: str,
    ) -> FactualBoundaryDecision:
        text = RoutingLanguageNormalizer.normalize(
            user_input
        )

        if not text:
            return FactualBoundaryDecision(
                kind=FactualRequestKind.GENERAL,
                requires_fresh_evidence=False,
                requires_retrieval=False,
                reason="No factual freshness signal was present.",
            )

        capability_signals = self._capability_status_signals(text)

        if capability_signals:
            return FactualBoundaryDecision(
                kind=FactualRequestKind.CAPABILITY_STATUS,
                requires_fresh_evidence=False,
                requires_retrieval=False,
                reason=(
                    "The user is asking about current Cauvis capability "
                    "availability, not requesting external retrieval."
                ),
                signals=capability_signals,
            )

        retrieval_signals = tuple(
            phrase
            for phrase in self._EXPLICIT_RETRIEVAL_PHRASES
            if phrase in text
        )

        if retrieval_signals:
            return FactualBoundaryDecision(
                kind=FactualRequestKind.EXPLICIT_RETRIEVAL,
                requires_fresh_evidence=True,
                requires_retrieval=True,
                reason=(
                    "The user explicitly requested external "
                    "web/online retrieval."
                ),
                signals=retrieval_signals,
            )

        runtime_signals = []

        for pattern in self._RUNTIME_CURRENT_PATTERNS:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                runtime_signals.append(match.group(0))

        if runtime_signals:
            return FactualBoundaryDecision(
                kind=FactualRequestKind.RUNTIME_CURRENT,
                requires_fresh_evidence=False,
                requires_retrieval=False,
                reason=(
                    "The request asks for current information about "
                    "the running Cauvis runtime. Verified runtime "
                    "context, not web retrieval, is the appropriate "
                    "evidence source."
                ),
                signals=tuple(dict.fromkeys(runtime_signals)),
            )

        assertion_signal = self._current_user_assertion_signal(text)

        if assertion_signal is not None:
            return FactualBoundaryDecision(
                kind=FactualRequestKind.USER_ASSERTION,
                requires_fresh_evidence=False,
                requires_retrieval=False,
                reason=(
                    "The user supplied a current-looking factual "
                    "assertion. It may be acknowledged as user-asserted "
                    "provenance, but it is not independently verified."
                ),
                signals=(assertion_signal,),
            )

        current_signals = []

        for phrase in self._TEMPORAL_PHRASES:
            if phrase in text:
                current_signals.append(phrase)

        current_match = self._CURRENT_ENTITY_PATTERN.search(text)

        if current_match:
            current_signals.append(current_match.group(0))

        generic_current_match = (
            self._GENERIC_CURRENT_REQUEST_PATTERN.search(
                text
            )
        )

        if generic_current_match:
            current_signals.append("current")

        for pattern in self._LIVE_DOMAIN_PATTERNS:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                current_signals.append(match.group(0))

        if current_signals:
            return FactualBoundaryDecision(
                kind=FactualRequestKind.CURRENT,
                requires_fresh_evidence=True,
                requires_retrieval=True,
                reason=(
                    "The request depends on current/live or "
                    "time-sensitive external factual information."
                ),
                signals=tuple(dict.fromkeys(current_signals)),
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

    @classmethod
    def _capability_status_signals(
        cls,
        text: str,
    ) -> tuple[str, ...]:
        plain = text.rstrip(" ?.!")

        if any(
            plain.startswith(prefix)
            for prefix in cls._CAPABILITY_QUESTION_PREFIXES
        ):
            return ("capability_question",)

        capability_hits = tuple(
            phrase
            for phrase in cls._CAPABILITY_PHRASES
            if phrase in plain
        )

        if not capability_hits:
            return ()

        if any(
            context in plain
            for context in cls._CAPABILITY_CONTEXT_PHRASES
        ):
            return tuple(
                dict.fromkeys(
                    capability_hits
                    + ("runtime_capability_context",)
                )
            )

        remainder = None

        for prefix in (
            "can you ",
            "could you ",
            "are you able to ",
        ):
            if plain.startswith(prefix):
                remainder = plain[len(prefix):].strip()
                break

        if remainder is None:
            return ()

        if len(capability_hits) >= 2:
            return tuple(dict.fromkeys(capability_hits))

        allowed_suffixes = (
            "",
            " right now",
            " currently",
            " in this running cauvis instance",
            " in this cauvis instance",
            " in this running instance",
        )

        for phrase in cls._CAPABILITY_PHRASES:
            for suffix in allowed_suffixes:
                if remainder == phrase + suffix:
                    return (phrase,)

        return ()

    @classmethod
    def _current_user_assertion_signal(
        cls,
        text: str,
    ) -> str | None:
        if "?" in text:
            return None

        request_prefixes = (
            "who ",
            "what ",
            "when ",
            "where ",
            "why ",
            "how ",
            "is ",
            "are ",
            "can ",
            "could ",
            "would ",
            "will ",
            "tell me ",
            "check ",
            "verify ",
            "search ",
            "browse ",
            "find ",
            "look up ",
        )

        if text.startswith(request_prefixes):
            return None

        match = cls._CURRENT_ASSERTION_PATTERN.search(text)

        if match is None:
            return None

        return match.group(0)
