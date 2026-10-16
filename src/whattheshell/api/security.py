# SPDX-License-Identifier: AGPL-3.0-or-later
"""Session token, Host/Origin checks and token check as pure ASGI middleware (HTTP and WebSocket).

No CORS headers are ever sent: the page is served from the same origin.
"""

import secrets
from dataclasses import dataclass, field
from urllib.parse import parse_qs

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from whattheshell.api.errors import error_response
from whattheshell.i18n import _, current_lang, normalize, use_lang

TOKEN_HEADER = "x-wts-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
GUARDED_PREFIXES = ("/api/", "/ws/")
MAX_BODY_BYTES = 1_048_576
TOO_LARGE = "Anfrage zu groß (Grenze 1 MiB)."


@dataclass(frozen=True, kw_only=True)
class Session:
    """Per-start secret and port of the local server."""

    port: int
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))


class SecurityMiddleware:
    """Reject requests with a foreign Host (DNS rebinding), foreign Origin (CSRF) or bad token."""

    def __init__(self, app: ASGIApp, session: Session) -> None:
        self.app = app
        self.session = session
        self.hosts = {f"127.0.0.1:{session.port}", f"localhost:{session.port}"}
        self.origins = {f"http://{host}" for host in self.hosts}

    def _violation(self, scope: Scope) -> tuple[int, str, str] | None:
        """Return (status, error, message) of the first violated rule, or None."""
        headers = Headers(scope=scope)
        is_ws = scope["type"] == "websocket"
        if headers.get("host", "").lower() not in self.hosts:
            return (
                400,
                "host",
                _("Unzulässiger Host-Header. Erlaubt: 127.0.0.1 und localhost."),
            )
        path: str = scope["path"]
        if path.startswith(GUARDED_PREFIXES):
            if is_ws:
                query = parse_qs(scope["query_string"].decode("latin-1"))
                supplied = query.get("token", [""])[0]
            else:
                supplied = headers.get(TOKEN_HEADER, "")
            if not secrets.compare_digest(supplied.encode(), self.session.token.encode()):
                return (
                    401,
                    "token",
                    _("Token fehlt oder ist falsch. Öffne die URL von `wts gui`."),
                )
        origin = headers.get("origin")
        if (is_ws or scope["method"] not in SAFE_METHODS) and origin and origin not in self.origins:
            return (
                403,
                "origin",
                _("Unzulässiger Origin. Anfragen nur von der eigenen Oberfläche."),
            )
        length = headers.get("content-length", "0")
        if length.isdigit() and int(length) > MAX_BODY_BYTES:
            return 413, "body_too_large", _(TOO_LARGE)
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        accept = headers.get("accept-language", "").split(",")[0].split(";")[0]
        if scope["type"] == "websocket":  # browsers cannot set headers on a WebSocket
            query = parse_qs(scope["query_string"].decode("latin-1"))
            asked = normalize(query.get("lang", [""])[0])
        else:
            asked = normalize(headers.get("x-wts-lang"))
        lang = asked or normalize(accept) or current_lang()
        with use_lang(lang):  # contextvar: copied into handler threads and tasks
            await self._dispatch(scope, receive, send)

    async def _dispatch(self, scope: Scope, receive: Receive, send: Send) -> None:
        violation = self._violation(scope)
        if violation is None:
            if scope["type"] == "http":
                await self._limited(scope, receive, send)
            else:
                await self.app(scope, receive, send)
            return
        status, error, message = violation
        if scope["type"] == "http":
            await error_response(status, error, message)(scope, receive, send)
        else:
            await receive()  # websocket.connect
            await send({"type": "websocket.close", "code": 4000 + status, "reason": message})

    async def _limited(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the app; a body without content-length that exceeds the limit is answered 413."""
        seen = 0
        rejected = False

        async def counting() -> Message:
            nonlocal seen, rejected
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > MAX_BODY_BYTES and not rejected:
                    rejected = True
                    await error_response(413, "body_too_large", _(TOO_LARGE))(scope, receive, send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded(message: Message) -> None:
            if not rejected:  # the app's own (400) answer to the cut-off body is dropped
                await send(message)

        await self.app(scope, counting, guarded)
