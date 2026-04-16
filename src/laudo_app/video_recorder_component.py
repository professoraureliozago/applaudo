from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "components" / "video_recorder"
_video_recorder = components.declare_component("video_recorder", path=str(_COMPONENT_DIR))


def render_video_recorder(*, key: str) -> tuple[bytes, str, int] | None:
    value: dict[str, Any] | None = _video_recorder(key=key, default=None)
    if not value:
        return None
    data_url = value.get("data_url")
    mime_type = value.get("mime_type", "video/webm")
    timestamp = value.get("timestamp", 0)
    if not isinstance(data_url, str) or "," not in data_url:
        return None
    _, encoded = data_url.split(",", 1)
    try:
        data = base64.b64decode(encoded)
    except Exception:
        return None
    return data, str(mime_type), int(timestamp) if isinstance(timestamp, (int, float)) else 0
