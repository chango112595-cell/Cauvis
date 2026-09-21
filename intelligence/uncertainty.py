from dataclasses import dataclass
from enum import Enum

from core.routing_language import RoutingLanguageNormalizer


class VerificationRequestKind(str, Enum):
    NONE = "none"
    VERIFY = "verify"
    CONFIRM = "confirm"
    FACT_CHECK = "fact_check"
    CERTAINTY = "certainty"


@dataclass(frozen=True)
class FactualUncertaintyDecision:
    requested: bool
    kind: VerificationRequestKind
    requires_independent_evidence: bool
    reason: str
    signals: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "kind": self.kind.value,
            "requires_independent_evidence": self.requires_independent_evidence,
            "reason": self.reason,
            "signals": list(self.signals),
        }


class FactualUncertaintyClassifier:
    _FACT_CHECK_PREFIXES = (
        "fact check ",
        "fact-check ",
        "can you fact check ",
        "could you fact check ",
        "please fact check ",
    )

    _VERIFY_PREFIXES = (
        "verify ",
        "verify that ",
        "verify whether ",
        "can you verify ",
        "could you verify ",
        "please verify ",
        "i want you to verify ",
        "i need you to verify ",
    )

    _CONFIRM_PREFIXES = (
        "confirm ",
        "confirm that ",
        "confirm whether ",
        "can you confirm ",
        "could you confirm ",
        "please confirm ",
        "i want you to confirm ",
        "i need you to confirm ",
    )

    _CERTAINTY_PREFIXES = (
        "are you sure ",
        "are you certain ",
        "how sure are you ",
        "how certain are you ",
        "is it true that ",
        "is that true ",
        "is this true ",
        "is that accurate ",
        "is this accurate ",
        "is that correct ",
        "is this correct ",
    )

    def classify(self, user_input: str) -> FactualUncertaintyDecision:
        text = (
            RoutingLanguageNormalizer.normalize(user_input)
            .strip()
            .lstrip("¿¡")
            .rstrip(" ?.!,:;")
        )

        if not text:
            return self._none()

        groups = (
            (VerificationRequestKind.FACT_CHECK, self._FACT_CHECK_PREFIXES),
            (VerificationRequestKind.VERIFY, self._VERIFY_PREFIXES),
            (VerificationRequestKind.CONFIRM, self._CONFIRM_PREFIXES),
            (VerificationRequestKind.CERTAINTY, self._CERTAINTY_PREFIXES),
        )

        for kind, prefixes in groups:
            for prefix in prefixes:
                signal = prefix.rstrip()
                if text.startswith(signal):
                    return FactualUncertaintyDecision(
                        requested=True,
                        kind=kind,
                        requires_independent_evidence=True,
                        reason=(
                            "The user explicitly requested independent "
                            "factual verification or certainty."
                        ),
                        signals=(signal,),
                    )

        return self._none()

    @staticmethod
    def _none() -> FactualUncertaintyDecision:
        return FactualUncertaintyDecision(
            requested=False,
            kind=VerificationRequestKind.NONE,
            requires_independent_evidence=False,
            reason="No explicit independent-verification request was detected.",
        )
