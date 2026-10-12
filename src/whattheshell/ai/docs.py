# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read the documents that go into prompts (bundled in the wheel, repo checkout as fallback)."""

import logging
from pathlib import Path

from whattheshell import bundled

logger = logging.getLogger(__name__)


def read_doc(name: str, start: str | None = None, end: str | None = None) -> str:
    """Text of a doc, optionally only the part between `start` and `end`.

    Returns an empty string (and logs a warning) when the doc is not found.
    """
    for folder in (bundled.DOCS_DIR, Path(__file__).resolve().parents[3] / "docs"):
        try:
            text = (folder / name).read_text(encoding="utf-8")
            break
        except OSError:
            continue
    else:
        logger.warning("Dokument %s nicht gefunden; der Prompt enthält es nicht.", name)
        return ""
    if start is not None:
        text = text.partition(start)[2]
        text = text.partition(end)[0] if end else text
    return text
