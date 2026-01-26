"""FastAPI entrypoint for Pixoo REST with Time Gate support and root redirect."""

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from pixoo import Pixoo

from pixoo_rest import __version__, utils
from pixoo_rest.api import divoom, download, draw, image, send, set as set_router
from pixoo_rest.core.config import settings
from pixoo_rest.dependencies import set_pixoo_instance
from pixoo_rest.models.requests import HealthCheckResponse, RootResponse
from pixoo_rest_timegate import router as timegate_router


def _normalize_device_type(value: str | None) -> str:
    normalized = (value or "pixoo").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    if normalized in ("timegate", "time_gate"):
        return "time_gate"
    if normalized == "auto":
        return "auto"
    return "pixoo"


def _root_path_from_headers(headers):
    for key in (
        "x-ingress-path",
        "x-forwarded-prefix",
        "x-forwarded-path",
        "x-script-name",
    ):
        value = headers.get(key)
        if not value:
            continue
        value = value.split(",")[0].strip().rstrip("/")
        if not value:
            continue
        if not value.startswith("/"):
            value = f"/{value}"
        return value
    return ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown."""
    device_type = _normalize_device_type(os.getenv("PIXOO_DEVICE_TYPE"))
    if device_type == "auto":
        device_type = "pixoo"

    if device_type == "time_gate":
        print("Time Gate mode enabled. Skipping Pixoo initialization.")
        yield
        print("Shutting down...")
        return

    # Startup: Initialize Pixoo device
    print(f"Connecting to Pixoo device at {settings.pixoo_host}...")

    # Test connection to Pixoo device
    for connection_test_count in range(settings.pixoo_test_connection_retries + 1):
        if utils.try_to_request(f"http://{settings.pixoo_host}/get"):
            break
        if connection_test_count == settings.pixoo_test_connection_retries:
            sys.exit("ERROR: Failed to connect to Pixoo device.")
        print(f"Connection attempt {connection_test_count + 1} failed, retrying...")

    pixoo = Pixoo(settings.pixoo_host, settings.pixoo_screen_size, settings.pixoo_debug)
    print(f"Successfully connected to Pixoo device at {settings.pixoo_host}")

    # Set the global pixoo instance
    set_pixoo_instance(pixoo)

    yield

    # Shutdown: Cleanup if needed
    print("Shutting down...")


# Create FastAPI app
pixoo_app = FastAPI(
    title="Pixoo REST API",
    description="A modern async RESTful API to interact with Wi-Fi enabled Divoom Pixoo devices",
    version=__version__,
    lifespan=lifespan,
)

# Include routers
pixoo_app.include_router(draw.router)
pixoo_app.include_router(send.router)
pixoo_app.include_router(set_router.router)
pixoo_app.include_router(image.router)
pixoo_app.include_router(download.router)
pixoo_app.include_router(divoom.router)
pixoo_app.include_router(timegate_router)


@pixoo_app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint."""
    return HealthCheckResponse(status="healthy", pixoo_host=settings.pixoo_host)


@pixoo_app.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    """Root endpoint with API information."""
    return RootResponse(
        name="Pixoo REST API",
        version=__version__,
        description="Modern async FastAPI application for Divoom Pixoo devices",
        docs="/docs",
        redoc="/redoc",
        openapi="/openapi.json",
    )


async def app(scope, receive, send):
    if scope.get("type") == "http":
        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        root_path = _root_path_from_headers(headers)
        if root_path:
            scope = dict(scope)
            scope["root_path"] = root_path

        path = scope.get("path", "")
        if path.startswith("//"):
            scope = dict(scope)
            scope["path"] = f"/{path.lstrip('/')}"
            path = scope["path"]
        if path in ("", "/"):
            response = RedirectResponse(url="docs")
            await response(scope, receive, send)
            return

    await pixoo_app(scope, receive, send)
