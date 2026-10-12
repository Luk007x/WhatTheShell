# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenAI-compatible chat completions over urllib (local servers and OpenAI)."""

import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from whattheshell.ai.protocol import Prompt

from .http import _OPENER, post_json


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
        """GET ``{base_url}/models`` (same opener: no redirects, proxies), return ``data[].id``.

        Raises:
            RuntimeError: HTTP error, unreachable host, or unexpected answer.
        """
        request = urllib.request.Request(  # noqa: S310 (scheme comes from settings)
            self._base + "/models", headers=self._headers
        )
        host = urlsplit(self._base).netloc
        # ponytail: own GET beside http.post_json; merge both into http.get_json when touched
        try:
            with _OPENER.open(request, timeout=self._timeout) as response:
                answer = json.load(response)
            return [str(model["id"]) for model in answer["data"]]
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"HTTP {error.code} von {host}") from None
        except OSError:  # URLError, timeout, connection reset
            raise RuntimeError(f"{host} nicht erreichbar") from None
        except (ValueError, KeyError, TypeError):
            raise RuntimeError(f"Unerwartete Antwortform von {host}/models") from None
