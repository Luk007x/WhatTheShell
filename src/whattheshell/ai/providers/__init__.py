# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider factory; provider modules are imported only inside `build`."""

from whattheshell.ai.protocol import Provider
from whattheshell.settings import AiSettings


def build(settings: AiSettings) -> Provider:
    """Create the provider selected in `settings.provider`.

    Raises:
        RuntimeError: Model missing for `api`, or the API key is unavailable.
    """
    if settings.provider == "agent":
        from .agent_cli import AgentCliProvider

        agent = settings.agent
        return AgentCliProvider(agent.kind, agent.command, agent.timeout)
    if settings.provider == "local":
        from .openai_compat import OpenAICompatProvider

        local = settings.local
        return OpenAICompatProvider(local.base_url, local.model, local.timeout, api_key=None)
    api = settings.api
    if not api.model:
        raise RuntimeError("Kein Modell für die API gesetzt: `wts ai config set api.model <name>`")
    from .keys import resolve_key

    key = resolve_key(api)
    if api.kind == "openai":
        from .openai_compat import OpenAICompatProvider

        url = api.base_url or "https://api.openai.com/v1"
        return OpenAICompatProvider(url, api.model, api.timeout, api_key=key)
    from .anthropic import AnthropicProvider

    return AnthropicProvider(
        api.base_url or "https://api.anthropic.com", api.model, api.timeout, api_key=key
    )
