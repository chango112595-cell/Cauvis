import json
import os
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from intelligence.models import ModelRequest, ModelResponse
from intelligence.router import ModelProvider


Transport = Callable[
    [
        str,
        dict[str, str],
        dict[str, Any],
        float,
    ],
    tuple[int, dict[str, Any]],
]


class OpenAIResponsesProvider(ModelProvider):
    """
    Real OpenAI provider using the Responses API.

    The provider uses Python's standard HTTP library so Cauvis
    does not require an external SDK for this stage.

    Credentials are read from OPENAI_API_KEY at request time.
    Credential values are never placed in ModelResponse metadata.
    """

    name = "openai"

    provider_types = {
        "cloud",
    }

    # Stage 3A only declares capabilities that this provider
    # implementation can actually support through the current
    # text-only ModelRequest interface.
    capabilities = {
        "chat",
        "code",
        "reasoning",
        "long_context",
        "complexity:low",
        "complexity:medium",
        "complexity:high",
    }

    credential_env_var = "OPENAI_API_KEY"
    credential_required = True
    enabled = True

    endpoint = (
        "https://api.openai.com/v1/responses"
    )

    def __init__(
        self,
        model: str,
        environment: Mapping[str, str] | None = None,
        transport: Transport | None = None,
        timeout_seconds: float = 60.0,
    ):
        model = str(model).strip()

        if not model:
            raise ValueError(
                "OpenAI provider model must not be empty."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        self.model = model

        self._environment = (
            environment
            if environment is not None
            else os.environ
        )

        self._transport = (
            transport
            or self._http_post_json
        )

        self.timeout_seconds = float(
            timeout_seconds
        )

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        """
        Send one real Responses API request.

        Router configuration enforcement should normally prevent
        this method from being called without credentials, but
        this provider also fails closed when used directly.
        """

        api_key = str(
            self._environment.get(
                self.credential_env_var,
                "",
            )
        ).strip()

        if not api_key:
            return ModelResponse(
                text="",
                model=self.model,
                provider=self.name,
                success=False,
                error=(
                    "OpenAI provider credential is not configured."
                ),
                metadata={
                    "endpoint": self.endpoint,
                    "credential_present": False,
                },
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "input": request.prompt,
        }

        if request.system_prompt:
            payload["instructions"] = (
                request.system_prompt
            )

        headers = {
            "Content-Type": "application/json",
            "Authorization": (
                f"Bearer {api_key}"
            ),
        }

        try:
            status_code, data = self._transport(
                self.endpoint,
                headers,
                payload,
                self.timeout_seconds,
            )

        except Exception as exc:
            return ModelResponse(
                text="",
                model=self.model,
                provider=self.name,
                success=False,
                error=(
                    "OpenAI transport failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
                metadata={
                    "endpoint": self.endpoint,
                    "credential_present": True,
                },
            )

        if not isinstance(data, dict):
            return ModelResponse(
                text="",
                model=self.model,
                provider=self.name,
                success=False,
                error=(
                    "OpenAI returned an invalid response payload."
                ),
                metadata={
                    "status_code": status_code,
                    "endpoint": self.endpoint,
                },
            )

        if not (
            200 <= status_code < 300
        ):
            return ModelResponse(
                text="",
                model=self.model,
                provider=self.name,
                success=False,
                error=self._extract_error(
                    data,
                    status_code,
                ),
                metadata={
                    "status_code": status_code,
                    "endpoint": self.endpoint,
                    "response_id": data.get("id"),
                },
            )

        text = self._extract_output_text(
            data
        )

        if not text:
            return ModelResponse(
                text="",
                model=self.model,
                provider=self.name,
                success=False,
                error=(
                    "OpenAI response contained no text output."
                ),
                metadata={
                    "status_code": status_code,
                    "endpoint": self.endpoint,
                    "response_id": data.get("id"),
                    "usage": data.get("usage"),
                },
            )

        return ModelResponse(
            text=text,
            model=str(
                data.get("model")
                or self.model
            ),
            provider=self.name,
            success=True,
            metadata={
                "status_code": status_code,
                "endpoint": self.endpoint,
                "response_id": data.get("id"),
                "usage": data.get("usage"),
            },
        )

    @staticmethod
    def _extract_output_text(
        data: dict[str, Any],
    ) -> str:
        """
        Collect text from all output_text content items.

        Do not assume text is located in the first output item.
        """

        pieces: list[str] = []

        output = data.get(
            "output",
            []
        )

        if isinstance(output, list):
            for item in output:
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                content = item.get(
                    "content",
                    []
                )

                if not isinstance(
                    content,
                    list,
                ):
                    continue

                for part in content:
                    if not isinstance(
                        part,
                        dict,
                    ):
                        continue

                    if (
                        part.get("type")
                        != "output_text"
                    ):
                        continue

                    text = part.get(
                        "text"
                    )

                    if isinstance(
                        text,
                        str,
                    ):
                        stripped = (
                            text.strip()
                        )

                        if stripped:
                            pieces.append(
                                stripped
                            )

        # Some compatible transports or SDK adapters may expose
        # an already-aggregated top-level output_text value.
        if not pieces:
            output_text = data.get(
                "output_text"
            )

            if isinstance(
                output_text,
                str,
            ):
                stripped = (
                    output_text.strip()
                )

                if stripped:
                    pieces.append(
                        stripped
                    )

        return "\n".join(
            pieces
        )

    @staticmethod
    def _extract_error(
        data: dict[str, Any],
        status_code: int,
    ) -> str:

        error = data.get(
            "error"
        )

        if isinstance(
            error,
            dict,
        ):
            message = error.get(
                "message"
            )

            if isinstance(
                message,
                str,
            ) and message.strip():
                return (
                    f"OpenAI API error "
                    f"({status_code}): "
                    f"{message.strip()}"
                )

        return (
            f"OpenAI API request failed "
            f"with HTTP status {status_code}."
        )

    @staticmethod
    def _http_post_json(
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> tuple[int, dict[str, Any]]:
        """
        Perform the real HTTPS request.

        HTTP and connection errors are converted into structured
        response data so AIModelRouter can record the real outcome.
        """

        request = Request(
            url=url,
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:

                status_code = int(
                    response.status
                )

                raw = response.read().decode(
                    "utf-8",
                    errors="replace",
                )

        except HTTPError as exc:
            status_code = int(
                exc.code
            )

            raw = exc.read().decode(
                "utf-8",
                errors="replace",
            )

        except URLError as exc:
            return (
                0,
                {
                    "error": {
                        "message": (
                            "Network error: "
                            f"{exc.reason}"
                        )
                    }
                },
            )

        try:
            data = json.loads(
                raw
            )

        except json.JSONDecodeError:
            data = {
                "error": {
                    "message": (
                        "OpenAI returned a non-JSON response."
                    )
                }
            }

        if not isinstance(
            data,
            dict,
        ):
            data = {
                "error": {
                    "message": (
                        "OpenAI returned an unexpected "
                        "JSON response type."
                    )
                }
            }

        return (
            status_code,
            data,
        )