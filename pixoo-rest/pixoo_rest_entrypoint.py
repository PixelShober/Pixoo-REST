"""FastAPI entrypoint for Pixoo REST with Time Gate support and root redirect."""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pixoo import Pixoo

from pixoo_rest import __version__, utils
from pixoo_rest.api import divoom, download, draw, image, send, set as set_router
from pixoo_rest.core.config import settings
from pixoo_rest.dependencies import get_pixoo, set_pixoo_instance
from pixoo_rest.models.requests import HealthCheckResponse, RootResponse
from pixoo_rest_devices import (
    get_device_registry,
    initialize_device_registry,
    load_devices_from_env,
    normalize_device_type,
)
from pixoo_rest_timegate import router as timegate_router


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


def _resolve_device_selector(
    device: str | None,
    host: str | None,
    header_device: str | None,
    header_host: str | None,
):
    try:
        registry = get_device_registry()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    device_key = device or header_device
    host_value = host or header_host
    selected = registry.select(device_key, host_value)
    if selected is None:
        available = ", ".join(registry.keys()) or "none"
        raise HTTPException(
            status_code=404,
            detail=f"Device not found. Available devices: {available}",
        )
    return selected


def get_pixoo_for_request(
    request: Request,
    device: str | None = Query(
        None,
        description="Device alias configured in the add-on (defaults to first device).",
    ),
    host: str | None = Query(
        None,
        description="Device host/IP to target (overrides default device).",
    ),
    x_pixoo_device: str | None = Header(None, alias="X-Pixoo-Device"),
    x_pixoo_host: str | None = Header(None, alias="X-Pixoo-Host"),
) -> Pixoo:
    selected = _resolve_device_selector(device, host, x_pixoo_device, x_pixoo_host)
    if selected.device_type != "pixoo":
        raise HTTPException(
            status_code=400,
            detail=f"Device '{selected.key}' is configured as {selected.device_type}.",
        )
    if selected.pixoo is None:
        raise HTTPException(status_code=503, detail="Pixoo device not initialized")
    return selected.pixoo


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown."""
    devices = load_devices_from_env()
    registry = initialize_device_registry(devices)

    if not registry.devices:
        sys.exit("ERROR: No Pixoo devices configured.")

    print("Initializing Pixoo REST devices...")
    default_pixoo = None

    for device in registry.devices:
        device.device_type = normalize_device_type(device.device_type)
        if device.device_type == "auto":
            device.device_type = "pixoo"
            print(
                f"Device '{device.key}' has device_type=auto; defaulting to pixoo."
            )

        if device.device_type == "time_gate":
            if device.screen_size < 128:
                device.screen_size = 128
            print(
                f"Time Gate device '{device.key}' configured at {device.host}."
            )
            continue

        print(f"Connecting to Pixoo device '{device.key}' at {device.host}...")
        for connection_test_count in range(device.connection_retries + 1):
            if utils.try_to_request(f"http://{device.host}/get"):
                break
            if connection_test_count == device.connection_retries:
                sys.exit(
                    f"ERROR: Failed to connect to Pixoo device '{device.key}' at {device.host}."
                )
            print(
                f"Connection attempt {connection_test_count + 1} failed for {device.host}, retrying..."
            )

        device.pixoo = Pixoo(device.host, device.screen_size, device.debug)
        print(f"Successfully connected to Pixoo device '{device.key}' at {device.host}")

        if default_pixoo is None:
            default_pixoo = device.pixoo

    if default_pixoo is not None:
        set_pixoo_instance(default_pixoo)

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
pixoo_app.dependency_overrides[get_pixoo] = get_pixoo_for_request


@pixoo_app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint."""
    registry = get_device_registry()
    default_host = registry.default.host if registry.default else settings.pixoo_host
    return HealthCheckResponse(status="healthy", pixoo_host=default_host)


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
