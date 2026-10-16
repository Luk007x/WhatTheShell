# SPDX-License-Identifier: AGPL-3.0-or-later
"""The suite runs with German messages: German texts are the catalog keys and the assertions."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _german_messages(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("WTS_LANG", "de")
    from whattheshell import i18n

    token = i18n.set_lang("de")
    yield
    i18n._lang.reset(token)
