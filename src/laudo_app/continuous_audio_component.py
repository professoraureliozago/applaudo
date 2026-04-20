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
    vad_threshold: float = 0.008,
) -> dict[str, Any] | None:
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
    transcript_text = value.get("transcript_text")
    data: bytes | None = None
    if isinstance(data_url, str) and "," in data_url:
        _, encoded = data_url.split(",", 1)
        try:
            data = base64.b64decode(encoded)
        except Exception:
            data = None
    if not data and not isinstance(transcript_text, str):
        return None

    mime_type = str(value.get("mime_type", "audio/wav"))
    timestamp = value.get("timestamp", 0)
    ts = int(timestamp) if isinstance(timestamp, (int, float)) else 0
    return {
        "audio_bytes": data,
        "mime_type": mime_type,
        "timestamp": ts,
        "transcript_text": transcript_text if isinstance(transcript_text, str) else "",
    }
