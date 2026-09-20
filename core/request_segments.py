from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RequestSegment:
    """One conservative deterministic part of a user request."""

    index: int
    text: str


class RequestSegmenter:
    """
    Split clearly multi-part requests without semantic planning.

    Ordinary conjunctions remain intact unless the text after the
    boundary begins like another explicit request.
    """

    _REQUEST_STARTERS = (
        "who", "what", "which", "when", "where", "why", "how",
        "can", "could", "would", "will", "should", "is", "are",
        "do", "does", "did", "explain", "tell", "show", "give",
        "search", "browse", "look", "check", "verify", "find",
        "open", "close", "run", "launch", "start", "stop",
        "delete", "move", "copy", "rename", "send", "click",
        "type", "install", "upload", "download", "remind",
        "write", "draft", "design", "create", "generate", "please",
    )

    _STARTER_PATTERN = (
        r"(?:"
        + "|".join(re.escape(value) for value in _REQUEST_STARTERS)
        + r")\b"
    )

    _STRONG_BOUNDARY = re.compile(
        r"(?<=\?)\s+|;\s*|\r?\n+",
        re.IGNORECASE,
    )

    _SENTENCE_BOUNDARY = re.compile(
        r"(?<=[.!])\s+(?=" + _STARTER_PATTERN + r")",
        re.IGNORECASE,
    )

    _AND_BOUNDARY = re.compile(
        r"(?:,\s*|\s+)and\s+(?=" + _STARTER_PATTERN + r")",
        re.IGNORECASE,
    )

    _COMMA_BOUNDARY = re.compile(
        r",\s+(?=" + _STARTER_PATTERN + r")",
        re.IGNORECASE,
    )

    def split(self, user_input: str) -> tuple[RequestSegment, ...]:
        text = str(user_input if user_input is not None else "").strip()

        if not text:
            return ()

        pieces = [text]

        for pattern in (
            self._STRONG_BOUNDARY,
            self._SENTENCE_BOUNDARY,
            self._AND_BOUNDARY,
            self._COMMA_BOUNDARY,
        ):
            next_pieces = []
            for piece in pieces:
                next_pieces.extend(pattern.split(piece))
            pieces = next_pieces

        cleaned = []
        for piece in pieces:
            value = str(piece).strip(" \t\r\n,;")
            if value:
                cleaned.append(value)

        return tuple(
            RequestSegment(index=index, text=value)
            for index, value in enumerate(cleaned)
        )
