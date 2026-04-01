from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "components" / "video_recorder"
_video_recorder = components.declare_component("video_recorder", path=str(_COMPONENT_DIR))


def render_video_recorder(*, key: str) -> tuple[bytes, str] | None:
    value: dict[str, Any] | None = _video_recorder(key=key, default=None)
    if not value:
        return None
    encoded = value.get("data_base64")
    mime_type = value.get("mime_type", "video/webm")
    if not isinstance(encoded, str):
        return None
    try:
        data = base64.b64decode(encoded)
    except Exception:
        return None
    return data, str(mime_type)
