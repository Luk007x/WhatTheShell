# SPDX-License-Identifier: AGPL-3.0-or-later
"""FastAPI application: security middleware, REST routers, static frontend."""

from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from whattheshell import APP_NAME
from whattheshell.api import rest, workflows
from whattheshell.api.errors import error_response
from whattheshell.api.runs import router as runs_router
from whattheshell.api.security import SecurityMiddleware, Session
from whattheshell.catalog import Catalog
from whattheshell.modules.registry import ModuleRegistry

STATIC_DIR = Path(__file__).parent / "static"
FRONTEND_MISSING = "Frontend nicht gebaut: cd gui && npm ci && npm run build"


def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        return error_response(exc.status_code, **detail)
    code = HTTPStatus(exc.status_code).phrase.lower().replace(" ", "_")
    return error_response(exc.status_code, code, str(detail))


def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"path": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
        for item in exc.errors()
    ]
    return error_response(422, "validation", "Ungültige Anfrage.", errors)


def create_app(
    session: Session,
    *,
    catalog: Catalog,
    registry: ModuleRegistry,
    static_dir: Path | None = None,
) -> FastAPI:
    """Build the app; no docs or OpenAPI endpoints, so there is nothing open without a token."""
    app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.session = session
    app.state.catalog = catalog
    app.state.registry = registry
    app.add_middleware(SecurityMiddleware, session=session)
    app.add_exception_handler(StarletteHTTPException, _http_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error)  # type: ignore[arg-type]
    app.include_router(rest.router)
    app.include_router(workflows.router)
    app.include_router(runs_router)
    root = STATIC_DIR if static_dir is None else static_dir
    if (root / "index.html").is_file():
        app.mount("/", StaticFiles(directory=root, html=True))
    else:

        @app.get("/")
        def frontend_missing() -> JSONResponse:
            return error_response(503, "frontend", FRONTEND_MISSING)

    return app
