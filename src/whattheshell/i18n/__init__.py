# SPDX-License-Identifier: AGPL-3.0-or-later
"""Backend message language: German source strings, English via catalog (default English).

``_("Deutscher Text {name}", name=...)`` returns the text in the current language. Module YAML
texts are translated separately (``whattheshell.modules.i18n``).
"""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Literal

from whattheshell.i18n import en_api, en_cli, en_engine, en_misc

Lang = Literal["de", "en"]

CATALOGS: dict[str, dict[str, str]] = {
    "en": en_cli.CATALOG | en_engine.CATALOG | en_api.CATALOG | en_misc.CATALOG
}
missing: set[str] = set()  # untranslated texts seen while WTS_I18N_DEBUG=1

_lang: ContextVar[Lang | None] = ContextVar("wts_lang", default=None)


def normalize(value: str | None) -> Lang | None:
    """Map "de", "de-DE", "en_US.UTF-8" etc. to "de"/"en"; anything else gives None."""
    code = (value or "").strip().lower()
    for lang in ("de", "en"):
        if code == lang or code[:3] in (f"{lang}-", f"{lang}_"):
            return lang
    return None


_stored: tuple[tuple[str, int, int] | None, str] | None = None  # ((path, mtime_ns, size), language)


def invalidate() -> None:
    """Forget the cached settings language (call after saving settings)."""
    global _stored
    _stored = None


def _stored_language() -> str:
    """``language`` from settings.yaml, cached by file mtime and size; "auto" if unreadable."""
    global _stored
    from whattheshell.settings import load_settings, settings_path  # lazy: avoids an import cycle

    try:
        path = settings_path()
        stat = path.stat()
        key: tuple[str, int, int] | None = (str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        key = None  # missing file: defaults
    if _stored is None or _stored[0] != key:
        try:
            language: str = load_settings().language
        except Exception:  # noqa: BLE001  # broken settings must not break messages
            language = "auto"
        _stored = (key, language)
    return _stored[1]


def resolve_default() -> Lang:
    """WTS_LANG, then settings ``language``, then locale variables, else "en"."""
    found = normalize(os.environ.get("WTS_LANG"))
    if found:
        return found
    found = normalize(_stored_language())
    if found:
        return found
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        found = normalize((os.environ.get(name) or "").split(":")[0])
        if found:
            return found
    return "en"


def current_lang() -> Lang:
    """Language of the running request/command; the default when none was set."""
    return _lang.get() or resolve_default()


def set_lang(lang: Lang) -> Token[Lang | None]:
    """Set the language of the current context; pass the token to ``_lang.reset``."""
    return _lang.set(lang)


@contextmanager
def use_lang(lang: Lang) -> Iterator[None]:
    """Use ``lang`` inside the block."""
    token = _lang.set(lang)
    try:
        yield
    finally:
        _lang.reset(token)


def _(text: str, /, **kw: object) -> str:
    """Return the German source ``text`` in the current language, formatted with ``kw``.

    Without ``kw`` the text is not formatted, so untranslated texts with braces stay intact.
    """
    if current_lang() == "en":
        translated = CATALOGS["en"].get(text)
        if translated is None and os.environ.get("WTS_I18N_DEBUG") == "1":
            missing.add(text)
            print(f"i18n missing: {text!r}", file=sys.stderr)
        text = translated or text
    return text.format(**kw) if kw else text
