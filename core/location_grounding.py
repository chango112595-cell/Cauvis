import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExplicitLocationAssertion:
    """
    A location value explicitly supplied by the user.

    This object preserves what the user actually stated.
    It does not geocode, resolve, normalize, or independently
    verify the location.
    """

    value: str
    source_text: str
    confidence: float
    reason: str


class UserLocationExtractor:
    """
    Conservative deterministic extractor for explicit
    self-location statements.

    Beta 1.2E principle:

        User-supplied named locations must not be silently
        replaced by model-generated alternatives.

    This extractor intentionally does NOT:

    - geocode
    - infer a state from a city
    - infer a city from a state
    - resolve ambiguous place names
    - use model output as evidence
    - treat destinations as the user's location
    - treat workplace/school/travel destinations as residence

    Only strong first-person location declarations are accepted.
    """

    _PATTERNS = (
        re.compile(
            r"""
            ^\s*
            i\s+live\s+in
            \s+
            (?P<location>.+?)
            \s*$
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
        re.compile(
            r"""
            ^\s*
            (?:i\s+am|i['’]m)
            \s+located\s+in
            \s+
            (?P<location>.+?)
            \s*$
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
        re.compile(
            r"""
            ^\s*
            (?:i\s+am|i['’]m)
            \s+currently\s+in
            \s+
            (?P<location>.+?)
            \s*$
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
        re.compile(
            r"""
            ^\s*
            my\s+(?:current\s+)?location\s+is
            \s+
            (?P<location>.+?)
            \s*$
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    )

    _REJECTED_LOCATION_VALUES = {
        "",
        "here",
        "there",
        "home",
        "somewhere",
        "nowhere",
        "unknown",
    }

    def extract(
        self,
        text: str,
    ) -> ExplicitLocationAssertion | None:
        """
        Extract an explicit user location declaration.

        Returns None when the text is not a sufficiently strong
        declaration of the user's own location.
        """

        source_text = str(
            text
        ).strip()

        if not source_text:
            return None

        candidate_text = self._first_sentence(
            source_text
        )

        for pattern in self._PATTERNS:
            match = pattern.match(
                candidate_text
            )

            if match is None:
                continue

            location = self._clean_location(
                match.group(
                    "location"
                )
            )

            if not self._is_usable_location(
                location
            ):
                return None

            return ExplicitLocationAssertion(
                value=location,
                source_text=source_text,
                confidence=1.0,
                reason=(
                    "explicit_first_person_location_statement"
                ),
            )

        return None

    @staticmethod
    def _first_sentence(
        text: str,
    ) -> str:
        """
        Use only the first sentence-like unit.

        This allows:

            I live in Columbus, Indiana. How far is Indianapolis?

        while preventing unrelated trailing instructions from
        becoming part of the stored location.
        """

        match = re.match(
            r"^(.*?)(?:[!?]|\.(?=\s|$)|$)",
            text,
            re.DOTALL,
        )

        if match is None:
            return text.strip()

        return match.group(
            1
        ).strip()

    @classmethod
    def _is_usable_location(
        cls,
        value: str,
    ) -> bool:
        normalized = value.casefold()

        if (
            normalized
            in cls._REJECTED_LOCATION_VALUES
        ):
            return False

        if len(
            value
        ) < 2:
            return False

        return True

    @staticmethod
    def _clean_location(
        value: str,
    ) -> str:
        """
        Preserve the user's named entity while removing only
        surrounding whitespace and terminal punctuation.

        No city/state substitution or canonicalization occurs.
        """

        value = " ".join(
            str(
                value
            ).strip().split()
        )

        value = value.rstrip(
            " \t\r\n.,!?;:"
        )

        return value.strip()
