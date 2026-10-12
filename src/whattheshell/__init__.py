# SPDX-License-Identifier: AGPL-3.0-or-later
"""WhatTheShell core package."""

from importlib.metadata import PackageNotFoundError, version

APP_NAME = "WhatTheShell"

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
