#!/usr/bin/env bash
# Baut Frontend und Wheel/sdist nach dist/ (lokal und in der CI).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$root/gui" && npm ci && npm run build)
cd "$root"
rm -rf dist
env -u VIRTUAL_ENV uv build
unzip -l dist/*.whl | grep -E "api/static/(index.html|assets/)"
