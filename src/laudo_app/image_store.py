from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

CAPTURE_DIR = Path("captured_images")


def _metadata_file() -> Path:
    return CAPTURE_DIR / "metadata.json"


def ensure_capture_dir() -> Path:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    return CAPTURE_DIR


def _load_metadata() -> dict[str, str]:
    ensure_capture_dir()
    metadata_file = _metadata_file()
    if not metadata_file.exists():
        return {}
    try:
        return json.loads(metadata_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_metadata(data: dict[str, str]) -> None:
    ensure_capture_dir()
    _metadata_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def infer_caption_from_text(text: str) -> str:
    text_l = text.lower()
    rules = [
        ("pós-polipectomia", ["polipectomia", "pos polipectomia", "pós polipectomia"]),
        ("ceco", ["ceco", "óstio apendicular", "ostio apendicular"]),
        ("reto", ["reto"]),
        ("cólon esquerdo", ["descendente", "sigmoide", "cólon esquerdo", "colon esquerdo"]),
        ("íleo terminal", ["íleo terminal", "ileo terminal"]),
    ]
    for caption, kws in rules:
        if any(k in text_l for k in kws):
            return caption
    return "imagem do exame"


def save_captured_image(image_bytes: bytes, suffix: str = ".jpg", caption: str = "") -> Path:
    folder = ensure_capture_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = folder / f"captura_{timestamp}{suffix}"
    path.write_bytes(image_bytes)

    metadata = _load_metadata()
    metadata[path.name] = caption.strip() or "imagem do exame"
    _save_metadata(metadata)

    return path


def list_captured_images() -> list[Path]:
    folder = ensure_capture_dir()
    images = sorted(
        [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}],
        reverse=True,
    )
    return images


def get_image_caption(path: Path) -> str:
    metadata = _load_metadata()
    return metadata.get(path.name, "imagem do exame")


def load_selected_images_with_captions(paths: list[str]) -> list[tuple[bytes, str]]:
    data: list[tuple[bytes, str]] = []
    for p in paths:
        path = Path(p)
        if path.exists() and path.is_file():
            data.append((path.read_bytes(), get_image_caption(path)))
    return data
