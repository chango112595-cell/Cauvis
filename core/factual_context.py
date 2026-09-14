from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FactProvenance(str, Enum):
    """
    Describes where a factual value came from.

    USER_ASSERTED:
        Explicitly stated by the user.

    RUNTIME_VERIFIED:
        Directly established by the running Cauvis system.

    RETRIEVAL_VERIFIED:
        Established by a connected external/retrieval source.

    INFERRED:
        Derived from available information but not directly proven.

    UNVERIFIED:
        No trustworthy supporting evidence is available.
    """

    USER_ASSERTED = "user_asserted"
    RUNTIME_VERIFIED = "runtime_verified"
    RETRIEVAL_VERIFIED = "retrieval_verified"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class GroundedFact:
    """
    One factual value with explicit provenance.

    A GroundedFact records where a value came from.
    It does not automatically mean the value has been
    independently verified.
    """

    key: str
    value: str
    provenance: FactProvenance
    source: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "provenance": self.provenance.value,
            "source": self.source,
            "confidence": self.confidence,
            "metadata": dict(
                self.metadata
            ),
        }


class FactualContextRuntime:
    """
    Session-scoped factual context with provenance.

    This runtime is intentionally separate from normal
    ConversationRuntime transcript history.

    Conversation history answers:

        "What was said?"

    FactualContextRuntime answers:

        "What factual value is currently grounded, and where
        did that value come from?"

    Beta 1.2E replacement rule:

    A USER_ASSERTED fact must not be silently replaced by an
    inferred, unverified, runtime, or retrieval value.

    If the user explicitly supplies a new value for the same
    key, the newer USER_ASSERTED value may replace the older
    USER_ASSERTED value.
    """

    _PROVENANCE_PRIORITY = {
        FactProvenance.UNVERIFIED: 0,
        FactProvenance.INFERRED: 1,
        FactProvenance.USER_ASSERTED: 2,
        FactProvenance.RETRIEVAL_VERIFIED: 3,
        FactProvenance.RUNTIME_VERIFIED: 4,
    }

    def __init__(
        self,
    ):
        self._sessions: dict[
            str,
            dict[str, GroundedFact],
        ] = {}

    def set_fact(
        self,
        session_id: str,
        key: str,
        value: str,
        provenance: FactProvenance,
        source: str,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> GroundedFact:
        """
        Store a grounded fact if replacement policy permits it.

        Returns the fact that remains authoritative in the
        session after the operation.

        If replacement is blocked, the existing fact is returned
        unchanged.
        """

        session_id = self._normalize_session_id(
            session_id
        )

        key = self._normalize_key(
            key
        )

        value = str(
            value
        ).strip()

        if not value:
            raise ValueError(
                "Fact value must not be empty."
            )

        if not isinstance(
            provenance,
            FactProvenance,
        ):
            raise TypeError(
                "provenance must be a FactProvenance."
            )

        source = str(
            source
        ).strip()

        if not source:
            raise ValueError(
                "Fact source must not be empty."
            )

        confidence = float(
            confidence
        )

        if not (
            0.0
            <= confidence
            <= 1.0
        ):
            raise ValueError(
                "Fact confidence must be between "
                "0.0 and 1.0."
            )

        session = self._sessions.setdefault(
            session_id,
            {},
        )

        existing = session.get(
            key
        )

        if (
            existing is not None
            and not self._can_replace(
                existing,
                provenance,
            )
        ):
            return existing

        fact = GroundedFact(
            key=key,
            value=value,
            provenance=provenance,
            source=source,
            confidence=confidence,
            metadata=dict(
                metadata or {}
            ),
        )

        session[
            key
        ] = fact

        return fact

    def set_user_fact(
        self,
        session_id: str,
        key: str,
        value: str,
        source: str = "current-session user input",
        metadata: dict[str, Any] | None = None,
    ) -> GroundedFact:
        """
        Store an explicitly user-supplied factual value.
        """

        return self.set_fact(
            session_id=session_id,
            key=key,
            value=value,
            provenance=(
                FactProvenance.USER_ASSERTED
            ),
            source=source,
            confidence=1.0,
            metadata=metadata,
        )

    def get(
        self,
        session_id: str,
        key: str,
    ) -> GroundedFact | None:
        session_id = self._normalize_session_id(
            session_id
        )

        key = self._normalize_key(
            key
        )

        return self._sessions.get(
            session_id,
            {},
        ).get(
            key
        )

    def facts(
        self,
        session_id: str,
    ) -> tuple[GroundedFact, ...]:
        session_id = self._normalize_session_id(
            session_id
        )

        session = self._sessions.get(
            session_id,
            {},
        )

        return tuple(
            session[key]
            for key in sorted(
                session
            )
        )

    def fact_count(
        self,
        session_id: str,
    ) -> int:
        return len(
            self.facts(
                session_id
            )
        )

    def clear(
        self,
        session_id: str,
    ) -> None:
        session_id = self._normalize_session_id(
            session_id
        )

        self._sessions.pop(
            session_id,
            None,
        )

    def clear_all(
        self,
    ) -> None:
        self._sessions.clear()

    def render_context(
        self,
        session_id: str,
    ) -> str:
        """
        Render factual context with explicit provenance.

        USER_ASSERTED means the user explicitly supplied the
        value. It does not mean Cauvis independently verified it.

        The rendered form is intended for model grounding later
        in Beta 1.2E.
        """

        facts = self.facts(
            session_id
        )

        if not facts:
            return ""

        lines = [
            (
                "The following session facts have explicit "
                "provenance. Preserve USER_ASSERTED values "
                "exactly unless the current user explicitly "
                "corrects them."
            ),
            (
                "USER_ASSERTED means the user stated the value; "
                "it is not an independent external verification."
            ),
        ]

        for fact in facts:
            lines.append(
                "- "
                + fact.key
                + "="
                + fact.value
                + "; provenance="
                + fact.provenance.value
                + "; source="
                + fact.source
                + "; confidence="
                + f"{fact.confidence:.2f}"
            )

        return "\n".join(
            lines
        )

    @classmethod
    def _can_replace(
        cls,
        existing: GroundedFact,
        incoming: FactProvenance,
    ) -> bool:
        """
        Decide whether an incoming fact may replace an existing
        factual value.

        USER_ASSERTED values receive special protection.

        Only another explicit USER_ASSERTED value may replace a
        USER_ASSERTED value automatically.
        """

        if (
            existing.provenance
            == FactProvenance.USER_ASSERTED
        ):
            return (
                incoming
                == FactProvenance.USER_ASSERTED
            )

        if (
            incoming
            == existing.provenance
        ):
            return True

        return (
            cls._PROVENANCE_PRIORITY[
                incoming
            ]
            >= cls._PROVENANCE_PRIORITY[
                existing.provenance
            ]
        )

    @staticmethod
    def _normalize_session_id(
        session_id: str,
    ) -> str:
        session_id = str(
            session_id
        ).strip()

        if not session_id:
            raise ValueError(
                "session_id must not be empty."
            )

        return session_id

    @staticmethod
    def _normalize_key(
        key: str,
    ) -> str:
        key = str(
            key
        ).strip()

        if not key:
            raise ValueError(
                "Fact key must not be empty."
            )

        return key
