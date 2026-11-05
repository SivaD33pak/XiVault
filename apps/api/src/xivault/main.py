"""XiVault FastAPI main application."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from xivault.api.auth import router as auth_router
from xivault.api.vault import router as vault_router
from xivault.config import settings
from xivault.db.session import close_db_pool, init_db_pool
from xivault.exceptions import XiVaultAPIException, xivault_exception_handler


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    await init_db_pool()
    yield
    await close_db_pool()


app = FastAPI(
    title="XiVault API",
    description="Authorized private source-code vault service",
    version="0.1.0",
    docs_url="/docs" if settings.xivault_env != "production" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.xivault_env != "production" else None,
    lifespan=lifespan,
)

# CORS middleware
origins = [settings.xivault_api_origin]
if settings.xivault_env == "development":
    origins.append("vscode-webview://*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if settings.xivault_env == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Ensure every request has an X-Request-ID."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Register custom XiVault exception handlers
app.add_exception_handler(XiVaultAPIException, xivault_exception_handler)  # type: ignore


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Format Pydantic 422 errors into the contract envelope."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=422,
        headers={"X-Request-ID": request_id},
        content={
            "error": {
                "code": "validation_error",
                "message": str(exc.errors()[0]["msg"]) if exc.errors() else "Validation failed",
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Format unhandled exceptions according to the API contract."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=500,
        headers={"X-Request-ID": request_id},
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected server error occurred.",
                "request_id": request_id,
            }
        },
    )


# Mount versioned routers
app.include_router(auth_router, prefix="/v1")
app.include_router(vault_router, prefix="/v1")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Process liveness probe."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    """Dependency readiness probe."""
    return {"status": "ready", "environment": settings.xivault_env}


@app.get("/")
async def root() -> dict[str, str]:
    """Service metadata endpoint."""
    return {"name": "XiVault API", "version": "0.1.0", "status": "online"}
