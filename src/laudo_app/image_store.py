from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import shutil

CAPTURE_DIR = Path("captured_images")


def _exam_folder(exam_id: int | None) -> Path:
    if exam_id is None:
        return CAPTURE_DIR / "unassigned"
    return CAPTURE_DIR / f"exam_{exam_id}"


def _metadata_file(exam_id: int | None) -> Path:
    return _exam_folder(exam_id) / "metadata.json"


def ensure_capture_dir(exam_id: int | None = None) -> Path:
    folder = _exam_folder(exam_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _load_metadata(exam_id: int | None) -> dict[str, str]:
    ensure_capture_dir(exam_id)
    metadata_file = _metadata_file(exam_id)
    if not metadata_file.exists():
        return {}
    try:
        return json.loads(metadata_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_metadata(data: dict[str, str], exam_id: int | None) -> None:
    ensure_capture_dir(exam_id)
    _metadata_file(exam_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def save_captured_image(image_bytes: bytes, suffix: str = ".jpg", caption: str = "", exam_id: int | None = None) -> Path:
    folder = ensure_capture_dir(exam_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = folder / f"captura_{timestamp}{suffix}"
    path.write_bytes(image_bytes)

    metadata = _load_metadata(exam_id)
    metadata[path.name] = caption.strip() or "imagem do exame"
    _save_metadata(metadata, exam_id)

    return path


def list_captured_images(exam_id: int | None = None) -> list[Path]:
    folder = ensure_capture_dir(exam_id)
    images = sorted(
        [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}],
        reverse=True,
    )
    return images


def get_image_caption(path: Path, exam_id: int | None = None) -> str:
    metadata = _load_metadata(exam_id)
    return metadata.get(path.name, "imagem do exame")


def load_selected_images_with_captions(paths: list[str], exam_id: int | None = None) -> list[tuple[bytes, str]]:
    data: list[tuple[bytes, str]] = []
    for p in paths:
        path = Path(p)
        if path.exists() and path.is_file():
            data.append((path.read_bytes(), get_image_caption(path, exam_id=exam_id)))
    return data


def reassign_images_to_exam(paths: list[str], exam_id: int) -> list[Path]:
    destination = ensure_capture_dir(exam_id)
    src_metadata = _load_metadata(None)
    dst_metadata = _load_metadata(exam_id)
    moved: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        new_path = destination / path.name
        if new_path.exists():
            stem = new_path.stem
            suffix = new_path.suffix
            new_path = destination / f"{stem}_{datetime.now().strftime('%H%M%S%f')}{suffix}"
        shutil.move(str(path), str(new_path))
        caption = src_metadata.pop(path.name, "imagem do exame")
        dst_metadata[new_path.name] = caption
        moved.append(new_path)

    _save_metadata(src_metadata, None)
    _save_metadata(dst_metadata, exam_id)
    return moved
