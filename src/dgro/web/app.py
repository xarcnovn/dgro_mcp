"""FastAPI application: server-rendered pages, no JavaScript build step."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ..runtime import Runtime, build_runtime

log = logging.getLogger(__name__)
HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))


# --- template helpers ----------------------------------------------------------------------------------
def local_time(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    if value is None:
        return ""
    return value.replace(tzinfo=UTC).astimezone().strftime(fmt)


def ago(value: datetime | None) -> str:
    if value is None:
        return ""
    seconds = (datetime.now(UTC).replace(tzinfo=None) - value).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    if seconds < 86400 * 7:
        return f"{int(seconds // 86400)} d ago"
    return local_time(value, "%Y-%m-%d")


NBSP = "\u00a0"


def money(amount: float | None, currency: str = "") -> str:
    if amount is None:
        return "—"
    text = f"{amount:,.2f}".rstrip("0").rstrip(".") if amount % 1 else f"{amount:,.0f}"
    return f"{text.replace(',', NBSP)}{NBSP}{currency}".strip(" \u00a0")  # keeps "24 900 PLN" on one line


templates.env.filters["local_time"] = local_time
templates.env.filters["ago"] = ago
templates.env.globals["money"] = money


# --- app -----------------------------------------------------------------------------------------------
def create_app(runtime: Runtime | None = None, *, start_worker: bool = True) -> FastAPI:
    rt = runtime or build_runtime()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_worker:
            rt.worker.start()
        yield
        if start_worker:
            rt.worker.stop()

    app = FastAPI(title="dgro", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.rt = rt
    templates.env.globals["settings"] = rt.settings
    templates.env.globals["llm_name"] = rt.llm.name
    templates.env.globals["mail_name"] = rt.mail.name

    # This app has no login: only accept requests addressed to the configured local host names (blocks DNS
    # rebinding), and reject form posts coming from other sites (CSRF).
    hosts = ["127.0.0.1", "localhost", "testserver", rt.settings.host]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"] if rt.settings.host == "0.0.0.0" else hosts)

    @app.middleware("http")
    async def same_origin_posts(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            source = request.headers.get("origin") or request.headers.get("referer")
            if source is not None and (source == "null"
                                       or urlparse(source).netloc != request.headers.get("host", "")):
                return PlainTextResponse("Cross-site request blocked.", status_code=403)
        return await call_next(request)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return templates.TemplateResponse(request, "error.html", {"message": "Not found."}, status_code=404)
        return HTMLResponse(str(exc.detail), status_code=exc.status_code)

    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    from .routes import router

    app.include_router(router)
    return app
