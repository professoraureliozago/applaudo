from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "components" / "continuous_audio"
_continuous_audio = components.declare_component("continuous_audio", path=str(_COMPONENT_DIR))


def render_continuous_audio(
    *,
    key: str,
    chunk_ms: int = 3500,
    silence_ms: int = 1100,
    vad_threshold: float = 0.018,
) -> tuple[bytes, str, int] | None:
    value: dict[str, Any] | None = _continuous_audio(
        key=key,
        chunk_ms=chunk_ms,
        silence_ms=silence_ms,
        vad_threshold=vad_threshold,
        default=None,
    )
    if not value:
        return None

    data_url = value.get("data_url")
    if not isinstance(data_url, str) or "," not in data_url:
        return None
    _, encoded = data_url.split(",", 1)
    try:
        data = base64.b64decode(encoded)
    except Exception:
        return None

    mime_type = str(value.get("mime_type", "audio/webm"))
    timestamp = value.get("timestamp", 0)
    ts = int(timestamp) if isinstance(timestamp, (int, float)) else 0
    return data, mime_type, ts
