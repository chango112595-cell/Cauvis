import json
import re
import time
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import (
    parse_qs,
    quote,
    unquote,
    urlencode,
    urlparse,
)
from urllib.request import Request, urlopen


Transport = Callable[
    [str, dict[str, str], float],
    tuple[int, str],
]


@dataclass(frozen=True)
class RetrievalDocument:
    title: str
    url: str
    snippet: str
    source_provider: str = "web"

    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source_provider": self.source_provider,
        }


@dataclass
class RetrievalResult:
    query: str
    success: bool
    provider: str
    documents: list[RetrievalDocument] = field(default_factory=list)
    error: str | None = None
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "success": self.success,
            "provider": self.provider,
            "documents": [
                item.to_dict()
                for item in self.documents
            ],
            "source_count": len(self.documents),
            "error": self.error,
            "elapsed_ms": float(self.elapsed_ms),
        }


class _DuckDuckGoHTMLParser(HTMLParser):
    """
    Small parser for DuckDuckGo's HTML results page.

    It deliberately extracts only result titles, result URLs,
    and result snippets.
    """

    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.snippets: list[str] = []
        self._mode: str | None = None
        self._tag: str | None = None
        self._href = ""
        self._buffer: list[str] = []

    @staticmethod
    def _class_tokens(attrs) -> set[str]:
        values = dict(attrs)
        return set(
            str(values.get("class", "")).split()
        )

    def handle_starttag(self, tag, attrs):
        classes = self._class_tokens(attrs)
        values = dict(attrs)

        if tag == "a" and "result__a" in classes:
            self._mode = "title"
            self._tag = tag
            self._href = str(values.get("href", ""))
            self._buffer = []
            return

        if "result__snippet" in classes:
            self._mode = "snippet"
            self._tag = tag
            self._buffer = []

    def handle_data(self, data):
        if self._mode is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if self._mode is None:
            return

        if tag != self._tag:
            return

        text = " ".join(
            " ".join(self._buffer).split()
        ).strip()

        if self._mode == "title":
            self.links.append(
                (self._href, text)
            )

        elif self._mode == "snippet":
            self.snippets.append(text)

        self._mode = None
        self._tag = None
        self._href = ""
        self._buffer = []


class WebRetrievalRuntime:
    """
    Read-only web retrieval runtime for Cauvis.

    Primary provider:
        DuckDuckGo HTML search.

    Fallback:
        Wikipedia search + introductory extracts.

    This runtime performs retrieval only. It does not click,
    submit forms, authenticate, purchase, upload, download,
    or mutate remote websites.
    """

    def __init__(
        self,
        timeout_seconds: float = 12.0,
        max_results: int = 5,
        transport: Transport | None = None,
    ):
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        if max_results <= 0:
            raise ValueError(
                "max_results must be greater than zero."
            )

        self.timeout_seconds = float(timeout_seconds)
        self.max_results = int(max_results)
        self._transport = (
            transport
            or self._http_get_text
        )

        self.last_attempted = False
        self.last_success = False
        self.last_error: str | None = None
        self.last_provider: str | None = None
        self.last_elapsed_ms: float | None = None

    @property
    def available(self) -> bool:
        return bool(self.last_success)

    def search(
        self,
        query: str,
    ) -> RetrievalResult:
        query = " ".join(
            str(query).strip().split()
        )

        if not query:
            return RetrievalResult(
                query="",
                success=False,
                provider="none",
                error="Retrieval query is empty.",
            )

        started = time.perf_counter()
        self.last_attempted = True

        errors = []

        for provider_name, handler in (
            (
                "duckduckgo_html",
                self._search_duckduckgo,
            ),
            (
                "wikipedia",
                self._search_wikipedia,
            ),
        ):
            try:
                documents = handler(query)

                if documents:
                    elapsed_ms = (
                        time.perf_counter() - started
                    ) * 1000.0

                    self.last_success = True
                    self.last_error = None
                    self.last_provider = provider_name
                    self.last_elapsed_ms = elapsed_ms

                    return RetrievalResult(
                        query=query,
                        success=True,
                        provider=provider_name,
                        documents=documents[
                            : self.max_results
                        ],
                        elapsed_ms=round(
                            elapsed_ms,
                            3,
                        ),
                    )

                errors.append(
                    provider_name
                    + ": no search results"
                )

            except Exception as exc:
                errors.append(
                    provider_name
                    + ": "
                    + type(exc).__name__
                    + ": "
                    + str(exc)
                )

        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000.0

        error = "; ".join(errors)

        self.last_success = False
        self.last_error = error
        self.last_provider = None
        self.last_elapsed_ms = elapsed_ms

        return RetrievalResult(
            query=query,
            success=False,
            provider="none",
            documents=[],
            error=error or "No retrieval provider succeeded.",
            elapsed_ms=round(
                elapsed_ms,
                3,
            ),
        )

    def _search_duckduckgo(
        self,
        query: str,
    ) -> list[RetrievalDocument]:
        url = (
            "https://html.duckduckgo.com/html/?"
            + urlencode(
                {
                    "q": query,
                }
            )
        )

        status, body = self._transport(
            url,
            {
                "User-Agent": (
                    "Mozilla/5.0 Cauvis/1.0 "
                    "read-only-retrieval"
                ),
                "Accept": "text/html,application/xhtml+xml",
            },
            self.timeout_seconds,
        )

        if status < 200 or status >= 300:
            raise RuntimeError(
                "DuckDuckGo returned HTTP "
                + str(status)
            )

        parser = _DuckDuckGoHTMLParser()
        parser.feed(body)

        documents = []

        for index, (
            href,
            title,
        ) in enumerate(parser.links):
            normalized_url = (
                self._normalize_duckduckgo_url(
                    href
                )
            )

            if not normalized_url:
                continue

            snippet = (
                parser.snippets[index]
                if index < len(parser.snippets)
                else ""
            )

            documents.append(
                RetrievalDocument(
                    title=(
                        title
                        or normalized_url
                    ),
                    url=normalized_url,
                    snippet=snippet,
                    source_provider=(
                        "duckduckgo_html"
                    ),
                )
            )

            if len(documents) >= self.max_results:
                break

        return documents

    def _search_wikipedia(
        self,
        query: str,
    ) -> list[RetrievalDocument]:
        search_url = (
            "https://en.wikipedia.org/w/api.php?"
            + urlencode(
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": self.max_results,
                    "format": "json",
                    "utf8": 1,
                }
            )
        )

        status, body = self._transport(
            search_url,
            {
                "User-Agent": (
                    "Cauvis/1.0 read-only-retrieval"
                ),
                "Accept": "application/json",
            },
            self.timeout_seconds,
        )

        if status < 200 or status >= 300:
            raise RuntimeError(
                "Wikipedia search returned HTTP "
                + str(status)
            )

        payload = json.loads(body)
        results = (
            payload
            .get("query", {})
            .get("search", [])
        )

        if not results:
            return []

        titles = [
            str(item.get("title", "")).strip()
            for item in results
            if str(item.get("title", "")).strip()
        ]

        extracts: dict[str, str] = {}

        if titles:
            extract_url = (
                "https://en.wikipedia.org/w/api.php?"
                + urlencode(
                    {
                        "action": "query",
                        "prop": "extracts",
                        "exintro": 1,
                        "explaintext": 1,
                        "redirects": 1,
                        "titles": "|".join(titles),
                        "format": "json",
                        "utf8": 1,
                    }
                )
            )

            extract_status, extract_body = (
                self._transport(
                    extract_url,
                    {
                        "User-Agent": (
                            "Cauvis/1.0 "
                            "read-only-retrieval"
                        ),
                        "Accept": "application/json",
                    },
                    self.timeout_seconds,
                )
            )

            if (
                extract_status >= 200
                and extract_status < 300
            ):
                extract_payload = json.loads(
                    extract_body
                )

                pages = (
                    extract_payload
                    .get("query", {})
                    .get("pages", {})
                )

                for page in pages.values():
                    page_title = str(
                        page.get(
                            "title",
                            "",
                        )
                    ).strip()

                    extract = " ".join(
                        str(
                            page.get(
                                "extract",
                                "",
                            )
                        ).split()
                    )

                    if page_title:
                        extracts[
                            page_title
                        ] = extract

        documents = []

        for item in results:
            title = str(
                item.get(
                    "title",
                    "",
                )
            ).strip()

            if not title:
                continue

            raw_snippet = str(
                item.get(
                    "snippet",
                    "",
                )
            )

            search_snippet = (
                self._strip_html(
                    raw_snippet
                )
            )

            snippet = (
                extracts.get(
                    title,
                    "",
                )
                or search_snippet
            )

            if len(snippet) > 1200:
                snippet = (
                    snippet[:1200].rstrip()
                    + "..."
                )

            documents.append(
                RetrievalDocument(
                    title=title,
                    url=(
                        "https://en.wikipedia.org/wiki/"
                        + quote(
                            title.replace(
                                " ",
                                "_",
                            ),
                            safe="()_-'",
                        )
                    ),
                    snippet=snippet,
                    source_provider="wikipedia",
                )
            )

            if len(documents) >= self.max_results:
                break

        return documents

    @staticmethod
    def _normalize_duckduckgo_url(
        href: str,
    ) -> str:
        href = unescape(
            str(href).strip()
        )

        if not href:
            return ""

        if href.startswith("//"):
            href = "https:" + href

        parsed = urlparse(href)
        query = parse_qs(parsed.query)

        if "uddg" in query:
            return unquote(
                query["uddg"][0]
            )

        if parsed.scheme in {
            "http",
            "https",
        }:
            return href

        return ""

    @staticmethod
    def _strip_html(
        value: str,
    ) -> str:
        value = re.sub(
            r"<[^>]+>",
            " ",
            value,
        )

        return " ".join(
            unescape(value).split()
        )

    @staticmethod
    def _http_get_text(
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, str]:
        request = Request(
            url=url,
            headers=headers,
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=timeout,
            ) as response:
                status = int(
                    getattr(
                        response,
                        "status",
                        200,
                    )
                )

                body = response.read().decode(
                    "utf-8",
                    errors="replace",
                )

                return status, body

        except HTTPError as exc:
            body = exc.read().decode(
                "utf-8",
                errors="replace",
            )

            return int(exc.code), body

        except URLError as exc:
            raise RuntimeError(
                "Network retrieval failed: "
                + str(exc.reason)
            ) from exc
