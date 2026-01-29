"""Time Gate endpoints for Pixoo REST."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from pixoo_rest.models.requests import DivoomApiResponse
from pixoo_rest_devices import get_device_registry

router = APIRouter(prefix="/timegate", tags=["timegate"])


def _validate_lcd_array(lcd_array: list[int]) -> list[int]:
    if len(lcd_array) != 5:
        raise HTTPException(status_code=422, detail="lcd_array must contain 5 items.")
    if any(value not in (0, 1) for value in lcd_array):
        raise HTTPException(status_code=422, detail="lcd_array values must be 0 or 1.")
    return lcd_array


def _select_timegate_device(
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
):
    try:
        registry = get_device_registry()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    device_key = device or x_pixoo_device
    host_value = host or x_pixoo_host
    selected = registry.select(device_key, host_value)
    if selected is None:
        available = ", ".join(registry.keys()) or "none"
        raise HTTPException(
            status_code=404,
            detail=f"Device not found. Available devices: {available}",
        )
    if selected.device_type != "time_gate":
        raise HTTPException(
            status_code=400,
            detail=f"Device '{selected.key}' is configured as {selected.device_type}.",
        )
    return selected


async def _post_command(payload: dict[str, Any], host: str) -> DivoomApiResponse:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"http://{host}/post",
                json=payload,
            )
            response.raise_for_status()
            return DivoomApiResponse(**response.json())
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Time Gate request failed: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Time Gate request failed: {exc}",
        ) from exc


async def _post_raw(payload: dict[str, Any], host: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"http://{host}/post",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Time Gate request failed: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Time Gate request failed: {exc}",
        ) from exc


class TimeGateSendGifRequest(BaseModel):
    """Request model for sending GIF frames to Time Gate."""

    lcd_array: list[int] = Field(
        default_factory=lambda: [1, 1, 1, 1, 1],
        description="Target screens (5 values of 0/1).",
    )
    pic_num: int = Field(..., ge=1, le=60, description="Total number of frames.")
    pic_width: int | None = Field(
        default=None,
        description="Frame width (16, 32, 64, or 128). Defaults to PIXOO_SCREEN_SIZE.",
    )
    pic_offset: int = Field(..., ge=0, description="Frame offset (0-based).")
    pic_id: int = Field(..., ge=1, description="Animation ID.")
    pic_speed: int = Field(..., ge=1, description="Frame delay in ms.")
    pic_data: str = Field(..., description="Base64-encoded JPG data.")


class TimeGateSendTextRequest(BaseModel):
    """Request model for sending scrolling text to Time Gate."""

    lcd_index: int = Field(..., ge=0, le=4, description="Target screen index (0-4).")
    text_id: int = Field(default=1, ge=0, le=20, description="Unique text ID (0-19).")
    x: int = Field(default=0, ge=0, description="Start X position.")
    y: int = Field(default=0, ge=0, description="Start Y position.")
    direction: int = Field(default=0, ge=0, le=1, description="0=left, 1=right.")
    font: int = Field(default=0, ge=0, le=7, description="Font index (0-7).")
    text_width: int = Field(default=56, ge=16, le=64, description="Text width (16-64).")
    text: str = Field(..., max_length=512, description="Text to display.")
    speed: int = Field(default=10, ge=0, description="Scroll speed in ms per step.")
    color: str = Field(default="#FFFFFF", description="Text color as hex string.")
    align: int = Field(default=1, ge=1, le=3, description="Alignment: 1=left, 2=center, 3=right.")


class TimeGatePlayGifRequest(BaseModel):
    """Request model for playing GIFs on Time Gate."""

    lcd_array: list[int] = Field(
        default_factory=lambda: [1, 1, 1, 1, 1],
        description="Target screens (5 values of 0/1).",
    )
    file_name: list[str] = Field(..., description="List of GIF URLs.")


class TimeGateBrightnessRequest(BaseModel):
    """Request model for setting Time Gate brightness."""

    brightness: int = Field(..., ge=0, le=100, description="Brightness (0-100).")


class TimeGateCommandListRequest(BaseModel):
    """Request model for sending a list of Time Gate commands."""

    command_list: list[dict[str, Any]] = Field(
        ..., description="List of command payloads."
    )


class TimeGateCommandRequest(BaseModel):
    """Request model for sending a raw Time Gate command."""

    command: dict[str, Any] = Field(..., description="Raw command payload.")


@router.post("/send-gif", response_model=DivoomApiResponse)
async def send_gif(
    request: TimeGateSendGifRequest,
    device=Depends(_select_timegate_device),
) -> DivoomApiResponse:
    """Send a GIF frame (Draw/SendHttpGif)."""
    lcd_array = _validate_lcd_array(request.lcd_array)
    pic_width = request.pic_width or device.screen_size
    payload = {
        "Command": "Draw/SendHttpGif",
        "LcdArray": lcd_array,
        "PicNum": request.pic_num,
        "PicWidth": pic_width,
        "PicOffset": request.pic_offset,
        "PicID": request.pic_id,
        "PicSpeed": request.pic_speed,
        "PicData": request.pic_data,
    }
    return await _post_command(payload, device.host)


@router.post("/send-text", response_model=DivoomApiResponse)
async def send_text(
    request: TimeGateSendTextRequest,
    device=Depends(_select_timegate_device),
) -> DivoomApiResponse:
    """Send scrolling text (Draw/SendHttpText)."""
    payload = {
        "Command": "Draw/SendHttpText",
        "LcdIndex": request.lcd_index,
        "TextId": request.text_id,
        "x": request.x,
        "y": request.y,
        "dir": request.direction,
        "font": request.font,
        "TextWidth": request.text_width,
        "TextString": request.text,
        "speed": request.speed,
        "color": request.color,
        "align": request.align,
    }
    return await _post_command(payload, device.host)


@router.post("/play-gif", response_model=DivoomApiResponse)
async def play_gif(
    request: TimeGatePlayGifRequest,
    device=Depends(_select_timegate_device),
) -> DivoomApiResponse:
    """Play GIFs from URLs (Device/PlayGif)."""
    lcd_array = _validate_lcd_array(request.lcd_array)
    payload = {
        "Command": "Device/PlayGif",
        "LcdArray": lcd_array,
        "FileName": request.file_name,
    }
    return await _post_command(payload, device.host)


@router.post("/set-brightness", response_model=DivoomApiResponse)
async def set_brightness(
    request: TimeGateBrightnessRequest,
    device=Depends(_select_timegate_device),
) -> DivoomApiResponse:
    """Set brightness (Channel/SetBrightness)."""
    payload = {"Command": "Channel/SetBrightness", "Brightness": request.brightness}
    return await _post_command(payload, device.host)


@router.post("/reset-gif-id", response_model=DivoomApiResponse)
async def reset_gif_id(device=Depends(_select_timegate_device)) -> DivoomApiResponse:
    """Reset GIF cache (Draw/ResetHttpGifId)."""
    payload = {"Command": "Draw/ResetHttpGifId"}
    return await _post_command(payload, device.host)


@router.post("/command-list", response_model=DivoomApiResponse)
async def command_list(
    request: TimeGateCommandListRequest,
    device=Depends(_select_timegate_device),
) -> DivoomApiResponse:
    """Send a list of commands (Draw/CommandList)."""
    payload = {"Command": "Draw/CommandList", "CommandList": request.command_list}
    return await _post_command(payload, device.host)


@router.post("/command")
async def command(
    request: TimeGateCommandRequest,
    device=Depends(_select_timegate_device),
) -> dict[str, Any]:
    """Send a raw command payload to the device."""
    return await _post_raw(request.command, device.host)
