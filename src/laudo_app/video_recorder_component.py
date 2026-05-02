from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "components" / "video_recorder"
_video_recorder = components.declare_component("video_recorder", path=str(_COMPONENT_DIR))


def render_video_recorder(*, key: str, ack_event_id: str = "") -> dict[str, Any] | None:
    value: dict[str, Any] | None = _video_recorder(key=key, ack_event_id=str(ack_event_id or ""), default=None)
    if not value:
        return None
    event_kind = str(value.get("event_kind", "") or "")
    event_id = str(value.get("event_id", "") or "")
    session_id = str(value.get("session_id", "") or "")
    mime_type = str(value.get("mime_type", "video/webm") or "video/webm")
    timestamp = int(value.get("timestamp", 0)) if isinstance(value.get("timestamp"), (int, float)) else 0
    chunk_index = int(value.get("chunk_index", 0)) if isinstance(value.get("chunk_index"), (int, float)) else 0

    result: dict[str, Any] = {
        "event_kind": event_kind,
        "event_id": event_id,
        "session_id": session_id,
        "mime_type": mime_type,
        "timestamp": timestamp,
        "chunk_index": chunk_index,
    }

    data_url = value.get("data_url")
    if isinstance(data_url, str) and "," in data_url:
        _, encoded = data_url.split(",", 1)
        try:
            result["data"] = base64.b64decode(encoded)
        except Exception:
            return None

    if not event_kind or not event_id or not session_id:
        return None
    return result
