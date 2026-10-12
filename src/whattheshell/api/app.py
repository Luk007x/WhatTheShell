# SPDX-License-Identifier: AGPL-3.0-or-later
"""FastAPI application: security middleware, REST routers, static frontend."""

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from whattheshell import APP_NAME, paths
from whattheshell.api import ai_api, modules_api, rest, settings_api, workflows
from whattheshell.api.errors import error_response
from whattheshell.api.runs import router as runs_router
from whattheshell.api.security import SecurityMiddleware, Session
from whattheshell.catalog import Catalog
from whattheshell.modules.loader import WORKFLOW_SUFFIXES, DocumentError
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.modules.watch import watch_dirs, watch_modules
from whattheshell.settings import Settings, load_settings
from whattheshell.workflows import WorkflowIndex

STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger(__name__)
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


def _watch(app: FastAPI, stop: threading.Event) -> None:
    """Thread body: hot-reload module files; a failing watcher is logged, never fatal."""
    registry: ModuleRegistry = app.state.registry

    def started(_: object) -> None:
        app.state.modules_watch = True

    try:
        watch_modules(registry, stop, on_start=started)
    except Exception:
        logger.exception(
            "Modul-Überwachung beendet. Änderungen an Modulen brauchen einen Neustart."
        )
    app.state.modules_watch = False


def _watch_workflows(app: FastAPI, stop: threading.Event) -> None:
    """Thread body: hot-reload workflow files; a failing watcher is logged, never fatal."""
    index: WorkflowIndex = app.state.workflows

    def started(_: object) -> None:
        app.state.workflows_watch = True

    try:
        watch_dirs(index.dirs, WORKFLOW_SUFFIXES, lambda _: index.scan(), stop, started)
    except Exception:
        logger.exception(
            "Workflow-Überwachung beendet. Änderungen an Workflows brauchen einen Neustart."
        )
    app.state.workflows_watch = False


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    stop = threading.Event()
    threading.Thread(target=_watch, args=(app, stop), daemon=True, name="wts-modules-watch").start()
    threading.Thread(
        target=_watch_workflows, args=(app, stop), daemon=True, name="wts-workflows-watch"
    ).start()
    try:
        yield
    finally:
        stop.set()


def create_app(
    session: Session,
    *,
    catalog: Catalog,
    registry: ModuleRegistry,
    static_dir: Path | None = None,
) -> FastAPI:
    """Build the app; no docs or OpenAPI endpoints, so there is nothing open without a token."""
    app = FastAPI(
        title=APP_NAME, docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan
    )
    app.state.session = session
    app.state.catalog = catalog
    # raw catalog: no module overrides, the base of module scaffolds
    app.state.raw_catalog = Catalog(catalog.cache_dir, sandbox=catalog.sandbox)
    try:
        app.state.settings = load_settings()
    except DocumentError as err:  # a broken file must not stop the GUI; AI stays off
        logger.warning("Einstellungen nicht lesbar, KI bleibt aus: %s", err)
        app.state.settings = Settings()
    app.state.modules_watch = False
    app.state.registry = registry
    app.state.workflows_watch = False
    app.state.workflows = WorkflowIndex(paths.workflow_dirs(Path.cwd()))
    app.state.workflows.scan()
    app.add_middleware(SecurityMiddleware, session=session)
    app.add_exception_handler(StarletteHTTPException, _http_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error)  # type: ignore[arg-type]
    app.include_router(rest.router)
    app.include_router(modules_api.router)
    app.include_router(modules_api.templates_router)
    app.include_router(workflows.router)
    app.include_router(runs_router)
    app.include_router(settings_api.router)
    app.include_router(ai_api.router)
    root = STATIC_DIR if static_dir is None else static_dir
    if (root / "index.html").is_file():
        app.mount("/", StaticFiles(directory=root, html=True))
    else:

        @app.get("/")
        def frontend_missing() -> JSONResponse:
            return error_response(503, "frontend", FRONTEND_MISSING)

    return app
