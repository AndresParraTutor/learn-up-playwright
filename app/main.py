from __future__ import annotations

import hmac
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import attempts, catalog, labs, lessons, progress, topic_transfer, topics
from app.config import get_settings
from app.db import engine
from app.models import Base

settings = get_settings()
Base.metadata.create_all(engine)

app = FastAPI(
    title="learn-up",
    version="1.15",
    description="Aplicación local de estudio",
)
app.state.api_token = settings.api_token or secrets.token_urlsafe(32)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        "[::1]",
        "testclient",
        "testserver",
    ],
)


def _allowed_browser_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        and port in {settings.frontend_port, settings.backend_port}
    )


@app.middleware("http")
async def local_api_security(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            return JSONResponse(
                status_code=403, content={"detail": "Solicitud cross-site rechazada."}
            )
        origin = request.headers.get("origin")
        if origin and not _allowed_browser_url(origin):
            return JSONResponse(
                status_code=403, content={"detail": "Origin no permitido."}
            )
        referer = request.headers.get("referer")
        if not origin and referer and not _allowed_browser_url(referer):
            return JSONResponse(
                status_code=403, content={"detail": "Referer no permitido."}
            )
        if path not in {"/api/health", "/api/auth/token"}:
            supplied = request.headers.get("x-learnup-token", "")
            if not hmac.compare_digest(supplied, request.app.state.api_token):
                return JSONResponse(
                    status_code=401, content={"detail": "Token de sesión inválido."}
                )
    return await call_next(request)


@app.get("/api/health")
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/auth/token")
def auth_token(request: Request) -> dict[str, str]:
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "testclient"}:
        return JSONResponse(
            status_code=403, content={"detail": "El token solo se entrega por loopback."}
        )
    return {"token": request.app.state.api_token}


app.include_router(topics.router)
app.include_router(catalog.router)
app.include_router(lessons.router)
app.include_router(attempts.router)
app.include_router(progress.router)
app.include_router(labs.router)
app.include_router(topic_transfer.router)

MEDIA_ROOT = Path(__file__).resolve().parents[1] / "media"
MEDIA_ROOT.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
