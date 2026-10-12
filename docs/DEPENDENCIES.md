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
| hatchling (Build) | 1.32.4 | MIT | ja | Build-Backend (nur Paketbau) |
