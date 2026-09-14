from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceSourceType(str, Enum):
    """
    Origin of one piece of factual evidence.

    Source type describes where evidence came from.
    It does not, by itself, prove that a claim is true.
    """

    USER_ASSERTION = "user_assertion"
    RUNTIME_OBSERVATION = "runtime_observation"
    RETRIEVAL = "retrieval"
    PROVIDER_CITATION = "provider_citation"
    MODEL_GENERATION = "model_generation"
    UNKNOWN = "unknown"


class EvidenceStance(str, Enum):
    """Relationship between evidence and a factual claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class ClaimEvidenceStatus(str, Enum):
    """
    Current evidence-backed state of a factual claim.

    This is intentionally separate from model-generation success
    and execution VerificationResult.
    """

    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class FactualEvidence:
    """
    One provenance-bearing piece of evidence about a factual claim.

    Important:
    MODEL_GENERATION is never independent factual proof.

    PROVIDER_CITATION is also not independently trusted at this
    stage. A citation must later be resolved/validated before it can
    become retrieval-backed evidence.
    """

    claim: str
    source_type: EvidenceSourceType
    source: str
    stance: EvidenceStance = EvidenceStance.NEUTRAL
    confidence: float = 1.0
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise ValueError(
                "Factual evidence claim cannot be empty."
            )

        if not isinstance(
            self.source_type,
            EvidenceSourceType,
        ):
            raise TypeError(
                "source_type must be an EvidenceSourceType."
            )

        if not self.source.strip():
            raise ValueError(
                "Factual evidence source cannot be empty."
            )

        if not isinstance(
            self.stance,
            EvidenceStance,
        ):
            raise TypeError(
                "stance must be an EvidenceStance."
            )

        confidence = float(
            self.confidence
        )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0.0 and 1.0."
            )

    @property
    def independently_verifiable(self) -> bool:
        """
        Whether this source type can currently establish factual
        support/contradiction without another evidence-resolution
        step.
        """

        return self.source_type in {
            EvidenceSourceType.RUNTIME_OBSERVATION,
            EvidenceSourceType.RETRIEVAL,
        }

    @property
    def independent_support(self) -> bool:
        return (
            self.independently_verifiable
            and self.stance
            == EvidenceStance.SUPPORTS
        )

    @property
    def independent_contradiction(self) -> bool:
        return (
            self.independently_verifiable
            and self.stance
            == EvidenceStance.CONTRADICTS
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "source_type": self.source_type.value,
            "source": self.source,
            "stance": self.stance.value,
            "confidence": float(
                self.confidence
            ),
            "independently_verifiable": (
                self.independently_verifiable
            ),
            "metadata": dict(
                self.metadata
            ),
        }


@dataclass
class ClaimEvidenceBundle:
    """
    Evidence collected for one exact factual claim.

    Claim matching is intentionally exact in this foundation.
    Cauvis does not silently canonicalize or replace named entities
    while evaluating evidence.
    """

    claim: str
    evidence: list[FactualEvidence] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise ValueError(
                "Evidence bundle claim cannot be empty."
            )

        initial = list(
            self.evidence
        )

        self.evidence = []

        for item in initial:
            self.add(
                item
            )

    def add(
        self,
        evidence: FactualEvidence,
    ) -> None:
        if not isinstance(
            evidence,
            FactualEvidence,
        ):
            raise TypeError(
                "evidence must be FactualEvidence."
            )

        if evidence.claim != self.claim:
            raise ValueError(
                "Evidence claim does not exactly match "
                "the bundle claim."
            )

        self.evidence.append(
            evidence
        )

    def count(self) -> int:
        return len(
            self.evidence
        )

    def evaluate(
        self,
    ) -> ClaimEvidenceStatus:
        """
        Evaluate the claim conservatively.

        Rules:

        - no evidence -> UNVERIFIED
        - only non-independent evidence -> INSUFFICIENT
        - independent support only -> SUPPORTED
        - independent contradiction only -> CONTRADICTED
        - independent support + contradiction -> INSUFFICIENT

        Conflicting evidence therefore fails closed instead of
        arbitrarily choosing one side.
        """

        if not self.evidence:
            return ClaimEvidenceStatus.UNVERIFIED

        has_support = any(
            item.independent_support
            for item in self.evidence
        )

        has_contradiction = any(
            item.independent_contradiction
            for item in self.evidence
        )

        if (
            has_support
            and has_contradiction
        ):
            return ClaimEvidenceStatus.INSUFFICIENT

        if has_contradiction:
            return ClaimEvidenceStatus.CONTRADICTED

        if has_support:
            return ClaimEvidenceStatus.SUPPORTED

        return ClaimEvidenceStatus.INSUFFICIENT

    @property
    def status(
        self,
    ) -> ClaimEvidenceStatus:
        return self.evaluate()

    @property
    def externally_supported(self) -> bool:
        return (
            self.status
            == ClaimEvidenceStatus.SUPPORTED
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "status": self.status.value,
            "externally_supported": (
                self.externally_supported
            ),
            "evidence_count": self.count(),
            "evidence": [
                item.to_dict()
                for item in self.evidence
            ],
        }
