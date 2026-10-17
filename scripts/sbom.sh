#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Erzeugt die CycloneDX-SBOM (Python-Laufzeitabhängigkeiten + gebündelte npm-Pakete).
# Ausgabe: dist/sbom.cdx.json und src/whattheshell/sbom.cdx.json (landet im Wheel).
# Voraussetzung: npm ci in gui/ (package-lock.json).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
env -u VIRTUAL_ENV uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o "$tmp/req.txt"
env -u VIRTUAL_ENV uv run cyclonedx-py requirements "$tmp/req.txt" --sv 1.5 --of JSON -o "$tmp/py.cdx.json"
(cd gui && npx @cyclonedx/cyclonedx-npm --omit dev --sv 1.5 --of JSON -o "$tmp/npm.cdx.json")
mkdir -p dist
python3 scripts/sbom_merge.py "$tmp/py.cdx.json" "$tmp/npm.cdx.json" dist/sbom.cdx.json
cp dist/sbom.cdx.json src/whattheshell/sbom.cdx.json
