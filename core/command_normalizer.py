import re


class CommandNormalizer:
    """
    Normalize routing text without changing the user's stored message.

    Removes Cauvis wake-name/polite command wrappers and fixes only a
    small set of command-keyword typos. It does not rewrite content.
    """

    _PREFIXES = (
        r"^\s*hey\s+cauvis[\s,:-]+",
        r"^\s*okay\s+cauvis[\s,:-]+",
        r"^\s*ok\s+cauvis[\s,:-]+",
        r"^\s*cauvis[\s,:-]+",
    )

    _REQUEST_WRAPPERS = (
        r"^\s*i\s+need\s+you\s+to\s+",
        r"^\s*i\s+want\s+you\s+to\s+",
        r"^\s*i(?:'d| would)\s+like\s+you\s+to\s+",
        r"^\s*please\s+",
    )

    _SAFE_TYPO_FIXES = (
        (r"\bcalle\b", "called"),
        (r"\bnmaed\b", "named"),
        (r"\btect\b", "text"),
        (r"\btxtt\b", "text"),
        (r"\bopne\b", "open"),
        (r"\bserach\b", "search"),
        (r"\bcreat\b", "create"),
    )

    @classmethod
    def routing_text(cls, text: str) -> str:
        value = " ".join(str(text).strip().split())

        for pattern in cls._PREFIXES:
            updated = re.sub(
                pattern,
                "",
                value,
                count=1,
                flags=re.IGNORECASE,
            )
            if updated != value:
                value = updated
                break

        for pattern in cls._REQUEST_WRAPPERS:
            updated = re.sub(
                pattern,
                "",
                value,
                count=1,
                flags=re.IGNORECASE,
            )
            if updated != value:
                value = updated
                break

        for pattern, replacement in cls._SAFE_TYPO_FIXES:
            value = re.sub(
                pattern,
                replacement,
                value,
                flags=re.IGNORECASE,
            )

        return value.strip()
