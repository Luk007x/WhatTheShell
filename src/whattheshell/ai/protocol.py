# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider protocol and factory; the only place that imports ``ai.providers``."""

from dataclasses import dataclass
from typing import Protocol

from whattheshell.ai import require_enabled
from whattheshell.settings import Settings


@dataclass(frozen=True)
class Prompt:
    """What is sent to a model."""

    system: str
    user: str
    max_tokens: int = 4000


class Provider(Protocol):
    """A model backend; `complete` returns the raw answer text (untrusted)."""

    name: str

    def complete(self, prompt: Prompt) -> str:
        """Send `prompt`, return the answer.

        Raises:
            RuntimeError: Backend unreachable or failed (message with cause and hint).
        """
        ...


def make_provider(settings: Settings) -> Provider:
    """Build the configured provider; the gate runs before ``ai.providers`` is imported.

    Raises:
        AiDisabled: AI is off.
        ImportError: ``ai.providers`` is not available.
    """
    require_enabled(settings)
    from .providers import build  # type: ignore[import-not-found,unused-ignore]  # lazy: gate first

    provider: Provider = build(settings.ai)
    return provider
