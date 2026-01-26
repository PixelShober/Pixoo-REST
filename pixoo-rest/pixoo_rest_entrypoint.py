"""FastAPI entrypoint for Pixoo REST with Time Gate support."""

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
app = FastAPI(
    title="Pixoo REST API",
    description="A modern async RESTful API to interact with Wi-Fi enabled Divoom Pixoo devices",
    version=__version__,
    lifespan=lifespan,
)

# Include routers
app.include_router(draw.router)
app.include_router(send.router)
app.include_router(set_router.router)
app.include_router(image.router)
app.include_router(download.router)
app.include_router(divoom.router)
app.include_router(timegate_router)


@app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint."""
    return HealthCheckResponse(status="healthy", pixoo_host=settings.pixoo_host)


@app.get("/", response_model=RootResponse)
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
