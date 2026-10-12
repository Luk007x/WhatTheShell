# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenAI-compatible chat completions over urllib (local servers and OpenAI)."""

from whattheshell.ai.protocol import Prompt

from .http import get_json, post_json


class OpenAICompatProvider:
    """`/chat/completions` client; sends a bearer token only if `api_key` is set."""

    name = "openai"

    def __init__(self, base_url: str, model: str, timeout: float, api_key: str | None) -> None:
        self._base = base_url.rstrip("/")
        self._url = self._base + "/chat/completions"
        self._model = model
        self._timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def complete(self, prompt: Prompt) -> str:
        """Send `prompt`, return `choices[0].message.content`."""
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "max_tokens": prompt.max_tokens,
            "temperature": 0.2,
            "stream": False,
        }
        answer = post_json(self._url, body, self._headers, self._timeout)
        try:
            return str(answer["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("Unerwartete Antwortform des Servers") from None

    def list_models(self) -> list[str]:
        """GET ``{base_url}/models``, return ``data[].id``.

        Raises:
            RuntimeError: HTTP error, unreachable host, or unexpected answer.
        """
        answer = get_json(self._base + "/models", self._headers, self._timeout)
        try:
            return [str(model["id"]) for model in answer["data"]]
        except (KeyError, TypeError):
            raise RuntimeError("Unerwartete Antwortform von /models") from None
