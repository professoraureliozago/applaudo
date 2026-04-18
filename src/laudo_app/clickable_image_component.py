from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "components" / "clickable_image"
_clickable_image = components.declare_component("clickable_image", path=str(_COMPONENT_DIR))


def render_clickable_image(path: Path, *, key: str) -> int | None:
    if not path.exists() or not path.is_file():
        return None

    suffix = path.suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    value: dict[str, Any] | None = _clickable_image(
        key=key,
        data_url=f"data:{mime_type};base64,{encoded}",
        default=None,
    )
    if not value:
        return None
    clicked_at = value.get("clicked_at")
    return int(clicked_at) if isinstance(clicked_at, (int, float)) else None
