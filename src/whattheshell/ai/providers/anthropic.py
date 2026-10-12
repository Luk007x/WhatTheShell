# SPDX-License-Identifier: AGPL-3.0-or-later
"""Anthropic Messages API over urllib."""

from whattheshell.ai.protocol import Prompt

from .http import post_json


class AnthropicProvider:
    """`/v1/messages` client."""

    name = "anthropic"

    def __init__(self, base_url: str, model: str, timeout: float, api_key: str) -> None:
        self._url = base_url.rstrip("/") + "/v1/messages"
        self._model = model
        self._timeout = timeout
        self._headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}

    def complete(self, prompt: Prompt) -> str:
        """Send `prompt`, return `content[0].text`."""
        body = {
            "model": self._model,
            "max_tokens": prompt.max_tokens,
            "system": prompt.system,
            "messages": [{"role": "user", "content": prompt.user}],
        }
        answer = post_json(self._url, body, self._headers, self._timeout)
        try:
            return str(answer["content"][0]["text"])
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("Unerwartete Antwortform des Servers") from None
