from __future__ import annotations

from datetime import datetime
from pathlib import Path

CAPTURE_DIR = Path("captured_images")


def ensure_capture_dir() -> Path:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    return CAPTURE_DIR


def save_captured_image(image_bytes: bytes, suffix: str = ".jpg") -> Path:
    folder = ensure_capture_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = folder / f"captura_{timestamp}{suffix}"
    path.write_bytes(image_bytes)
    return path


def list_captured_images() -> list[Path]:
    folder = ensure_capture_dir()
    images = sorted(
        [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}],
        reverse=True,
    )
    return images


def load_selected_images(paths: list[str]) -> list[bytes]:
    data: list[bytes] = []
    for p in paths:
        path = Path(p)
        if path.exists() and path.is_file():
            data.append(path.read_bytes())
    return data
