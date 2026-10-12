# Abhängigkeiten

Lizenzen aus den Paket-Metadaten (importlib.metadata). Alle permissiv (MIT, BSD, Apache-2.0, MPL-2.0 nur Dev), damit AGPL-3.0-or-later-kompatibel.

| Paket | Version | Lizenz | AGPL-kompatibel | Zweck |
|---|---|---|---|---|
| pydantic | 2.14.1 | MIT | ja | Modelle und Schema-Export |
| ruamel.yaml | 0.19.1 | MIT | ja | YAML lesen/schreiben (Module, Workflows) |
| watchfiles | 1.3.0 | MIT | ja | Modul-Ordner beobachten (Live-Reload) |
| fastapi | 0.143.0 | MIT | ja | Lokale HTTP/WebSocket-API |
| starlette (via fastapi) | 1.7.0 | BSD-3-Clause | ja | ASGI-Grundlage von FastAPI |
| uvicorn[standard] | 0.54.0 | BSD-3-Clause | ja | ASGI-Server für `wts gui` |
| click, h11 (via uvicorn) | 8.5.0, 0.16.0 | BSD-3-Clause, MIT | ja | Server-Grundlagen |
| httptools, uvloop (via uvicorn[standard]) | 0.9.0, 0.23.0 | MIT | ja | Schnellere HTTP-/Eventloop-Pfade |
| websockets (via uvicorn[standard]) | 17.2 | BSD-3-Clause | ja | WebSocket-Transport |
| python-dotenv, pyyaml (via uvicorn[standard]) | 1.2.4, 6.0.3 | BSD-3-Clause, MIT | ja | Transitiv, ungenutzt |
| annotated-doc, opentelemetry-api (via fastapi) | 0.0.5, 1.45.1 | MIT, Apache-2.0 | ja | Transitiv |
| pytest (dev) | 9.1.1 | MIT | ja | Tests |
| ruff (dev) | 0.17.0 | MIT | ja | Lint und Format |
| mypy (dev) | 2.4.0 | MIT | ja | Typprüfung |
| httpx (dev) | 0.28.1 | BSD-3-Clause | ja | `TestClient` der API-Tests |
| httpcore, certifi (dev, via httpx) | 1.0.9, 2026.7.22 | BSD-3-Clause, MPL-2.0 | ja (nicht ausgeliefert) | Transitiv |
| keyring (optional, nicht installiert) | >=25 | MIT | ja | Extra `keyring`: API-Schlüssel im Systemschlüsselbund (`key_source: keyring`) |
| hatchling (Build) | 1.32.4 | MIT | ja | Build-Backend (nur Paketbau) |

## Frontend (`gui/`, nur Build-Zeit; das gebaute Bundle liegt im Wheel)

| Paket | Version | Lizenz | AGPL-kompatibel | Zweck |
|---|---|---|---|---|
| react, react-dom | 18.3 | MIT | ja | UI |
| @xyflow/react | 12.12 | MIT | ja | Knoten-Graph |
| @dagrejs/dagre | 3.1 | MIT | ja | Auto-Layout |
| yaml | 2.x | ISC | ja | Modul-Editor: Formular ↔ YAML-Rohtext |
| vite, @vitejs/plugin-react, vitest (dev) | 6.4, 4.7, 4.1 | MIT | ja | Build, Tests |
| typescript (dev) | 5.9 | Apache-2.0 | ja | Typprüfung |
| json-schema-to-typescript (dev) | 16 | MIT | ja | Typen aus `schemas/` |
| @playwright/test (dev) | 1.64 | Apache-2.0 | ja | E2E-Smoke |
| @axe-core/playwright (dev) | 4.x | MPL-2.0 | ja (nur Tests, nicht ausgeliefert) | Barrierefreiheits-Audit (WCAG 2.1 AA) |
| @types/* (dev) | – | MIT | ja | Typdefinitionen |
