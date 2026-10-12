# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared JSON-over-HTTP helper; redirects are refused, proxies from the environment apply."""

import json
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None  # the 3xx surfaces as HTTPError; never follow to another host


# build_opener keeps the default ProxyHandler (HTTP_PROXY, HTTPS_PROXY, NO_PROXY)
_OPENER = urllib.request.build_opener(_NoRedirect)


def printable(text: str) -> str:
    """Replace control characters (terminal escapes) in foreign text with spaces."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", text)


def post_json(url: str, body: dict[str, Any], headers: dict[str, str], timeout: float) -> Any:
    """POST `body` as JSON and return the decoded answer.

    Raises:
        RuntimeError: HTTP error (status, first 200 chars of the body) or unreachable host.
    """
    request = urllib.request.Request(  # noqa: S310 (scheme comes from settings)
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    host = urlsplit(url).netloc
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        text = printable(error.read(200).decode(errors="replace"))
        raise RuntimeError(f"HTTP {error.code} von {host}: {text}") from None
    except ValueError:
        raise RuntimeError("Antwort ist kein gültiges JSON") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError(
            f"Verbindung zu {host} fehlgeschlagen: läuft der lokale Server?"
        ) from None
