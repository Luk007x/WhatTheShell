#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Baut Frontend und Wheel/sdist nach dist/ (lokal und in der CI).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$root/gui" && npm ci && npm run build)
cd "$root"
rm -rf dist
scripts/sbom.sh
env -u VIRTUAL_ENV uv build
unzip -l dist/*.whl | grep -E "api/static/(index.html|assets/)"
unzip -l dist/*.whl | grep -E "whattheshell/sbom.cdx.json"
