# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline provider for tests: returns canned answers and records the prompts."""

from whattheshell.ai.protocol import Prompt


class FakeProvider:
    """Answers with `responses` in order; ``prompts`` holds everything it was sent."""

    name = "fake"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.prompts: list[Prompt] = []

    def complete(self, prompt: Prompt) -> str:
        """Return the next canned answer."""
        self.prompts.append(prompt)
        if not self._responses:
            raise RuntimeError("FakeProvider: keine Antwort mehr vorbereitet")
        return self._responses.pop(0)
