from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "components" / "image_annotator"
_image_annotator = components.declare_component("image_annotator", path=str(_COMPONENT_DIR))


def render_image_annotator(
    path: Path,
    *,
    key: str,
    annotation_text: str,
    color_hex: str,
    line_width: int,
    font_size: int,
    start_x: float = 18,
    start_y: float = 22,
    end_x: float = 70,
    end_y: float = 52,
) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None

    suffix = path.suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    value: dict[str, Any] | None = _image_annotator(
        key=key,
        data_url=f"data:{mime_type};base64,{encoded}",
        image_key=f"{path.resolve()}:{path.stat().st_mtime_ns}",
        mime_type=mime_type,
        annotation_text=annotation_text,
        color_hex=color_hex,
        line_width=line_width,
        font_size=font_size,
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        default=None,
    )
    return value or None
