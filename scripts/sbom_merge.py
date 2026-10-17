#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Merge the Python and npm CycloneDX SBOMs into one SBOM for whattheshell.

Usage: sbom_merge.py PY_SBOM NPM_SBOM OUT
"""

import argparse
import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def merge(parts: list[dict], version: str) -> dict:
    """Return one SBOM with a whattheshell root depending on all direct components."""
    purl = f"pkg:pypi/whattheshell@{version}"
    components: dict[str, dict] = {}
    edges: dict[str, set[str]] = {}
    direct: set[str] = set()
    for part in parts:
        # bom-refs of the generators are not stable across tools: use the purl as reference
        ref_map = {c["bom-ref"]: c.get("purl", c["bom-ref"]) for c in part["components"]}
        root_ref = part.get("metadata", {}).get("component", {}).get("bom-ref")
        dep_map = {d["ref"]: d.get("dependsOn", []) for d in part.get("dependencies", [])}
        for comp in part["components"]:
            ref = ref_map[comp["bom-ref"]]
            components.setdefault(ref, {**comp, "bom-ref": ref})
            targets = {ref_map[t] for t in dep_map.get(comp["bom-ref"], []) if t in ref_map}
            edges.setdefault(ref, set()).update(targets)
        if root_ref is not None:
            direct |= {ref_map[t] for t in dep_map.get(root_ref, []) if t in ref_map}
        else:  # no root in the source (pip requirements): direct = nobody depends on it
            depended = {t for deps in dep_map.values() for t in deps}
            direct |= {ref_map[r] for r in ref_map if r not in depended}
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type": "application",
                "bom-ref": purl,
                "name": "whattheshell",
                "version": version,
                "licenses": [{"license": {"id": "AGPL-3.0-or-later"}}],
                "purl": purl,
            },
        },
        "components": [components[r] for r in sorted(components)],
        "dependencies": [{"ref": purl, "dependsOn": sorted(direct)}]
        + [{"ref": r, "dependsOn": sorted(edges[r])} for r in sorted(edges)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("py_sbom", type=Path)
    parser.add_argument("npm_sbom", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    parts = [json.loads(p.read_text()) for p in (args.py_sbom, args.npm_sbom)]
    args.out.write_text(json.dumps(merge(parts, version), indent=2) + "\n")


if __name__ == "__main__":
    main()
