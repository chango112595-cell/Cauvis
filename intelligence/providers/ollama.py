import json
from typing import Any, Callable
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


class OllamaProvider(ModelProvider):
    """
    Real local Ollama provider for Cauvis.

    This provider communicates with a locally running Ollama
    service through its HTTP API.

    No cloud account, API key, or external authentication is
    required for the default localhost configuration.
    """

    name = "ollama"

    provider_types = {
        "local",
    }

    capabilities = {
        "chat",
        "code",
        "reasoning",
        "complexity:low",
        "complexity:medium",
        "complexity:high",
    }

    credential_env_var = None
    credential_required = False
    enabled = True

    default_base_url = (
        "http://127.0.0.1:11434"
    )

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        transport: Transport | None = None,
        timeout_seconds: float = 120.0,
        keep_alive: str | int | float | None = None,
    ):
        model = str(model).strip()

        if not model:
            raise ValueError(
                "Ollama provider model must not be empty."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        selected_base_url = str(
            base_url
            or self.default_base_url
        ).strip()

        if not selected_base_url:
            raise ValueError(
                "Ollama provider base_url must not be empty."
            )

        self.model = model

        self.base_url = (
            selected_base_url.rstrip("/")
        )

        self.endpoint = (
            f"{self.base_url}/api/chat"
        )

        self._transport = (
            transport
            or self._http_post_json
        )

        self.timeout_seconds = float(
            timeout_seconds
        )

        if isinstance(
            keep_alive,
            bool,
        ):
            raise ValueError(
                "Ollama keep_alive must be a duration string, "
                "number, or None."
            )

        if isinstance(
            keep_alive,
            str,
        ):
            keep_alive = keep_alive.strip()

            if not keep_alive:
                keep_alive = None

        elif keep_alive is not None:
            keep_alive = (
                float(keep_alive)
                if isinstance(keep_alive, float)
                else int(keep_alive)
            )

        self.keep_alive = keep_alive

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        """
        Send one non-streaming chat request to local Ollama.
        """

        messages: list[dict[str, str]] = []

        if request.system_prompt:
            system_prompt = str(
                request.system_prompt
            ).strip()

            if system_prompt:
                messages.append(
                    {
                        "role": "system",
                        "content": system_prompt,
                    }
                )

        messages.append(
            {
                "role": "user",
                "content": request.prompt,
            }
        )

        options: dict[str, Any] = {
            "temperature": float(
                request.temperature
            ),
        }

        if request.max_tokens is not None:
            max_tokens = int(
                request.max_tokens
            )

            if max_tokens <= 0:
                return ModelResponse(
                    text="",
                    model=self.model,
                    provider=self.name,
                    success=False,
                    error=(
                        "Ollama max_tokens must be greater "
                        "than zero when provided."
                    ),
                    metadata={
                        "endpoint": self.endpoint,
                    },
                )

            options["num_predict"] = (
                max_tokens
            )

        else:
            # Functional Core default: bound local generation so
            # short everyday turns cannot run unbounded.
            options["num_predict"] = 256

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }

        if self.keep_alive is not None:
            payload["keep_alive"] = (
                self.keep_alive
            )

        headers = {
            "Content-Type": "application/json",
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
                    "Ollama transport failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
                metadata={
                    "endpoint": self.endpoint,
                },
            )

        if not isinstance(data, dict):
            return ModelResponse(
                text="",
                model=self.model,
                provider=self.name,
                success=False,
                error=(
                    "Ollama returned an invalid "
                    "response payload."
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
                },
            )

        text = self._extract_message_text(
            data
        )

        if not text:
            return ModelResponse(
                text="",
                model=self.model,
                provider=self.name,
                success=False,
                error=(
                    "Ollama response contained "
                    "no assistant text."
                ),
                metadata=self._metadata(
                    data,
                    status_code,
                ),
            )

        return ModelResponse(
            text=text,
            model=str(
                data.get("model")
                or self.model
            ),
            provider=self.name,
            success=True,
            metadata=self._metadata(
                data,
                status_code,
            ),
        )

    @staticmethod
    def _extract_message_text(
        data: dict[str, Any],
    ) -> str:
        message = data.get(
            "message"
        )

        if not isinstance(
            message,
            dict,
        ):
            return ""

        content = message.get(
            "content"
        )

        if not isinstance(
            content,
            str,
        ):
            return ""

        return content.strip()

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
            str,
        ) and error.strip():
            return (
                f"Ollama API error "
                f"({status_code}): "
                f"{error.strip()}"
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
                    f"Ollama API error "
                    f"({status_code}): "
                    f"{message.strip()}"
                )

        return (
            "Ollama API request failed "
            f"with HTTP status {status_code}."
        )

    def _metadata(
        self,
        data: dict[str, Any],
        status_code: int,
    ) -> dict[str, Any]:
        return {
            "status_code": status_code,
            "endpoint": self.endpoint,
            "done": data.get("done"),
            "done_reason": data.get(
                "done_reason"
            ),
            "total_duration": data.get(
                "total_duration"
            ),
            "load_duration": data.get(
                "load_duration"
            ),
            "prompt_eval_count": data.get(
                "prompt_eval_count"
            ),
            "prompt_eval_cached_count": (
                data.get(
                    "prompt_eval_cached_count"
                )
            ),
            "eval_count": data.get(
                "eval_count"
            ),
            "eval_duration": data.get(
                "eval_duration"
            ),
        }

    @staticmethod
    def _http_post_json(
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> tuple[int, dict[str, Any]]:
        """
        Perform one real local Ollama HTTP request.

        HTTP and connection failures are converted into
        structured data so Cauvis can record the real outcome.
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
                    "error": (
                        "Local Ollama connection error: "
                        f"{exc.reason}"
                    )
                },
            )

        try:
            data = json.loads(
                raw
            )

        except json.JSONDecodeError:
            data = {
                "error": (
                    "Ollama returned a non-JSON response."
                )
            }

        if not isinstance(
            data,
            dict,
        ):
            data = {
                "error": (
                    "Ollama returned an unexpected "
                    "JSON response type."
                )
            }

        return (
            status_code,
            data,
        )
