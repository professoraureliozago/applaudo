from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "components" / "webrtc_click_snapshot"
_webrtc_click_snapshot = components.declare_component("webrtc_click_snapshot", path=str(_COMPONENT_DIR))


def render_webrtc_click_snapshot(
    *,
    key: str,
    width: int = 960,
    height: int = 540,
    image_format: str = "image/jpeg",
    image_quality: float = 0.92,
) -> tuple[bytes, int] | None:
    value: dict[str, Any] | None = _webrtc_click_snapshot(
        key=key,
        width=width,
        height=height,
        image_format=image_format,
        image_quality=image_quality,
        default=None,
    )
    if not value:
        return None

    data_url = value.get("data_url")
    timestamp = value.get("timestamp", 0)
    if not isinstance(data_url, str) or "," not in data_url:
        return None

    _, encoded = data_url.split(",", 1)
    try:
        data = base64.b64decode(encoded)
    except Exception:
        return None
    ts = int(timestamp) if isinstance(timestamp, (int, float)) else 0
    return data, ts
