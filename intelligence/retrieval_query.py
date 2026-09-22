from dataclasses import dataclass
import re
from urllib.parse import urlparse


@dataclass(frozen=True)
class RetrievalQueryPlan:
    original_query: str
    search_query: str
    wikipedia_query: str
    significant_terms: tuple[str, ...]
    preferred_domains: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "original_query": self.original_query,
            "search_query": self.search_query,
            "wikipedia_query": self.wikipedia_query,
            "significant_terms": list(self.significant_terms),
            "preferred_domains": list(self.preferred_domains),
        }


class RetrievalQueryPlanner:
    """Deterministic cleanup and relevance planning for web retrieval."""

    _LEADING_PATTERNS = (
        r"^(?:please\s+)?search\s+the\s+web\s+for\s+",
        r"^(?:please\s+)?search\s+online\s+for\s+",
        r"^(?:please\s+)?search\s+the\s+internet\s+for\s+",
        r"^(?:please\s+)?browse\s+the\s+web\s+for\s+",
        r"^(?:please\s+)?look\s+online\s+for\s+",
        r"^(?:please\s+)?look\s+up\s+",
        r"^(?:please\s+)?find\s+online\s+",
        r"^(?:please\s+)?check\s+online\s+",
        r"^(?:can|could|would|will)\s+you\s+verify\s+(?:that\s+)?",
        r"^(?:can|could|would|will)\s+you\s+confirm\s+(?:that\s+)?",
        r"^(?:please\s+)?verify\s+(?:that\s+)?",
        r"^(?:please\s+)?confirm\s+(?:that\s+)?",
    )

    _STOP_WORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by",
        "can", "could", "do", "does", "for", "from", "give",
        "how", "i", "in", "is", "it", "me", "of", "on",
        "please", "right", "search", "show", "that", "the",
        "this", "to", "up", "web", "what", "when", "where",
        "which", "who", "why", "will", "would", "you",
        "online", "internet", "verify", "confirm",
        "current", "latest", "today", "now",
    }

    _DOMAIN_HINTS = (
        ({"python"}, "python.org"),
        ({"microsoft"}, "microsoft.com"),
        ({"openai"}, "openai.com"),
        ({"github"}, "github.com"),
        ({"ollama"}, "ollama.com"),
    )

    @classmethod
    def plan(cls, query: str) -> RetrievalQueryPlan:
        original = " ".join(str(query).strip().split())
        cleaned = original

        for pattern in cls._LEADING_PATTERNS:
            updated = re.sub(
                pattern,
                "",
                cleaned,
                count=1,
                flags=re.IGNORECASE,
            )
            if updated != cleaned:
                cleaned = updated
                break

        cleaned = cleaned.strip(" \t\r\n?.!,;:")
        if not cleaned:
            cleaned = original.strip()

        tokens = tuple(
            re.findall(
                r"[A-Za-z0-9][A-Za-z0-9.+#_-]*",
                cleaned.lower(),
            )
        )

        significant = []
        for token in tokens:
            if token in cls._STOP_WORDS:
                continue
            if len(token) <= 1 and not token.isdigit():
                continue
            if token not in significant:
                significant.append(token)

        token_set = set(significant)
        preferred_domains = []

        for required_terms, domain in cls._DOMAIN_HINTS:
            if required_terms.issubset(token_set):
                preferred_domains.append(domain)

        wiki_terms = list(significant)
        lower_cleaned = cleaned.lower()

        for word in (
            "release",
            "version",
            "ceo",
            "president",
            "weather",
            "price",
            "status",
        ):
            if word in lower_cleaned and word not in wiki_terms:
                wiki_terms.append(word)

        wikipedia_query = " ".join(wiki_terms[:8]).strip() or cleaned

        search_query = cleaned
        if preferred_domains:
            search_query = cleaned + " site:" + preferred_domains[0]

        return RetrievalQueryPlan(
            original_query=original,
            search_query=search_query,
            wikipedia_query=wikipedia_query,
            significant_terms=tuple(significant),
            preferred_domains=tuple(preferred_domains),
        )

    @classmethod
    def relevance_score(
        cls,
        plan: RetrievalQueryPlan,
        *,
        title: str,
        url: str,
        snippet: str,
    ) -> float:
        title_l = str(title).lower()
        snippet_l = str(snippet).lower()
        url_l = str(url).lower()

        score = 0.0

        for term in plan.significant_terms:
            if term in title_l:
                score += 4.0
            if term in snippet_l:
                score += 1.0
            if term in url_l:
                score += 1.5

        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            host = ""

        for domain in plan.preferred_domains:
            if host == domain or host.endswith("." + domain):
                score += 8.0

        return score

    @classmethod
    def rank_documents(
        cls,
        plan: RetrievalQueryPlan,
        documents,
        *,
        max_results: int,
    ):
        scored = []

        for index, document in enumerate(documents):
            score = cls.relevance_score(
                plan,
                title=document.title,
                url=document.url,
                snippet=document.snippet,
            )

            if plan.significant_terms and score <= 0:
                continue

            scored.append((-score, index, document))

        scored.sort(key=lambda item: (item[0], item[1]))

        return [
            item[2]
            for item in scored[:max_results]
        ]
